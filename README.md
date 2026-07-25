# Debian Neglect Explorer

An interactive D3 scatter plot that maps Debian source packages by install count vs. staleness, with version-comparison data from Arch Linux, FreeBSD Ports, Homebrew, pkgsrc, and Repology to identify packages genuinely behind upstream.

## Quick Start

```bash
# Set up environment
python3 -m venv .venv
.venv/bin/pip install -e .

# Generate sample data for testing
python3 generate_sample_data.py

# Serve locally
python3 -m http.server 8080

# Open http://localhost:8080
```

## Fetching Real Data

Requires `psql` (PostgreSQL client) to query the UDD mirror:

```bash
# 1. Fetch Debian data from UDD
.venv/bin/python fetch_data.py

# 2. Fetch version data from comparison sources (Arch, Homebrew)
.venv/bin/python -m comparisons.fetch_all

# 3. Merge and precompute final dataset
.venv/bin/python build.py
```

This produces `data/packages.json` with all fields precomputed. The output schema is documented in `schema.json`.

### Comparison Sources

The pipeline compares Debian versions against multiple external sources to find packages behind upstream:

| Source | Packages | Notes |
|--------|----------|-------|
| Arch Linux | ~15k | Tracks upstream closely |
| FreeBSD Ports | ~38k | BSD ports tree |
| Homebrew | ~8.5k | macOS package manager |
| pkgsrc | ~20k | NetBSD package collection |
| Repology | per-query | Aggregates nix, Void, Fedora rawhide, openSUSE Tumbleweed, Chimera, Alpine, Gentoo, etc. |

Bulk sources (Arch, FreeBSD, Homebrew, pkgsrc) are fetched via direct downloads. Repology is queried per-package (sorted by popularity) — re-entrant, so you can stop/resume:

```bash
# Query top 500 most popular packages
.venv/bin/python -m comparisons.repology --limit 500

# Resume from where you left off (default)
.venv/bin/python -m comparisons.repology
```

Run `python -m comparisons.fetch_all --list` to see all available sources.

To fetch only specific sources:
```bash
.venv/bin/python -m comparisons.fetch_all --sources arch homebrew
```

## How It Works

The pipeline compares Debian package versions against external sources (Arch Linux, Homebrew) to compute a **version delta** — how many semver versions behind Debian is. This distinguishes packages that are genuinely neglected (behind upstream) from those that are simply old (upstream is also stagnant).

The comparison framework is extensible — see `comparisons/` directory to add new sources.

## Features

- Log-log scatter plot, one dot per source package
- X-axis: install count (how widely deployed)
- Y-axis: days since last upload, oldest open RC bug age, or **version delta** (how far behind upstream)
- Dot size: number of open RC bugs (bigger = more bugs)
- Quadrant dividers at the median (neglected, active, etc.)
- Hover tooltips showing installs, votes, version info, bugs, maintainer, VCS status
- Click any dot to open tracker.debian.org/pkg/{name}
- Y-axis toggle: three metrics available
- Hide zero-bug packages (on by default)
- Min installs slider to filter low-deployment packages
- Dot size multiplier slider
- Search with regex support (try `^alsa$`, `alac|7zip`, etc.)
- Search finds packages across all data regardless of filters
- Source package names resolve to binary names (e.g. rust-alacritty shows as alacritty)
- Scroll-wheel zoom and drag-to-pan, axes extend beyond data range
- Shift+drag brush-select to filter the package list
- Sidebar lists matching packages with install/staleness stats
- Dark theme (GitHub-dark style)

## Files

```
index.html                 Single-page D3 scatter plot (HTML + CSS + JS)
fetch_data.py              Queries UDD via psql -> data/packages_raw.json
build.py                   Merges data -> data/packages.json
comparisons/               Version comparison framework
  __init__.py                Shared utilities + base class
  arch.py                    Arch Linux source
  freebsd.py                 FreeBSD Ports source
  homebrew.py                Homebrew source
  pkgsrc.py                  pkgsrc (NetBSD) source
  repology.py                Repology (re-entrant per-query)
  fetch_all.py               Fetch from all sources
generate_sample_data.py    Generates fake data for development
schema.json                Output schema for data/packages.json
pyproject.toml             Python project config
data/packages.json         Generated data (git-ignored)
```

## License

GPL-3.0, see [LICENSE](LICENSE).
