// Dual-match reporting.
//
//   GET    /api/duals?team=<teamSeasonId>[&status=]  -> duals involving a team
//   POST   /api/duals                                -> file a dual (home team)
//   GET    /api/duals/<id>                           -> the full card
//   PUT    /api/duals/<id>                           -> replace the card
//   POST   /api/duals/<id>/confirm                   -> away team agrees
//   POST   /api/duals/<id>/dispute   {note}          -> away team objects
//   POST   /api/duals/<id>/resolve   {status}        -> administrator
//   DELETE /api/duals/<id>                           -> void
//   GET    /api/duals/__ping
//
// The home coach is the reporter of record; the away coach confirms or disputes.
// A dual is published as soon as it is filed — confirmation raises confidence but
// does not gate publication, because waiting on a coach who never signs in would
// silently drop the other team's season. A disputed dual is published too, and
// flagged, since freezing disputes out of the maths would reward disputing every
// loss.
//
// Two concurrency rules, both learned from the read-modify-write deep merge in
// scores.mjs (where simultaneous saves silently lose an edit):
//
//   1. A card is REPLACED, never merged. One transaction deletes every line and
//      re-inserts, so there is no question of whether an omitted flight means
//      "unchanged" or "cleared".
//   2. Writes carry the `updatedAt` the client loaded. A mismatch is a 409, not
//      a silent overwrite.

import {
  HttpError, currentCoach, db, json, nextIds, readJson, requireAdmin,
  requireClaim, requireCoach, route, segments, tx,
} from './_db.mjs';
import { ensurePlayers } from './roster.mjs';

const MATCH_TYPES = new Set(['Singles', 'Doubles']);
const PUBLISHED = new Set(['reported', 'confirmed', 'contested']);

// ---------------------------------------------------------------------------
// Validation
//
// Coach-entered data always wins statewide, so one fat-fingered entry has teeth.
// Everything below is a rule a real dual cannot break.
// ---------------------------------------------------------------------------

const FINISHES = new Set([null, undefined, 'retired', 'default']);

/**
 * The bottom-up forfeit rule.
 *
 * A team short of players gives up the bottom of the card, so the contested
 * flights have to run from the top with no hole in them. Fourth singles played
 * while third singles is absent is a data-entry error, not a lineup. Enforced
 * here as well as in the browser because the browser is not the authority.
 */
function validateBottomUp(lines) {
  for (const matchType of ['Singles', 'Doubles']) {
    const present = new Map();
    for (const line of lines) {
      if (line.matchType === matchType) present.set(Number(line.flight), line);
    }
    // A default has a winner but was not contested, so it forfeits the position
    // exactly as an absent flight does.
    const contested = [...present.entries()]
      .filter(([, l]) => l.finish !== 'default')
      .map(([f]) => f);
    if (!contested.length) continue;
    const deepest = Math.max(...contested);
    for (let f = 1; f < deepest; f += 1) {
      const line = present.get(f);
      if (!line || line.finish === 'default') {
        const pos = (n) => `${n}${matchType === 'Singles' ? 'S' : 'D'}`;
        throw new HttpError(400,
          `${pos(deepest)} was played but ${pos(f)} was not. Forfeits come from ` +
          `the bottom of the card up.`);
      }
    }
  }
}

