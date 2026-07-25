# Debian Neglect Explorer

An interactive D3 scatter plot that maps Debian source packages by install count vs. staleness, with version-comparison data from Arch Linux to identify packages genuinely behind upstream.

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

# 2. Fetch Arch Linux package database
.venv/bin/python fetch_arch.py

# 3. Merge and precompute final dataset
.venv/bin/python build.py
```

This produces `data/packages.json` with all fields precomputed. The output schema is documented in `schema.json`.

## How It Works

The pipeline compares Debian package versions against Arch Linux (which tracks upstream closely) to compute a **version delta** — how many semver versions behind Debian is. This distinguishes packages that are genuinely neglected (behind upstream) from those that are simply old (upstream is also stagnant).

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
fetch_arch.py              Downloads Arch DB -> data/arch_versions.json
build.py                   Merges both -> data/packages.json
generate_sample_data.py    Generates fake data for development
schema.json                Output schema for data/packages.json
pyproject.toml             Python project config
data/packages.json         Generated data (git-ignored)
```

## License

GPL-3.0, see [LICENSE](LICENSE).
