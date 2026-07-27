#!/usr/bin/env python3
"""Fetch version data from all comparison sources.

Usage:
    python -m comparisons.fetch_all                      # fetch all sources
    python -m comparisons.fetch_all --sources arch       # fetch specific source
    python -m comparisons.fetch_all --sources repology --limit 500  # query top 500 via Repology
    python -m comparisons.fetch_all --list               # list available sources
"""

import argparse
import json
import sys

from comparisons.arch import ArchSource
from comparisons.freebsd import FreebsdSource
from comparisons.homebrew import HomebrewSource
from comparisons.pkgsrc import PkgsrcSource
from comparisons.repology import RepologySource
from comparisons import CACHE_DIR


BULK_SOURCES = [
    ArchSource(),
    FreebsdSource(),
    HomebrewSource(),
    PkgsrcSource(),
]

REPOLOGY = RepologySource()


def get_source(slug):
    """Get a comparison source by slug."""
    for s in BULK_SOURCES:
        if s.slug == slug:
            return s
    if slug == REPOLOGY.slug:
        return REPOLOGY
    return None


def main():
    parser = argparse.ArgumentParser(description="Fetch version data from comparison sources")
    parser.add_argument("--sources", nargs="*", help="Specific sources to fetch (default: all bulk sources)")
    parser.add_argument("--list", action="store_true", help="List available sources")
    parser.add_argument("--cache-dir", default=str(CACHE_DIR), help="Cache directory (default: ~/.cache/orphan/)")
    parser.add_argument("--limit", type=int, default=None, help="Limit Repology queries (default: all unmatched)")
    args = parser.parse_args()

    if args.list:
        print("Available sources (bulk download):")
        for source in BULK_SOURCES:
            print(f"  {source.slug:<12} {source.name}")
        print("Available sources (slow query):")
        print(f"  {REPOLOGY.slug:<12} {REPOLOGY.name}")
        return

    sources_to_fetch = []
    run_repology = False

    if args.sources:
        for s in args.sources:
            if s == "repology":
                run_repology = True
            else:
                src = get_source(s)
                if src:
                    sources_to_fetch.append(src)
                else:
                    print(f"Unknown source: {s}", file=sys.stderr)
                    sys.exit(1)
    else:
        sources_to_fetch = BULK_SOURCES
        run_repology = True

    # Fetch bulk sources
    for source in sources_to_fetch:
        print(f"\nFetching {source.name}...", flush=True)
        try:
            packages = source.fetch(cache_dir=args.cache_dir)
            print(f"  Done: {len(packages)} packages", flush=True)
        except Exception as e:
            print(f"  Error: {e}", file=sys.stderr, flush=True)
            continue

    # Fetch Repology incrementally
    if run_repology:
        print(f"\nFetching {REPOLOGY.name}...", flush=True)
        try:
            with open(CACHE_DIR / "packages_raw.json") as f:
                raw = json.load(f)
            REPOLOGY.fetch_incremental(
                raw["packages"],
                cache_dir=args.cache_dir,
                limit=args.limit,
                resume=True,
            )
        except FileNotFoundError:
            print("  No packages_raw.json found. Run fetch_data.py first.", file=sys.stderr)
        except Exception as e:
            print(f"  Error: {e}", file=sys.stderr, flush=True)


if __name__ == "__main__":
    main()
