-- Oregon HS Tennis — coach reporting store.
--
-- This is the write side of oregontennis.org. Coaches report duals here; the
-- compile step (compile_entered.py) renders what lands in these tables back
-- into TennisReporting meet shape under data/<year>/, which is what
-- generate_site.py already reads. Nothing in the ranking pipeline knows this
-- database exists.
--
-- Target: Neon serverless Postgres, reached over HTTP from the Netlify
-- functions in netlify/functions/. Apply with:
--     psql "$DATABASE_URL" -f db/schema.sql
-- The file is idempotent — every object is CREATE ... IF NOT EXISTS — so it
-- doubles as the migration path for additive changes.

BEGIN;

-- ---------------------------------------------------------------------------
-- Reserved ID ranges.
--
-- Compiled meets have to carry integer ids that can never collide with a real
-- TennisReporting id. Observed TR ids are six figures (schools ~74000-125000,
-- players ~140000-190000, meets ~220000, lines ~1560000), so we start our
-- sequences far above them and let the compile step use the primary keys
-- directly. compile_entered.py replaces every meet whose id sits in the
-- reserved meet range on each run, which is what makes compilation idempotent.
--
--   roster_player.id   900,000,000+   -> TR player id
--   dual.id            800,000,000+   -> TR meet id
--   dual_line.id       700,000,000+   -> TR match (line) id
--   matchTeam ids      600,000,000+   -> derived from dual_line.id, not stored
--
-- Keep these in sync with RESERVED_* in compile_entered.py.
-- ---------------------------------------------------------------------------


-- ---------------------------------------------------------------------------
-- People and permissions
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS coach (
    id            BIGSERIAL PRIMARY KEY,
    email         TEXT        NOT NULL,
    name          TEXT        NOT NULL DEFAULT '',
    phone         TEXT        NOT NULL DEFAULT '',
    is_admin      BOOLEAN     NOT NULL DEFAULT FALSE,
    -- Set when the row was seeded from a scraped coaches[] entry rather than
    -- created by a real sign-in. Lets an admin see who has actually shown up.
    seeded_from_scrape BOOLEAN NOT NULL DEFAULT FALSE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_login_at TIMESTAMPTZ
);

-- Email is the login identity, matched case-insensitively. Stored as typed so
-- mail to the coach looks right; compared lowered. (citext would be tidier but
-- an expression index needs no extension.)
CREATE UNIQUE INDEX IF NOT EXISTS coach_email_key ON coach (lower(email));


-- Single-use magic-link tokens. Only the SHA-256 hash is stored, so a database
-- read never yields a usable login link.
CREATE TABLE IF NOT EXISTS auth_token (
    token_hash  TEXT        PRIMARY KEY,
    coach_id    BIGINT      NOT NULL REFERENCES coach(id) ON DELETE CASCADE,
    expires_at  TIMESTAMPTZ NOT NULL,
    used_at     TIMESTAMPTZ,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- Coarse abuse signal for the request endpoint; not used for auth.
    request_ip  TEXT
);

CREATE INDEX IF NOT EXISTS auth_token_coach_idx ON auth_token (coach_id);
CREATE INDEX IF NOT EXISTS auth_token_expiry_idx ON auth_token (expires_at);


-- One row per team-season a coach can report for. Seeded from
-- master_school_list.csv; `entry_enabled` is the beta gate, flipped on per
-- league.
CREATE TABLE IF NOT EXISTS team_season (
    id             BIGSERIAL PRIMARY KEY,
    year           INTEGER  NOT NULL,
    school_id      BIGINT   NOT NULL,          -- TennisReporting school id
    gender_id      SMALLINT NOT NULL CHECK (gender_id IN (1, 2)),  -- 1 boys, 2 girls
    is_jv          BOOLEAN  NOT NULL DEFAULT FALSE,
    school_name    TEXT     NOT NULL DEFAULT '',
    league         TEXT     NOT NULL DEFAULT '',
    classification TEXT     NOT NULL DEFAULT '',
    entry_enabled  BOOLEAN  NOT NULL DEFAULT FALSE,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (year, school_id, gender_id, is_jv)
);

CREATE INDEX IF NOT EXISTS team_season_year_league_idx
    ON team_season (year, league);


