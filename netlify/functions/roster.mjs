// Team rosters for the reporting system.
//
//   GET   /api/roster/<teamSeasonId>          -> {team, players}   (public)
//   POST  /api/roster/<teamSeasonId>          -> add one player
//   POST  /api/roster/<teamSeasonId>/import   -> bulk add, one name per line
//   PATCH /api/roster/player/<id>             -> rename / regrade / deactivate
//   GET   /api/roster/__ping
//
// Rosters exist because entered players have no TennisReporting id, and player
// identity is what makes the ladder, the position matrix and all-state follow a
// person across matches. `roster_player.id` comes from a sequence in the
// reserved range so it can be used verbatim as the compiled TR player id.
//
// Reading a roster needs no session — the site already publishes who played.
// Writing needs a claim on the team.

import {
  HttpError, currentCoach, db, json, nextIds, readJson, requireClaim,
  requireCoach, route, segments, tx,
} from './lib/db.mjs';

const MAX_IMPORT_LINES = 60;

function cleanName(value, field) {
  const s = String(value ?? '').trim().replace(/\s+/g, ' ');
  if (!s) throw new HttpError(400, `${field} is required`);
  if (s.length > 60) throw new HttpError(400, `${field} is too long`);
  return s;
}

/** Split "Last, First" or "First Last" into parts. */
function splitName(line) {
  const s = line.trim().replace(/\s+/g, ' ');
  if (!s) return null;
  if (s.includes(',')) {
    const [last, first] = s.split(',', 2);
    if (!last.trim() || !first.trim()) return null;
    return { first: first.trim(), last: last.trim() };
  }
  const parts = s.split(' ');
  if (parts.length < 2) return null;
  return { first: parts.slice(0, -1).join(' '), last: parts[parts.length - 1] };
}

async function listPlayers(teamSeasonId) {
  return db()`
    SELECT id, first_name, last_name, grade, tr_player_id, active
      FROM roster_player
     WHERE team_season_id = ${teamSeasonId}
     ORDER BY active DESC, lower(last_name), lower(first_name)
  `;
}

/**
 * Find or create players on a team, returning ids in the order given.
 *
 * Also used by duals.mjs when a home coach records opponents who are not yet on
 * the away team's roster — the alternative is free-text opponent names, which
 * would fork player identity the first time anyone typed "Maddie" for "Madison".
 * The unique index on (team, lower(first), lower(last)) makes this idempotent.
 */
export async function ensurePlayers(teamSeasonId, people, coachId) {
  if (!people.length) return [];
  const sql = db();
  const existing = await sql`
    SELECT id, lower(first_name) AS f, lower(last_name) AS l
      FROM roster_player WHERE team_season_id = ${teamSeasonId}
  `;
  const index = new Map(existing.map((r) => [`${r.f}|${r.l}`, r.id]));

  const missing = [];
  for (const p of people) {
    const key = `${cleanName(p.firstName, 'first name').toLowerCase()}|` +
                `${cleanName(p.lastName, 'last name').toLowerCase()}`;
    if (!index.has(key) && !missing.some((m) => m.key === key)) {
      missing.push({ key, person: p });
    }
  }

  if (missing.length) {
    const ids = await nextIds('roster_player_id_seq', missing.length);
    await tx(missing.map(({ person }, i) => sql`
      INSERT INTO roster_player (id, team_season_id, first_name, last_name, grade, created_by)
      VALUES (${ids[i]}, ${teamSeasonId}, ${cleanName(person.firstName, 'first name')},
              ${cleanName(person.lastName, 'last name')},
              ${String(person.grade ?? '').trim()}, ${coachId})
      ON CONFLICT (team_season_id, lower(first_name), lower(last_name)) DO NOTHING
    `));
    missing.forEach(({ key }, i) => index.set(key, ids[i]));

    // A concurrent insert can win the ON CONFLICT race, leaving our reserved id
    // unused and the real id different. Re-read so callers get the row that
    // actually exists.
    const after = await sql`
      SELECT id, lower(first_name) AS f, lower(last_name) AS l
        FROM roster_player WHERE team_season_id = ${teamSeasonId}
    `;
    for (const r of after) index.set(`${r.f}|${r.l}`, r.id);
  }

  return people.map((p) => index.get(
    `${String(p.firstName).trim().replace(/\s+/g, ' ').toLowerCase()}|` +
    `${String(p.lastName).trim().replace(/\s+/g, ' ').toLowerCase()}`
  ));
}

