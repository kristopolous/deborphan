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

## CLI

`run.py` is the main entry point:

```bash
# Full pipeline (fetch + build)
.venv/bin/python run.py fetch

# Fetch only specific comparison sources
.venv/bin/python run.py fetch --sources arch
.venv/bin/python run.py fetch --sources arch homebrew

# Skip UDD, just refresh comparison sources
.venv/bin/python run.py fetch --no-udd

# Build final data/packages.json from cached data
.venv/bin/python run.py build

# Query Repology (re-entrant, sorted by popularity)
.venv/bin/python run.py repology --limit 500
.venv/bin/python run.py repology             # resume from last checkpoint

# List available sources
.venv/bin/python run.py list

# Generate sample data for testing
.venv/bin/python run.py sample

# Serve locally
.venv/bin/python run.py serve
.venv/bin/python run.py serve --port 3000
```

Requires `psql` (PostgreSQL client) for UDD fetch. The pipeline produces `data/packages.json` with all fields precomputed. Schema is documented in `schema.json`.

### Comparison Sources

The pipeline compares Debian versions against multiple external sources to find packages behind upstream:

| Source | Packages | Notes |
|--------|----------|-------|
| Arch Linux | ~15k | Tracks upstream closely |
| FreeBSD Ports | ~38k | BSD ports tree |
| Homebrew | ~8.5k | macOS package manager |
| pkgsrc | ~20k | NetBSD package collection |
| Repology | per-query | Aggregates nix, Void, Fedora rawhide, openSUSE Tumbleweed, Chimera, Alpine edge, Gentoo, Slackware, OpenBSD, etc. |

Bulk sources (Arch, FreeBSD, Homebrew, pkgsrc) are fetched via direct downloads. Repology is queried per-package (sorted by popularity) — re-entrant, so you can stop/resume:

```bash
.venv/bin/python run.py fetch --sources arch   # Arch only
.venv/bin/python run.py repology --limit 500   # Repology top 500
```

## How It Works

The pipeline compares Debian package versions against external sources (Arch, FreeBSD, Homebrew, pkgsrc, Repology) to compute a **version delta** — how many semver versions behind Debian is. This distinguishes packages that are genuinely neglected (behind upstream) from those that are simply old (upstream is also stagnant).

The comparison framework is extensible — see `comparisons/` directory to add new sources.

## Features

- Log-log scatter plot, one dot per source package
- X-axis: install count (how widely deployed)
- Y-axis: days since last upload, oldest open RC bug age, or **version delta** (how far behind upstream)
- Dot size: number of open RC bugs (bigger = more bugs)
- Quadrant dividers at the median (neglected, active, etc.)
- Hover tooltips showing installs, votes, version info, bugs, maintainer, VCS status
- Tooltip is interactive — click the tracker link inside it
- Click dot to open tracker.debian.org/pkg/{name} (or use tooltip link on mobile)
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
run.py                     CLI entry point (fetch, build, repology, serve, list, sample)
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
