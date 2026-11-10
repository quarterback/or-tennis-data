// Reordering a team ladder. Pure; used by lineups.html, tested by
// tests/functions/ladder-order.test.mjs.
//
// Every move INSERTS: the player lands at the new position and everyone in
// between slides one place. (The ladder used to SWAP, so moving No. 1 down to
// No. 3 sent No. 3 up to No. 1 — never what a coach means.)

// Move `pid` so it ends up at 0-based `index`. Returns a new array.
export function moveTo(order, pid, index) {
  const from = order.indexOf(pid);
  if (from < 0) return order.slice();
  const out = order.slice();
  out.splice(from, 1);
  const to = Math.max(0, Math.min(out.length, index));
  out.splice(to, 0, pid);
  return out;
}

const norm = (s) => String(s || '').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '')
  .replace(/[^a-z0-9 ]+/g, ' ').replace(/\s+/g, ' ').trim();

// Read a typed or pasted ladder: one player per line, top to bottom.
// Each line may be a full name, a last name, a first name, or the start of a
// name, as long as it points at ONE player on the roster. Leading numbering
// ("1.", "#2", "3)") and trailing notes after a tab or " - " are ignored.
//   players: [{ pid, name }]
// Returns { order, unmatched, ambiguous, repeated, leftOver }:
//   order     pids in the typed order, then everyone not typed, in `fallback` order
//   unmatched lines that name nobody on the roster
//   ambiguous lines that could be more than one player, with who they could be
//   repeated  lines that name a player already placed by an earlier line
//   leftOver  pids nobody typed (appended to the bottom of `order`)
export function parseOrder(text, players, fallback = players.map((p) => p.pid)) {
  const lines = String(text || '').split(/\r?\n/)
    .map((l) => l.replace(/^\s*(#?\d+[.):\-]?\s+)/, '').split(/\t| - /)[0].trim())
    .filter(Boolean);
  const roster = players.map((p) => ({ pid: p.pid, name: p.name, n: norm(p.name), parts: norm(p.name).split(' ') }));
  const placed = [], unmatched = [], ambiguous = [], repeated = [];
  const used = new Set();
  for (const line of lines) {
    const q = norm(line);
    if (!q) continue;
    let hits = roster.filter((r) => r.n === q);
    if (!hits.length) hits = roster.filter((r) => r.parts.includes(q));
    if (!hits.length) hits = roster.filter((r) => r.n.startsWith(q) || r.parts.some((w) => w.startsWith(q)));
    // Several matches but only one not yet placed: that is who they mean.
    if (hits.length > 1) {
      const free = hits.filter((r) => !used.has(r.pid));
      if (free.length === 1) hits = free;
    }
    if (!hits.length) { unmatched.push(line); continue; }
    if (hits.length > 1) { ambiguous.push({ line, could: hits.map((h) => h.name) }); continue; }
    const pid = hits[0].pid;
    if (used.has(pid)) { repeated.push(line); continue; }
    used.add(pid); placed.push(pid);
  }
  const leftOver = fallback.filter((pid) => !used.has(pid));
  return { order: [...placed, ...leftOver], unmatched, ambiguous, repeated, leftOver };
}
