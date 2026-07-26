# Debian Neglect Explorer

An interactive D3 scatter plot that maps Debian source packages by install count vs. staleness, with version-comparison data from Arch Linux, FreeBSD Ports, Homebrew, pkgsrc, and Repology. Includes a maintainer burden view to identify over-encumbered teams and individuals.

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

The pipeline compares Debian package versions against external sources (Arch, FreeBSD, Homebrew, pkgsrc, Repology) to compute a **version delta** — how many semver versions behind Debian is. The formula is `(other_major - deb_major)*100 + (other_minor - deb_minor)*10 + (other_patch - deb_patch)`. Date-based versions (major > 1900) are excluded. The best (largest) delta across all sources is kept per package.

The **Maintainer Burden** view aggregates packages by maintainer email, computing average version delta and total RC bugs. Teams are identified by name matching (`/^Debian|Team$/`).

The comparison framework is extensible — see `comparisons/` directory to add new sources.

## Features

### Package View
- Log-log scatter plot, one dot per source package
- X-axis: install count (popcon)
- Y-axis: days since last upload, oldest open RC bug age, or **version delta** (how far behind upstream)
- Dot size: number of open RC bugs (bigger = more bugs)
- Quadrant dividers at the median (neglected, active, etc.)
- Click dot to open tracker.debian.org/pkg/{name}
- Hide zero-bug packages (on by default)
- Dot size multiplier slider

### Maintainer Burden View
- X-axis: number of packages maintained
- Y-axis: average version delta vs upstream (best of all comparison sources)
- Shape: triangles = Debian teams, circles = individuals
- Size: total open RC bugs across all packages
- Quadrant split at median: overburdened = many packages + far behind upstream
- Click to open qa.debian.org/developer page

### Common
- Hover tooltips with details
- Search with regex support (try `^alsa$`, `alac|7zip`, etc.)
- Search finds packages across all data regardless of filters
- Source package names resolve to binary names (e.g. rust-alacritty shows as alacritty)
- Scroll-wheel zoom and drag-to-pan, axes extend beyond data range
- Shift+drag brush-select to filter the package list
- Sidebar lists matching packages/maintainers
- Dark theme (GitHub-dark style)
- Dynamic guide with view-specific axis/size documentation

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