export default async function handler(req) {
  return route(async () => {
    const parts = segments(req, 'roster');
    if (parts[0] === '__ping') return json({ ok: true });
    if (!parts.length) throw new HttpError(400, 'team required');

    const sql = db();

    // PATCH /api/roster/player/<id>
    if (parts[0] === 'player') {
      const playerId = Number(parts[1]);
      if (!Number.isFinite(playerId)) throw new HttpError(400, 'bad player id');
      if (req.method !== 'PATCH') throw new HttpError(405, 'method not allowed');

      const coach = await requireCoach(req);
      const [player] = await sql`
        SELECT id, team_season_id, first_name, last_name, grade, active
          FROM roster_player WHERE id = ${playerId}
      `;
      if (!player) throw new HttpError(404, 'player not found');
      await requireClaim(coach, player.team_season_id);

      const body = await readJson(req);
      const next = {
        first_name: body.firstName !== undefined
          ? cleanName(body.firstName, 'first name') : player.first_name,
        last_name: body.lastName !== undefined
          ? cleanName(body.lastName, 'last name') : player.last_name,
        grade: body.grade !== undefined ? String(body.grade).trim() : player.grade,
        active: body.active !== undefined ? !!body.active : player.active,
      };

      await tx([
        sql`
          UPDATE roster_player
             SET first_name = ${next.first_name}, last_name = ${next.last_name},
                 grade = ${next.grade}, active = ${next.active}, updated_at = now()
           WHERE id = ${playerId}
        `,
        sql`
          INSERT INTO audit_log (actor_coach_id, entity, entity_id, action, before, after)
          VALUES (${coach.id}, 'roster_player', ${playerId}, 'update',
                  ${JSON.stringify(player)}::jsonb, ${JSON.stringify(next)}::jsonb)
        `,
      ]);
      return json({ ok: true, player: { id: playerId, ...next } });
    }

    const teamSeasonId = Number(parts[0]);
    if (!Number.isFinite(teamSeasonId)) throw new HttpError(400, 'bad team id');

    if (req.method === 'GET') {
      const [team] = await sql`
        SELECT id, year, school_id, school_name, gender_id, is_jv, league,
               classification, entry_enabled
          FROM team_season WHERE id = ${teamSeasonId}
      `;
      if (!team) throw new HttpError(404, 'team not found');
      const coach = await currentCoach(req);
      const players = await listPlayers(teamSeasonId);
      return json({
        team,
        players,
        canEdit: !!coach && (coach.is_admin || (await claims(coach.id)).has(teamSeasonId)),
      });
    }

    if (req.method !== 'POST') throw new HttpError(405, 'method not allowed');

    const coach = await requireCoach(req);
    await requireClaim(coach, teamSeasonId);
    const body = await readJson(req);

    // POST /api/roster/<id>/import — a pasted list, one name per line.
    if (parts[1] === 'import') {
      const lines = String(body.text || '').split('\n')
        .map(splitName).filter(Boolean).slice(0, MAX_IMPORT_LINES);
      if (!lines.length) throw new HttpError(400, 'no names recognised');
      await ensurePlayers(
        teamSeasonId,
        lines.map((n) => ({ firstName: n.first, lastName: n.last, grade: '' })),
        coach.id
      );
      return json({ ok: true, added: lines.length, players: await listPlayers(teamSeasonId) });
    }

    const [id] = await ensurePlayers(teamSeasonId, [{
      firstName: body.firstName, lastName: body.lastName, grade: body.grade,
    }], coach.id);
    return json({ ok: true, id, players: await listPlayers(teamSeasonId) });
  });
}

async function claims(coachId) {
  const rows = await db()`
    SELECT team_season_id FROM team_claim WHERE coach_id = ${coachId}
  `;
  return new Set(rows.map((r) => Number(r.team_season_id)));
}

export const config = { path: '/api/roster/*' };
