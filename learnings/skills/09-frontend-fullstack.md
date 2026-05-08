# 09 — Frontend / Full-Stack Reach

**One-line:** A TypeScript React app, a Python static-site generator, a
GitHub-as-CDN data layer, and a pipeline that produces the artifact both
consume.

---

## Two renderers, one data artifact

The system has two ways of rendering rankings, both reading from the
same source data:

1. **The Python static-site generator** (`generate_site.py`). Produces a
   single ~3.4 MB `index.html` with embedded JSON, DataTables/Bootstrap
   UI, and inline CSS+JS. Used in production at oregontennis.org.

2. **The React/TypeScript app** (`src/`). Used for local dev and a
   parallel rendering path. Reads `master_school_list.csv` + per-year
   JSON files from GitHub raw URLs.

The data is the contract. Both renderers compute the same APR formula
(`(WWP × 0.35) + (OWP × 0.65)` in `src/rankingCalculator.ts:79`,
`generate_site.py` constants block).

## Typed domain model

`src/types.ts` (60 lines):

```typescript
School, SchoolData, SchoolStats, SchoolRanking, FLIGHT_WEIGHTS
```

Every cross-module value is typed. `FLIGHT_WEIGHTS` is exported as a
typed constant matching the Python flight-weight table.

## GitHub-as-CDN data layer

`src/dataFetcher.ts`:

```typescript
const csvUrl = `https://raw.githubusercontent.com/${GITHUB_FULL_REPO}/main/master_school_list.csv`;
```

No backend, no auth, no rate-limit handling beyond what the API gives
you. The static-site model makes that fine. `Promise.all` for
parallel fetches:

```typescript
const schoolDataPromises = jsonFiles.map((file: any) =>
  fetchJsonFile(`${yearPath}/${file.name}`)
);
const results = await Promise.all(schoolDataPromises);
```

## React app structure

`src/App.tsx`:

- `useState` for year, classification, rankings, loading, error.
- `useEffect` chained on year change to refetch.
- Filter selectors + `RankingsTable` component.
- Visible legend explaining APR formula and flight weights.

It's small (125 lines) but it's idiomatic — the right hooks, dependency
arrays included, loading and error states modeled.

## Inline static-site generation

`generate_html()` in `generate_site.py:1935+`. A 2,300-line f-string
template with embedded JSON, inline CSS, inline JS (DataTables config,
playoff simulator logic, head-to-head tooltip rendering).

This is unfashionable but well-suited: the data-as-page model means
"first load shows full UI" with no hydration round-trip. For a static
site that updates a few times a day, that's the right tradeoff.

## Build tooling

`vite.config.ts`, `tsconfig.json`, `package.json`. Vite for dev and
build. `npm run dev` / `npm run build` per the README.

## Resume bullets specific to this skill

- *Built a TypeScript/React frontend (`Vite` + DataTables) consuming a
  versioned JSON artifact published by a Python pipeline, with
  cross-language verification of the rating formula in both implementations.*
- *Designed a GitHub-as-CDN data layer (raw URLs + contents API) for a
  zero-backend static site, with `Promise.all` parallel fetches and
  typed domain models in TypeScript.*
- *Authored a Python static-site generator producing a self-contained
  3.4 MB HTML page with embedded JSON and inline UI, eliminating
  hydration round-trips for a static daily-update use case.*

## Where to grow

- Reconcile the two renderers — pick one as canonical, retire the other
  or repurpose it. Right now the React app and the Python-generated
  HTML drift independently.
- Replace f-string HTML with Jinja2. Eliminates a class of escaping
  bugs and makes UI changes reviewable.
- Consider Astro or similar islands frameworks if you want dynamic
  features without rehydration cost.
- Add basic Lighthouse / a11y testing — the inline UI is feature-rich
  but probably has a11y debt.
