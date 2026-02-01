# Oregon High School Tennis Rankings System

## Project Overview

A data-driven ranking and playoff simulation system for Oregon high school tennis, designed to solve real problems in how teams are evaluated and seeded for state competition.

---

## The Problem Space

Oregon high school tennis faces a challenge common to many sports: **how do you fairly rank teams that play in different leagues, different regions, and face vastly different competition?**

The existing system relies heavily on win-loss records and subjective committee decisions. This creates several issues:

- **Schedule strength is invisible.** A team going 10-2 against strong Portland-area competition looks worse on paper than a team going 14-0 in a weak rural league.
- **Roster depth doesn't factor in.** Tennis is unique—a team fields 7-8 positions (4 singles, 4 doubles). A team winning 6-1 every match demonstrates more depth than one scraping by 4-3, but both count as wins.
- **Playoff seeding is contentious.** Without objective metrics, bracket placement involves guesswork and politics.
- **Travel logistics are ignored.** A 16-team bracket using pure seeding might send a Pendleton team to Brookings (400+ miles) in round one when reasonable alternatives exist.

---

## System Design Philosophy

### 1. Transparent, Defensible Methodology

Every ranking decision can be traced back to match data. The system uses established statistical approaches (RPI-style strength of schedule) combined with sport-specific innovations (flight-weighted scoring). When stakeholders ask "why is Team A ranked above Team B?", there's always a concrete answer.

### 2. Serve the Actual Users

The primary users are coaches and athletic directors—people who understand tennis but aren't data scientists. Design decisions consistently prioritize usability:

- Display raw scores (0-3.95 FWS) that map to intuitive concepts ("we averaged 2.8 flight wins per match")
- Use normalized values internally for calculations, but don't expose that complexity
- Provide "what-if" tools (playoff simulator) so users can explore scenarios themselves
- Include head-to-head context directly in the interface

### 3. Handle Real-World Messiness

High school sports data is incomplete and inconsistent:
- Matches get rained out or forfeited
- Some teams play 8 flights, others play 6
- Dual meets sometimes end in ties
- Schools change classifications year-to-year
- City names in the source data have typos and variations

The system handles all of this gracefully rather than failing or producing misleading results.

---

## Technical Architecture

### Data Pipeline

```
OSAA API → Raw JSON → Normalization → Statistical Processing → Static Site
```

**Ingestion:** Fetches match-level data from the OSAA athletics API, handling pagination and rate limiting.

**Normalization:** Reconciles school identities across years, maps classifications and leagues, handles missing fields.

**Processing:** Calculates cascading statistics where each metric depends on others:
- Win Percentage → Opponent Win Percentage → Opponent's Opponent Win Percentage → APR
- Flight results → Weighted FWS → Normalized FWS → Power Index

**Output:** Generates a static HTML dashboard with embedded JSON data. No server required—hosts anywhere.

### The Ranking Algorithm

**Power Index = (APR × 0.50) + (Normalized FWS × 0.50)**

This balances two questions:
1. **APR (Adjusted Power Rating):** "How good are you at winning, accounting for who you played?"
2. **FWS (Flight-Weighted Score):** "How deep is your roster?"

**APR** uses the RPI formula common in college sports:
- 25% your win percentage
- 50% your opponents' win percentages
- 25% your opponents' opponents' win percentages

**FWS** weights each flight position:
- #1 Singles/Doubles: 1.0 points (your best players)
- #2 Singles: 0.75, #2 Doubles: 0.50
- #3 positions: 0.25 each
- #4 positions: 0.10 each

A team winning all 8 flights earns 3.95 points. But critically, **the denominator adjusts for matches with fewer flights**—a 6-flight match earning 3.0/3.0 rates the same as an 8-flight match earning 3.95/3.95.

### Head-to-Head Tiebreaker Logic

When teams are close in Power Index, direct competition matters. The system implements nuanced H2H logic:

