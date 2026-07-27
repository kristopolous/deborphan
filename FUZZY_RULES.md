# Fuzzy Matching Rules

## Core Principle

**Blank comparisons are REJECTS, not passes.** If we can't verify a match, we don't accept it.

## Acceptance Logic

A fuzzy match is ACCEPTED only if ALL of:

1. **dist=0** (normalized names match exactly): auto-accept
2. **dist=1 AND one name is a prefix of the other** (e.g. `lme` → `lme4`, `c-lolcat` → `lolcat`): auto-accept
3. **dist > 1**: ALL of the following must pass:
   - Debian homepage exists AND overlaps with Repology project homepages
   - BOTH Debian description AND Repology summary are non-null
   - Homepages match (fetched from `repology.org/project/{name}/information`)

Otherwise REJECT.

## What Gets Printed

Every fuzzy match prints:

```
FUZZY ACCEPTED/REJECTED: '{debian_name}' -> '{repology_name}' (dist=N)
  Normalized: '{debian_norm}' vs '{repology_norm}'
  Debian summary: {description or (none)}
  Repology summary: {summary or (none)}
  Debian homepage: {stripped homepage}
  Other candidates: ...
```

Both summaries are ALWAYS shown. If either is `(none)`, that's visible in the output and causes rejection for dist > 1.

## Data Sources

- **Debian descriptions**: Bulk download from `deb.debian.org/debian/dists/sid/{main,contrib,non-free,non-free-firmware}/source/Sources.xz`. Fetched once during `fetch_data.py`, stored in `data/packages_raw.json` as `description` field.
- **Repology summaries**: From Repology API response entries (`/api/v1/project/{name}`).
- **Repology homepages**: From Repology project information page (`/api/v1/project/{name}/information`), parsed from HTML "Homepage links" section.
- **Debian homepages**: From UDD `sources.homepage` column.

## Provenance

- All Debian data comes from official Debian mirrors (`deb.debian.org`, `udd-mirror.debian.net`)
- Repology queries hit `repology.org/api/v1/` with documented User-Agent
- The Sources.xz fetch is part of `fetch_data.py` (documented pipeline step), not ad-hoc
- Source URLs and timestamps are logged during fetch
