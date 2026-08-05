// Administrator surface and the season CSV export.
//
//   GET   /api/admin/disputes                 -> contested duals with both sides
//   GET   /api/admin/teams?year=&league=      -> beta enrolment status
//   POST  /api/admin/teams/<id>/entry {on}    -> open or close entry for a team
//   POST  /api/admin/claims  {email, teamSeasonId, role}
//   DELETE /api/admin/claims/<coachId>/<teamSeasonId>
//   GET   /api/admin/audit?limit=             -> recent write history
//   GET   /api/admin/export?year=&league=     -> CSV of every reported flight
//   GET   /api/admin/__ping
//
// The export is deliberately public: a seeding committee asking for the
// spreadsheet should not need an account, and everything in it is already
// published on the site. Every other route requires an administrator.

import {
  HttpError, csv, db, json, readJson, requireAdmin, route, segments,
} from './lib/db.mjs';

function csvRow(values) {
  return values.map((v) => {
    const s = v === null || v === undefined ? '' : String(v);
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  }).join(',');
}

async function exportCsv(req) {
  const url = new URL(req.url);
  const year = Number(url.searchParams.get('year'));
  if (!Number.isFinite(year)) throw new HttpError(400, 'year is required');
  const league = url.searchParams.get('league');

  const rows = await db()`
    SELECT d.id AS dual_id, d.played_on, d.gender_id, d.is_jv, d.status,
           d.is_postseason, d.event_name,
           d.home_school_id, hs.school_name AS home_school, hs.league AS home_league,
           d.away_school_id, aws.school_name AS away_school, aws.league AS away_league,
           dl.match_type, dl.flight, dl.home_won, dl.finish,
           (SELECT string_agg(rp.first_name || ' ' || rp.last_name, ' / '
                              ORDER BY lp.position)
              FROM line_player lp JOIN roster_player rp ON rp.id = lp.roster_player_id
             WHERE lp.dual_line_id = dl.id AND lp.side = 'home') AS home_players,
           (SELECT string_agg(rp.first_name || ' ' || rp.last_name, ' / '
                              ORDER BY lp.position)
              FROM line_player lp JOIN roster_player rp ON rp.id = lp.roster_player_id
             WHERE lp.dual_line_id = dl.id AND lp.side = 'away') AS away_players,
           (SELECT string_agg(ls.home_games || '-' || ls.away_games, ', '
                              ORDER BY ls.set_number)
              FROM line_set ls WHERE ls.dual_line_id = dl.id) AS score
      FROM dual d
      JOIN dual_line dl ON dl.dual_id = d.id
      LEFT JOIN team_season hs ON hs.year = d.year AND hs.school_id = d.home_school_id
                              AND hs.gender_id = d.gender_id AND hs.is_jv = d.is_jv
      LEFT JOIN team_season aws ON aws.year = d.year AND aws.school_id = d.away_school_id
                              AND aws.gender_id = d.gender_id AND aws.is_jv = d.is_jv
     WHERE d.year = ${year} AND d.status <> 'void' AND d.status <> 'draft'
       AND (${league}::text IS NULL OR hs.league = ${league} OR aws.league = ${league})
     ORDER BY d.played_on, d.id, dl.match_type, dl.flight
  `;

  const header = [
    'dual_id', 'date', 'gender', 'level', 'status', 'postseason', 'event',
    'home_school', 'home_league', 'away_school', 'away_league',
    'flight', 'home_players', 'away_players', 'score', 'winner', 'finish',
  ];
  const body = rows.map((r) => csvRow([
    r.dual_id, r.played_on, r.gender_id === 1 ? 'Boys' : 'Girls',
    r.is_jv ? 'JV' : 'Varsity', r.status, r.is_postseason ? 'yes' : 'no', r.event_name,
    r.home_school, r.home_league, r.away_school, r.away_league,
    `${r.flight}${r.match_type === 'Singles' ? 'S' : 'D'}`,
    r.home_players, r.away_players, r.score,
    r.home_won === null ? '' : (r.home_won ? 'home' : 'away'), r.finish,
  ]));

  const slug = league ? `-${league.replace(/[^A-Za-z0-9]+/g, '-')}` : '';
  return csv([csvRow(header), ...body].join('\n') + '\n',
             `oregon-tennis-${year}${slug}.csv`);
}

