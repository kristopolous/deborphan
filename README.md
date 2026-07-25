# Debian Neglect Explorer

An interactive D3 scatter plot that maps Debian source packages by install count vs. staleness (days since upload, RC bug age), with drill-down links to tracker.debian.org.

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

- Log-log scatter plot, one dot per source package
- X-axis: install count (how widely deployed)
- Y-axis: days since last upload or oldest open RC bug age
- Dot size: number of open RC bugs (bigger = more bugs)
- Quadrant dividers at the median (neglected, active, etc.)
- Hover tooltips showing installs, votes, days since upload, bugs, maintainer, VCS status
- Click any dot to open tracker.debian.org/pkg/{name}
- Y-axis toggle: days since upload or oldest RC bug age
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
fetch_data.py              Queries UDD via psql and dumps JSON
generate_sample_data.py    Generates fake data for development
data/packages.json         Generated data (git-ignored)
```

## License

GPL-3.0, see [LICENSE](LICENSE).