function validateCard(lines) {
  if (!Array.isArray(lines) || !lines.length) {
    throw new HttpError(400, 'a dual needs at least one flight');
  }
  const seen = new Set();
  const players = new Set();

  for (const line of lines) {
    if (!MATCH_TYPES.has(line.matchType)) {
      throw new HttpError(400, `unknown match type ${line.matchType}`);
    }
    const flight = Number(line.flight);
    // Oregon's card is 4 singles + 4 doubles. Six-flight duals are legal and
    // common; a short card is simply fewer lines.
    if (!Number.isInteger(flight) || flight < 1 || flight > 4) {
      throw new HttpError(400, `flight ${line.flight} is out of range`);
    }
    const key = `${line.matchType}${flight}`;
    if (seen.has(key)) throw new HttpError(400, `${key} appears twice`);
    seen.add(key);

    if (!FINISHES.has(line.finish ?? null)) {
      throw new HttpError(400, `${key}: unknown finish ${line.finish}`);
    }
    if (line.finish && line.homeWon !== true && line.homeWon !== false) {
      throw new HttpError(400, `${key}: a ${line.finish} needs a winner`);
    }
    if (line.finish === 'default' && (line.sets || []).length) {
      throw new HttpError(400, `${key}: a default has no score`);
    }

    const expected = line.matchType === 'Doubles' ? 2 : 1;
    for (const side of ['homePlayers', 'awayPlayers']) {
      const list = line[side] || [];
      // On a default one side had nobody — that is the whole meaning of the
      // result, so an empty side is required rather than merely tolerated.
      const winnerSide = line.homeWon ? 'homePlayers' : 'awayPlayers';
      if (line.finish === 'default' && side !== winnerSide) {
        if (list.length) throw new HttpError(400, `${key}: a defaulting team has no player`);
        continue;
      }
      if (list.length !== expected) {
        throw new HttpError(400, `${key} needs ${expected} player(s) per side`);
      }
      for (const p of list) {
        const id = p && p.id;
        if (id) {
          // A player cannot be in two flights of the same dual.
          if (players.has(`${side}:${id}`)) {
            throw new HttpError(400, 'a player appears in two flights of this dual');
          }
          players.add(`${side}:${id}`);
        }
      }
    }

    for (const s of line.sets || []) {
      const h = Number(s.homeGames);
      const a = Number(s.awayGames);
      const n = Number(s.number);
      if (!Number.isInteger(n) || n < 1 || n > 3) {
        throw new HttpError(400, `${key}: set number ${s.number} is out of range`);
      }
      if (!Number.isInteger(h) || !Number.isInteger(a) || h < 0 || a < 0) {
        throw new HttpError(400, `${key}: set ${n} has a non-numeric score`);
      }
      // Generous upper bound: covers 7-6, 8-game pro sets and 10-point match
      // tiebreaks (which can run past 10) without trying to referee tennis.
      if (h > 30 || a > 30) throw new HttpError(400, `${key}: set ${n} score is implausible`);
      if (h === a) throw new HttpError(400, `${key}: set ${n} cannot be level`);
    }

    if (line.homeWon !== null && line.homeWon !== undefined && typeof line.homeWon !== 'boolean') {
      throw new HttpError(400, `${key}: homeWon must be true, false or null`);
    }
  }

  validateBottomUp(lines);
}

// ---------------------------------------------------------------------------
// Loading
// ---------------------------------------------------------------------------

async function loadDual(id) {
  const sql = db();
  const [dual] = await sql`SELECT * FROM dual WHERE id = ${id}`;
  if (!dual) throw new HttpError(404, 'dual not found');

  const lines = await sql`
    SELECT id, match_type, flight, home_won, finish
      FROM dual_line WHERE dual_id = ${id}
     ORDER BY match_type, flight
  `;
  if (!lines.length) return { ...dual, lines: [] };

  const ids = lines.map((l) => l.id);
  const [people, sets] = await Promise.all([
    sql`
      SELECT lp.dual_line_id, lp.side, lp.position, rp.id, rp.first_name, rp.last_name, rp.grade
        FROM line_player lp JOIN roster_player rp ON rp.id = lp.roster_player_id
       WHERE lp.dual_line_id = ANY(${ids}) ORDER BY lp.side, lp.position
    `,
    sql`
      SELECT dual_line_id, set_number, home_games, away_games, tie_points
        FROM line_set WHERE dual_line_id = ANY(${ids}) ORDER BY set_number
    `,
  ]);

  const byLine = new Map(lines.map((l) => [Number(l.id), { ...l, homePlayers: [], awayPlayers: [], sets: [] }]));
  for (const p of people) {
    byLine.get(Number(p.dual_line_id))[`${p.side}Players`].push({
      id: Number(p.id), firstName: p.first_name, lastName: p.last_name, grade: p.grade,
    });
  }
  for (const s of sets) {
    byLine.get(Number(s.dual_line_id)).sets.push({
      number: s.set_number, homeGames: s.home_games,
      awayGames: s.away_games, tiePoints: s.tie_points,
    });
  }
  return { ...dual, lines: [...byLine.values()] };
}

async function teamSeason({ year, schoolId, genderId, isJv }) {
  const [team] = await db()`
    SELECT * FROM team_season
     WHERE year = ${year} AND school_id = ${schoolId}
       AND gender_id = ${genderId} AND is_jv = ${!!isJv}
  `;
  if (!team) throw new HttpError(404, `no ${year} team for school ${schoolId}`);
  return team;
}