- **Trigger conditions:** Teams within 2% PI difference, OR teams in the same league within 2 standings positions
- **Resolution:** H2H winner moves up, but only if it doesn't create circular conflicts (A beats B, B beats C, C beats A)
- **Split series:** If teams split their matches, the tiebreaker defers to other metrics
- **Match ties:** Uses FWS differential from the head-to-head match itself

### Geographic Optimization

The playoff bracket simulator includes a "Regional Mode" that optimizes travel while respecting competitive integrity:

- **Protected Tier (Seeds 1-4):** Pure seeding preserved—top teams earned their placement
- **Flex Tier (Seeds 5-12):** Matchups optimized for geographic proximity, avoiding same-district pairings
- **Anchor Tier (Seeds 13-16):** Placed by proximity to their likely round-two opponents

Distance calculations use real coordinates via OpenStreetMap geocoding, not estimates.

---

## Key Engineering Decisions

### Why Static Site Generation?

- **Zero infrastructure cost.** Hosts on GitHub Pages, Netlify, or any static host.
- **No security surface.** No database, no auth, no API to protect.
- **Offline-capable.** Coaches can save the page and use it without connectivity.
- **Fast.** All interactivity happens client-side with pre-processed data.

### Why Embedded JSON Instead of API Calls?

The dataset is small enough (1,200 team-seasons) that embedding it directly in the page makes sense. This eliminates latency, simplifies deployment, and makes the system self-contained.

### Why Cache Geocoding Results?

OpenStreetMap's Nominatim API is free but rate-limited. Caching results means:
- First build geocodes unknown cities (slowly, respectfully)
- Subsequent builds use cached coordinates (instantly)
- The cache ships with the repo, so fresh clones don't need API access

### Why Not Use an Existing Sports Analytics Platform?

High school sports have unique constraints:
- No budget for commercial tools
- Data access is limited and non-standard
- Stakeholders need education, not just dashboards
- The ranking methodology itself is part of the value

---

## Impact and Stakeholder Value

### For Coaches
- Objective measure of team strength beyond win-loss
- Understand where they stand in the state, not just their league
- Simulate playoff scenarios before the bracket is set
- Identify strength-of-schedule opportunities

### For Athletic Directors
- Data to support playoff seeding decisions
- Reduce controversy around bracket placement
- Historical tracking across seasons

### For OSAA (Potential)
- Model for modernizing playoff selection
- Travel optimization could save thousands of miles across classifications
- Transparent methodology reduces appeals and complaints

---

## What This Project Demonstrates

1. **Domain Modeling:** Translating messy real-world rules (tennis scoring, OSAA classifications, tiebreaker hierarchies) into clean data structures.

2. **Algorithm Design:** Building ranking systems that balance multiple factors fairly, handle edge cases, and produce defensible results.

3. **Systems Thinking:** Understanding how components interact—data quality affects rankings, rankings affect tiebreakers, tiebreakers affect user trust.

4. **User Empathy:** Building for non-technical users without dumbing down the capability.

5. **Pragmatic Engineering:** Choosing boring technology (static HTML, embedded JSON) when it's the right fit, rather than over-engineering.

6. **Data Pipeline Design:** Handling the full lifecycle from external API to processed output, with appropriate caching and error handling.

---

## Future Directions

- **Multi-sport expansion:** The ranking methodology generalizes to other dual-meet sports (wrestling, swimming)
- **Predictive modeling:** Use historical data to forecast match outcomes
- **Mobile app:** Native experience for coaches checking rankings at tournaments
- **Official OSAA integration:** Work toward adoption as an official ranking tool

---

## Repository Structure

```
or-tennis-data/
├── generate_site.py      # Main processing and site generation
├── master_school_list.csv # School metadata (classification, league)
├── geocode_cache.json    # Cached city coordinates
├── data/                 # Raw JSON from OSAA API, by year
├── public/               # Generated static assets
├── docs/                 # Documentation and methodology
└── index.html            # Generated dashboard
```
