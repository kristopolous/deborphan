# Fuzzy Matching Rules

## Core Principle

**Blank comparisons are REJECTS, not passes.** If we can't verify a match, we don't accept it.

## Acceptance Logic

1. **dist=0** (normalized names match exactly): auto-accept
2. **dist > 0**: BOTH Debian description AND Repology summary must be non-null. If either is missing → REJECT.
3. **dist > 1**: ALSO require homepage cross-check (Debian homepage must overlap with Repology project homepages).
4. **dist == 1 with both summaries**: ACCEPT — descriptions confirm the match.

Otherwise REJECT.

## Output Format

Every fuzzy match prints:

```
FUZZY ACCEPTED/REJECTED: '{debian_name}' -> '{repology_name}' (dist=N)
  Normalized: '{debian_norm}' vs '{repology_norm}'
  Debian summary: {description or (none)}
  Repology summary: {summary or (none)}
  Debian homepage: {stripped homepage}
  Other candidates: ...
```

Both summaries are ALWAYS shown. If either is `(none)`, that's visible and causes rejection.

## Data Sources

- **Debian descriptions**: Bulk download from `deb.debian.org/debian/dists/sid/{main,contrib,non-free,non-free-firmware}/source/Sources.xz`
- **Repology summaries**: From Repology API (`/api/v1/project/{name}`)
- **Repology homepages**: From `repology.org/project/{name}/information` (HTML parsed)
- **Debian homepages**: From UDD `sources.homepage`

## Provenance

- All Debian data from official mirrors (`deb.debian.org`, `udd-mirror.debian.net`)
- Repology queries hit `repology.org/api/v1/` with documented User-Agent
- Sources.xz fetch is part of `fetch_data.py` (pipeline step), not ad-hoc
- Source URLs and timestamps logged during fetch