CREATE TABLE IF NOT EXISTS team_claim (
    coach_id       BIGINT      NOT NULL REFERENCES coach(id) ON DELETE CASCADE,
    team_season_id BIGINT      NOT NULL REFERENCES team_season(id) ON DELETE CASCADE,
    role           TEXT        NOT NULL DEFAULT 'head'
                               CHECK (role IN ('head', 'assistant')),
    granted_by     BIGINT      REFERENCES coach(id),
    granted_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (coach_id, team_season_id)
);

CREATE INDEX IF NOT EXISTS team_claim_team_idx ON team_claim (team_season_id);


-- ---------------------------------------------------------------------------
-- Rosters
--
-- Entered players have no TennisReporting id, and player identity is what makes
-- the ladder, the position matrix and all-state work across matches. The
-- sequence therefore starts in the reserved player range so roster_player.id
-- can be used verbatim as the compiled TR player id.
-- ---------------------------------------------------------------------------

CREATE SEQUENCE IF NOT EXISTS roster_player_id_seq START WITH 900000000;

CREATE TABLE IF NOT EXISTS roster_player (
    id             BIGINT PRIMARY KEY DEFAULT nextval('roster_player_id_seq'),
    team_season_id BIGINT   NOT NULL REFERENCES team_season(id) ON DELETE CASCADE,
    first_name     TEXT     NOT NULL,
    last_name      TEXT     NOT NULL,
    grade          TEXT     NOT NULL DEFAULT '',
    -- Set when a coach links an entered player to the TR player the scrape
    -- already knows, so a mid-season switch to entry keeps one identity.
    tr_player_id   BIGINT,
    active         BOOLEAN  NOT NULL DEFAULT TRUE,
    created_by     BIGINT   REFERENCES coach(id),
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS roster_player_name_key
    ON roster_player (team_season_id, lower(first_name), lower(last_name));

CREATE INDEX IF NOT EXISTS roster_player_team_idx ON roster_player (team_season_id);


-- ---------------------------------------------------------------------------
-- Duals
--
-- The unique key deliberately mirrors dedupe_meets() in generate_site.py, which
-- collapses duplicate duals on (date, unordered school pair). Matching it here
-- means the database cannot hold two rows that the pipeline would merge, so a
-- second coach reporting the same dual hits a conflict we can turn into the
-- confirm/dispute flow instead of a duplicate.
--
-- Multi-team postseason events are one dual row per school pairing sharing an
-- event_name; that is the shape is_dual_match()/dedupe_meets() already expect.
-- ---------------------------------------------------------------------------

CREATE SEQUENCE IF NOT EXISTS dual_id_seq START WITH 800000000;

CREATE TABLE IF NOT EXISTS dual (
    id             BIGINT PRIMARY KEY DEFAULT nextval('dual_id_seq'),
    year           INTEGER  NOT NULL,
    gender_id      SMALLINT NOT NULL CHECK (gender_id IN (1, 2)),
    is_jv          BOOLEAN  NOT NULL DEFAULT FALSE,
    played_on      DATE     NOT NULL,
    home_school_id BIGINT   NOT NULL,
    away_school_id BIGINT   NOT NULL,
    is_postseason  BOOLEAN  NOT NULL DEFAULT FALSE,
    -- Whether the dual is in league play. Derived from the two schools today,
    -- but a coach can say so directly and leagues change year to year.
    conference     BOOLEAN,
    -- Where it was played. A dual is at the home team's site unless a
    -- tournament put both teams somewhere else.
    venue          TEXT     NOT NULL DEFAULT 'home'
                            CHECK (venue IN ('home', 'neutral')),
    -- What happened to the fixture, as against `status` below, which is where
    -- the REPORT is in the confirm cycle. A postponed or cancelled dual is a
    -- real row with no card.
    result_status  TEXT     NOT NULL DEFAULT 'completed'
                            CHECK (result_status IN ('completed', 'postponed', 'cancelled')),
    event_name     TEXT,
    title          TEXT     NOT NULL DEFAULT '',
    status         TEXT     NOT NULL DEFAULT 'draft'
                            CHECK (status IN ('draft', 'reported', 'confirmed',
                                              'contested', 'void')),
    reported_by    BIGINT   REFERENCES coach(id),
    reported_at    TIMESTAMPTZ,
    confirmed_by   BIGINT   REFERENCES coach(id),
    confirmed_at   TIMESTAMPTZ,
    dispute_note   TEXT,
    resolved_by    BIGINT   REFERENCES coach(id),
    resolved_at    TIMESTAMPTZ,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (home_school_id <> away_school_id)
);

CREATE UNIQUE INDEX IF NOT EXISTS dual_natural_key
    ON dual (year, gender_id, is_jv, played_on,
             least(home_school_id, away_school_id),
             greatest(home_school_id, away_school_id));

CREATE INDEX IF NOT EXISTS dual_home_idx ON dual (year, gender_id, home_school_id);
CREATE INDEX IF NOT EXISTS dual_away_idx ON dual (year, gender_id, away_school_id);
CREATE INDEX IF NOT EXISTS dual_status_idx ON dual (year, status);


CREATE SEQUENCE IF NOT EXISTS dual_line_id_seq START WITH 700000000;

CREATE TABLE IF NOT EXISTS dual_line (
    id         BIGINT PRIMARY KEY DEFAULT nextval('dual_line_id_seq'),
    dual_id    BIGINT   NOT NULL REFERENCES dual(id) ON DELETE CASCADE,
    match_type TEXT     NOT NULL CHECK (match_type IN ('Singles', 'Doubles')),
    -- Oregon's card is 4 singles + 4 doubles, and every league plays all eight.
    -- (The fourth flights are missing from the imported data because the
    -- TennisReporting API does not expose who played them — a feed limitation,
    -- not a format one.)
    flight     SMALLINT NOT NULL CHECK (flight BETWEEN 1 AND 4),
    home_won   BOOLEAN,
    -- How the flight ended:
    --   NULL       played out normally
    --   'retired'  a player quit mid-match; the other side wins whatever the
    --              score was when they stopped
    --   'default'  one team had nobody at that position; the side that fielded
    --              a player wins the point without playing
    -- A flight that was never contested at all is simply ABSENT — no row. That
    -- is not the same as a default: nobody wins it, and generate_site.py leaves
    -- it out of the flight denominator, which is what makes a short card score
    -- correctly. Coaches may agree to play a subset of the card, and teams
    -- short of players forfeit from the bottom up.
    finish     TEXT     CHECK (finish IS NULL OR finish IN ('retired', 'default')),
    -- A retirement and a default both have a winner; only a played flight can
    -- be left undecided (mid-entry).
    CHECK (finish IS NULL OR home_won IS NOT NULL),
    UNIQUE (dual_id, match_type, flight)
);

CREATE INDEX IF NOT EXISTS dual_line_dual_idx ON dual_line (dual_id);


CREATE TABLE IF NOT EXISTS line_player (
    dual_line_id     BIGINT   NOT NULL REFERENCES dual_line(id) ON DELETE CASCADE,
    roster_player_id BIGINT   NOT NULL REFERENCES roster_player(id),
    side             TEXT     NOT NULL CHECK (side IN ('home', 'away')),
    position         SMALLINT NOT NULL CHECK (position IN (1, 2)),
    PRIMARY KEY (dual_line_id, side, position)
);

CREATE INDEX IF NOT EXISTS line_player_player_idx ON line_player (roster_player_id);


CREATE TABLE IF NOT EXISTS line_set (
    dual_line_id BIGINT   NOT NULL REFERENCES dual_line(id) ON DELETE CASCADE,
    set_number   SMALLINT NOT NULL CHECK (set_number BETWEEN 1 AND 3),
    home_games   SMALLINT NOT NULL,
    away_games   SMALLINT NOT NULL,
    -- Losing side's tiebreak points, rendered in parens the way score_str() in
    -- build_lineup_data.py expects. NULL when the set had no tiebreak.
    tie_points   SMALLINT,
    PRIMARY KEY (dual_line_id, set_number)
);


-- ---------------------------------------------------------------------------
-- Audit
--
-- Every write that changes a published number is recorded. This is the answer
-- to "who put that score in" during seeding week, which is the week the whole
-- system will be judged on.
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS audit_log (
    id             BIGSERIAL PRIMARY KEY,
    actor_coach_id BIGINT REFERENCES coach(id),
    entity         TEXT   NOT NULL,   -- 'dual' | 'roster_player' | 'team_claim' | ...
    entity_id      BIGINT,
    action         TEXT   NOT NULL,   -- 'create' | 'update' | 'confirm' | 'dispute' | ...
    before         JSONB,
    after          JSONB,
    at             TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS audit_log_entity_idx ON audit_log (entity, entity_id, at DESC);
CREATE INDEX IF NOT EXISTS audit_log_actor_idx ON audit_log (actor_coach_id, at DESC);

COMMIT;