/** Statements that write a whole card. Callers wrap them in one transaction. */
function cardStatements(dualId, lines, lineIds) {
  const sql = db();
  const out = [sql`DELETE FROM dual_line WHERE dual_id = ${dualId}`];
  lines.forEach((line, i) => {
    const lineId = lineIds[i];
    out.push(sql`
      INSERT INTO dual_line (id, dual_id, match_type, flight, home_won, finish)
      VALUES (${lineId}, ${dualId}, ${line.matchType}, ${Number(line.flight)},
              ${line.homeWon ?? null}, ${line.finish || null})
    `);
    for (const side of ['home', 'away']) {
      (line[`${side}Players`] || []).forEach((p, idx) => {
        out.push(sql`
          INSERT INTO line_player (dual_line_id, roster_player_id, side, position)
          VALUES (${lineId}, ${p.id}, ${side}, ${idx + 1})
        `);
      });
    }
    for (const s of line.sets || []) {
      out.push(sql`
        INSERT INTO line_set (dual_line_id, set_number, home_games, away_games, tie_points)
        VALUES (${lineId}, ${Number(s.number)}, ${Number(s.homeGames)},
                ${Number(s.awayGames)}, ${s.tiePoints ?? null})
      `);
    }
  });
  return out;
}

/**
 * Resolve every player on the card to a roster_player id.
 *
 * Away-side players usually do not exist yet: the away coach may not have signed
 * in. The home coach supplies names, they are created on the away team's roster,
 * and when that coach does sign in their roster is already half-built.
 */
async function resolvePlayers(lines, homeTeam, awayTeam, coachId) {
  for (const side of ['home', 'away']) {
    const team = side === 'home' ? homeTeam : awayTeam;
    const field = `${side}Players`;
    const needed = [];
    for (const line of lines) {
      for (const p of line[field] || []) {
        if (!p.id) needed.push(p);
      }
    }
    if (!needed.length) continue;
    const ids = await ensurePlayers(team.id, needed, coachId);
    needed.forEach((p, i) => { p.id = ids[i]; });
  }
}

// ---------------------------------------------------------------------------
// Handlers
// ---------------------------------------------------------------------------

async function createDual(req) {
  const coach = await requireCoach(req);
  const body = await readJson(req);
  const sql = db();

  const year = Number(body.year);
  const genderId = Number(body.genderId);
  const isJv = !!body.isJv;
  const homeSchoolId = Number(body.homeSchoolId);
  const awaySchoolId = Number(body.awaySchoolId);
  const playedOn = String(body.playedOn || '').slice(0, 10);

  if (!/^\d{4}-\d{2}-\d{2}$/.test(playedOn)) throw new HttpError(400, 'playedOn must be YYYY-MM-DD');
  // The date has to fall in the season it is filed under, or the dual compiles
  // into data/<year>/ carrying a date from a different season and the natural
  // key stops matching the scraped copy of the same match.
  if (!playedOn.startsWith(`${year}-`)) {
    throw new HttpError(400, `a ${year} dual cannot be dated ${playedOn}`);
  }
  if (homeSchoolId === awaySchoolId) throw new HttpError(400, 'a team cannot play itself');

  const homeTeam = await teamSeason({ year, schoolId: homeSchoolId, genderId, isJv });
  const awayTeam = await teamSeason({ year, schoolId: awaySchoolId, genderId, isJv });
  await requireClaim(coach, homeTeam.id);   // the home coach files

  const lines = body.lines || [];
  validateCard(lines);

  // The natural key mirrors dedupe_meets(), so a dual the other coach already
  // filed collides here rather than becoming a duplicate downstream.
  const [clash] = await sql`
    SELECT id, status FROM dual
     WHERE year = ${year} AND gender_id = ${genderId} AND is_jv = ${isJv}
       AND played_on = ${playedOn}
       AND least(home_school_id, away_school_id) = ${Math.min(homeSchoolId, awaySchoolId)}
       AND greatest(home_school_id, away_school_id) = ${Math.max(homeSchoolId, awaySchoolId)}
  `;
  if (clash) {
    return json({
      error: 'this dual has already been reported',
      dualId: Number(clash.id), status: clash.status,
    }, 409);
  }

  await resolvePlayers(lines, homeTeam, awayTeam, coach.id);

  const [dualId] = await nextIds('dual_id_seq', 1);
  const lineIds = await nextIds('dual_line_id_seq', lines.length);
  const status = body.draft ? 'draft' : 'reported';

  try {
    await tx([
      sql`
        INSERT INTO dual (id, year, gender_id, is_jv, played_on, home_school_id,
                          away_school_id, is_postseason, event_name, title, status,
                          reported_by, reported_at)
        VALUES (${dualId}, ${year}, ${genderId}, ${isJv}, ${playedOn}, ${homeSchoolId},
                ${awaySchoolId}, ${!!body.isPostseason}, ${body.eventName || null},
                ${`${awayTeam.school_name} at ${homeTeam.school_name}`}, ${status},
                ${coach.id}, ${status === 'draft' ? null : new Date().toISOString()})
      `,
      ...cardStatements(dualId, lines, lineIds),
      sql`
        INSERT INTO audit_log (actor_coach_id, entity, entity_id, action, after)
        VALUES (${coach.id}, 'dual', ${dualId}, 'create', ${JSON.stringify(body)}::jsonb)
      `,
    ]);
  } catch (err) {
    if (String(err.message || '').includes('dual_natural_key')) {
      throw new HttpError(409, 'this dual has already been reported');
    }
    throw err;
  }

  return json({ ok: true, dual: await loadDual(dualId) }, 201);
}

