# Debian Package Neglect Explorer

An interactive scatter plot that visualizes Debian source packages by popularity (popcon votes) vs. maintenance activity (days since last upload), helping identify packages that are widely used but under-attended.

## Quick Start

```bash
# Generate sample data for testing
python3 generate_sample_data.py

# Serve locally
python3 -m http.server 8080

# Open http://localhost:8080
```

## Fetching Real Data

Requires `psql` (PostgreSQL client) to query the UDD mirror:

```bash
python3 fetch_data.py
```

This connects to `udd-mirror.debian.net` and writes `data/packages.json`.

## Features

- **Log-log scatter plot** — one point per source package
- **Quadrant dividers** — median-based lines split popular/neglected/active quadrants
- **Hover tooltips** — popcon vote, days since upload, RC bug count, maintainer, links
- **Click through** — opens package on tracker.debian.org
- **Brush selection** — drag-select a region to filter the package list
- **Y-axis toggle** — switch between "days since upload" and "oldest RC bug age"
- **Zero-bug filter** — hide packages with no open bugs (on by default)
- **Min vote slider** — filter out low-popularity packages

## Files

```
index.html                 # Single-page D3 scatter plot app
fetch_data.py              # Python script to query UDD and dump JSON
generate_sample_data.py    # Generates fake data for development
data/packages.json         # Generated data (git-ignored)
```

## License

GPL-3.0 — see [LICENSE](LICENSE).
