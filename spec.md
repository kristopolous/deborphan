## PRD: Debian Package Neglect Explorer

**Problem**
Popularity and maintenance activity are tracked separately across Debian's infrastructure (popcon, BTS, snapshot.debian.org, salsa/vcswatch). There's no single view that surfaces packages which are widely used but under-attended — the highest-risk category for the ecosystem.

**Goal**
An interactive scatter plot that plots popularity against activity/staleness per source package, letting a user visually identify the "popular but neglected" quadrant and drill into individual packages.

**Data source**
UDD (Ultimate Debian Database), public read-only Postgres mirror at `udd-mirror.debian.net`. Single query joins `packages`, `popcon`, `upload_history`, `all_bugs` (see prior SQL sketch for shape — table/column names should be confirmed against live schema at build time, they drift).

**Metrics**

- X-axis (popularity): `popcon.vote`, log scale. Optional secondary weighting by reverse-dependency count for infra packages underrepresented by popcon.
- Y-axis (staleness): primary = `days_since_last_upload`. Secondary/tooltip fields: `oldest_open_RC_bug_age`, `rc_bug_count`, `vcswatch` commits-since-last-upload (to distinguish "no releases but actively developed" from "true silence").
- Combined score: rank-based ratio (`popularity_rank / activity_recency_rank`), not weighted sum — raw scales differ too much to blend meaningfully. Score used for sort/threshold, not necessarily shown as an axis.

**Core interactions**

1. Log-log scatter, one point per source package.
2. Quadrant divider lines (median or configurable threshold on each axis).
3. Hover: package name, popcon vote, days since upload, RC bug count, link to BTS/salsa.
4. Click: opens package detail (or external link to tracker.debian.org page).
5. Filter/brush: drag-select a region → live list of matching packages below/beside plot.
6. Sort/toggle: switch y-axis between "days since upload" and "oldest RC bug age" without re-fetching data.
7. Exclude toggle for `open_bug_count == 0` packages (healthy-quiet, not neglected) — on by default, user can turn off.

**Non-goals**
- Not attempting to score "quality" of maintenance, only presence/absence of recent signal.
- Not real-time — daily-refresh data (matches UDD's own update cadence) is fine.
- No auth/write-back to Debian infra; read-only exploration tool.

**Tech**
D3 (direct, not Plotly) for the scatter + brush interaction, given need for linked filtering and quadrant-line rendering control. Data pulled from UDD via a backend query (script/cron dumping to static JSON is enough for v1 — no need for live DB connection per page load).

**Open questions**
- Threshold values for quadrant lines: fixed cutoffs vs. median-of-dataset (latter self-adjusts as Debian's overall activity baseline shifts).
- Whether "abandoned" list should be scoped to a section (e.g. only packages you maintain, or a specific team) vs. archive-wide — archive-wide is ~30k source packages, worth confirming render/perf budget before committing to no virtualization.