async function replaceCard(req, id) {
  const coach = await requireCoach(req);
  const body = await readJson(req);
  const sql = db();

  const dual = await loadDual(id);
  if (dual.status === 'void') throw new HttpError(409, 'this dual has been voided');

  const homeTeam = await teamSeason({
    year: dual.year, schoolId: Number(dual.home_school_id),
    genderId: dual.gender_id, isJv: dual.is_jv,
  });
  await requireClaim(coach, homeTeam.id);

  // Optimistic concurrency: the client sends the timestamp it loaded.
  if (body.updatedAt && new Date(body.updatedAt).getTime() !== new Date(dual.updated_at).getTime()) {
    return json({
      error: 'another coach changed this dual — reload before saving',
      updatedAt: dual.updated_at,
    }, 409);
  }

  const lines = body.lines || [];
  validateCard(lines);

  const awayTeam = await teamSeason({
    year: dual.year, schoolId: Number(dual.away_school_id),
    genderId: dual.gender_id, isJv: dual.is_jv,
  });
  await resolvePlayers(lines, homeTeam, awayTeam, coach.id);

  const lineIds = await nextIds('dual_line_id_seq', lines.length);
  // Editing after the away team confirmed drops it back to reported: their
  // confirmation was of a card that no longer exists.
  const status = body.draft ? 'draft' : 'reported';

  await tx([
    ...cardStatements(id, lines, lineIds),
    sql`
      UPDATE dual
         SET status = ${status}, updated_at = now(),
             confirmed_by = NULL, confirmed_at = NULL,
             reported_at = coalesce(reported_at, now())
       WHERE id = ${id}
    `,
    sql`
      INSERT INTO audit_log (actor_coach_id, entity, entity_id, action, before, after)
      VALUES (${coach.id}, 'dual', ${id}, 'update',
              ${JSON.stringify({ lines: dual.lines })}::jsonb,
              ${JSON.stringify({ lines })}::jsonb)
    `,
  ]);

  return json({ ok: true, dual: await loadDual(id) });
}

async function respond(req, id, action) {
  const coach = await requireCoach(req);
  const body = req.method === 'POST' ? await readJson(req).catch(() => ({})) : {};
  const sql = db();
  const dual = await loadDual(id);

  // Confirming and disputing are the AWAY team's call — the whole point is that
  // the two sides are independent.
  const awayTeam = await teamSeason({
    year: dual.year, schoolId: Number(dual.away_school_id),
    genderId: dual.gender_id, isJv: dual.is_jv,
  });
  await requireClaim(coach, awayTeam.id);

  if (dual.status === 'draft') throw new HttpError(409, 'this dual has not been filed yet');

  const next = action === 'confirm' ? 'confirmed' : 'contested';
  const note = action === 'dispute' ? String(body.note || '').slice(0, 2000) : null;
  if (action === 'dispute' && !note) {
    throw new HttpError(400, 'a dispute needs a note saying what is wrong');
  }

  await tx([
    sql`
      UPDATE dual
         SET status = ${next}, updated_at = now(),
             confirmed_by = ${action === 'confirm' ? coach.id : null},
             confirmed_at = ${action === 'confirm' ? new Date().toISOString() : null},
             dispute_note = ${note}
       WHERE id = ${id}
    `,
    sql`
      INSERT INTO audit_log (actor_coach_id, entity, entity_id, action, before, after)
      VALUES (${coach.id}, 'dual', ${id}, ${action},
              ${JSON.stringify({ status: dual.status })}::jsonb,
              ${JSON.stringify({ status: next, note })}::jsonb)
    `,
  ]);
  return json({ ok: true, status: next });
}