export default async function handler(req) {
  return route(async () => {
    const parts = segments(req, 'admin');
    if (parts[0] === '__ping') return json({ ok: true });
    if (parts[0] === 'export' && req.method === 'GET') return exportCsv(req);

    const admin = await requireAdmin(req);
    const sql = db();

    if (parts[0] === 'disputes' && req.method === 'GET') {
      const rows = await sql`
        SELECT d.id, d.played_on, d.gender_id, d.is_jv, d.dispute_note, d.updated_at,
               d.home_school_id, d.away_school_id, d.title,
               rc.email AS reported_by_email
          FROM dual d LEFT JOIN coach rc ON rc.id = d.reported_by
         WHERE d.status = 'contested'
         ORDER BY d.updated_at DESC
      `;
      return json({ disputes: rows });
    }

    if (parts[0] === 'teams' && req.method === 'GET') {
      const url = new URL(req.url);
      const year = Number(url.searchParams.get('year')) || new Date().getFullYear();
      const league = url.searchParams.get('league');
      const rows = await sql`
        SELECT ts.*,
               (SELECT count(*)::int FROM team_claim tc WHERE tc.team_season_id = ts.id) AS coaches,
               (SELECT count(*)::int FROM roster_player rp
                 WHERE rp.team_season_id = ts.id AND rp.active) AS players,
               (SELECT count(*)::int FROM dual d
                 WHERE d.year = ts.year AND d.gender_id = ts.gender_id
                   AND d.is_jv = ts.is_jv AND d.status <> 'void'
                   AND (d.home_school_id = ts.school_id OR d.away_school_id = ts.school_id)
               ) AS duals
          FROM team_season ts
         WHERE ts.year = ${year}
           AND (${league}::text IS NULL OR ts.league = ${league})
         ORDER BY ts.league, ts.school_name, ts.gender_id
      `;
      return json({ teams: rows });
    }

    // Beta enrolment. `entry_enabled` is the gate that decides who can type;
    // flipping it per league is how the beta stays a beta.
    if (parts[0] === 'teams' && parts[2] === 'entry' && req.method === 'POST') {
      const teamSeasonId = Number(parts[1]);
      const { on } = await readJson(req);
      await sql`UPDATE team_season SET entry_enabled = ${!!on} WHERE id = ${teamSeasonId}`;
      await sql`
        INSERT INTO audit_log (actor_coach_id, entity, entity_id, action, after)
        VALUES (${admin.id}, 'team_season', ${teamSeasonId}, 'entry_enabled',
                ${JSON.stringify({ on: !!on })}::jsonb)
      `;
      return json({ ok: true, entryEnabled: !!on });
    }

    if (parts[0] === 'claims' && req.method === 'POST') {
      const { email, teamSeasonId, role = 'head', name = '' } = await readJson(req);
      const clean = String(email || '').trim().toLowerCase();
      if (!clean.includes('@')) throw new HttpError(400, 'a valid email is required');

      const [coach] = await sql`
        INSERT INTO coach (email, name) VALUES (${clean}, ${name})
        ON CONFLICT (lower(email)) DO UPDATE SET email = EXCLUDED.email
        RETURNING id, email
      `;
      await sql`
        INSERT INTO team_claim (coach_id, team_season_id, role, granted_by)
        VALUES (${coach.id}, ${Number(teamSeasonId)}, ${role}, ${admin.id})
        ON CONFLICT (coach_id, team_season_id) DO UPDATE SET role = EXCLUDED.role
      `;
      await sql`
        INSERT INTO audit_log (actor_coach_id, entity, entity_id, action, after)
        VALUES (${admin.id}, 'team_claim', ${Number(teamSeasonId)}, 'grant',
                ${JSON.stringify({ email: clean, role })}::jsonb)
      `;
      return json({ ok: true, coachId: Number(coach.id) });
    }

    if (parts[0] === 'claims' && req.method === 'DELETE') {
      const coachId = Number(parts[1]);
      const teamSeasonId = Number(parts[2]);
      await sql`
        DELETE FROM team_claim
         WHERE coach_id = ${coachId} AND team_season_id = ${teamSeasonId}
      `;
      await sql`
        INSERT INTO audit_log (actor_coach_id, entity, entity_id, action, before)
        VALUES (${admin.id}, 'team_claim', ${teamSeasonId}, 'revoke',
                ${JSON.stringify({ coachId })}::jsonb)
      `;
      return json({ ok: true });
    }

    if (parts[0] === 'audit' && req.method === 'GET') {
      const limit = Math.min(Number(new URL(req.url).searchParams.get('limit')) || 100, 500);
      const rows = await sql`
        SELECT a.id, a.at, a.entity, a.entity_id, a.action, c.email
          FROM audit_log a LEFT JOIN coach c ON c.id = a.actor_coach_id
         ORDER BY a.at DESC LIMIT ${limit}
      `;
      return json({ audit: rows });
    }

    throw new HttpError(404, 'unknown admin route');
  });
}

export const config = { path: '/api/admin/*' };