async function listDuals(req) {
  const url = new URL(req.url);
  const teamSeasonId = Number(url.searchParams.get('team'));
  if (!Number.isFinite(teamSeasonId)) throw new HttpError(400, 'team is required');
  const sql = db();

  const [team] = await sql`SELECT * FROM team_season WHERE id = ${teamSeasonId}`;
  if (!team) throw new HttpError(404, 'team not found');

  const rows = await sql`
    SELECT d.*,
           (d.home_school_id = ${team.school_id}) AS is_home,
           hs.school_name AS home_name, aws.school_name AS away_name,
           (SELECT count(*)::int FROM dual_line dl WHERE dl.dual_id = d.id) AS flight_count,
           (SELECT count(*)::int FROM dual_line dl
             WHERE dl.dual_id = d.id AND dl.home_won IS TRUE) AS home_flights,
           (SELECT count(*)::int FROM dual_line dl
             WHERE dl.dual_id = d.id AND dl.home_won IS FALSE) AS away_flights
      FROM dual d
      LEFT JOIN team_season hs ON hs.year = d.year AND hs.school_id = d.home_school_id
                              AND hs.gender_id = d.gender_id AND hs.is_jv = d.is_jv
      LEFT JOIN team_season aws ON aws.year = d.year AND aws.school_id = d.away_school_id
                              AND aws.gender_id = d.gender_id AND aws.is_jv = d.is_jv
     WHERE d.year = ${team.year} AND d.gender_id = ${team.gender_id}
       AND d.is_jv = ${team.is_jv}
       AND (d.home_school_id = ${team.school_id} OR d.away_school_id = ${team.school_id})
       AND d.status <> 'void'
     ORDER BY d.played_on DESC, d.id DESC
  `;
  // The away coach's inbox: filed, not yet answered by them.
  const awaiting = rows.filter((r) => !r.is_home && r.status === 'reported').map((r) => Number(r.id));
  return json({ team, duals: rows, awaitingYou: awaiting });
}

export default async function handler(req) {
  return route(async () => {
    const parts = segments(req, 'duals');
    if (parts[0] === '__ping') return json({ ok: true });

    if (!parts.length) {
      if (req.method === 'GET') return listDuals(req);
      if (req.method === 'POST') return createDual(req);
      throw new HttpError(405, 'method not allowed');
    }

    const id = Number(parts[0]);
    if (!Number.isFinite(id)) throw new HttpError(400, 'bad dual id');
    const action = parts[1];

    if (req.method === 'GET' && !action) {
      const dual = await loadDual(id);
      const coach = await currentCoach(req);
      return json({ dual, signedIn: !!coach });
    }
    if (req.method === 'PUT' && !action) return replaceCard(req, id);
    if (req.method === 'POST' && (action === 'confirm' || action === 'dispute')) {
      return respond(req, id, action);
    }

    if (req.method === 'POST' && action === 'resolve') {
      const admin = await requireAdmin(req);
      const body = await readJson(req);
      const status = String(body.status || '');
      if (!PUBLISHED.has(status) && status !== 'void') {
        throw new HttpError(400, 'status must be reported, confirmed, contested or void');
      }
      await db()`
        UPDATE dual SET status = ${status}, resolved_by = ${admin.id},
                        resolved_at = now(), updated_at = now()
         WHERE id = ${id}
      `;
      await db()`
        INSERT INTO audit_log (actor_coach_id, entity, entity_id, action, after)
        VALUES (${admin.id}, 'dual', ${id}, 'resolve', ${JSON.stringify({ status })}::jsonb)
      `;
      return json({ ok: true, status });
    }

    if (req.method === 'DELETE' && !action) {
      const admin = await requireAdmin(req);
      await db()`
        UPDATE dual SET status = 'void', resolved_by = ${admin.id},
                        resolved_at = now(), updated_at = now()
         WHERE id = ${id}
      `;
      return json({ ok: true });
    }

    throw new HttpError(405, 'method not allowed');
  });
}

// Both forms: the collection endpoint has no trailing segment, so a bare
// '/api/duals/*' would never match a list or a create.
export const config = { path: ['/api/duals', '/api/duals/*'] };
