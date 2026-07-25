#!/usr/bin/env python3
"""Fetch version data from all comparison sources.

Usage:
    python -m comparisons.fetch_all              # fetch all sources
    python -m comparisons.fetch_all --sources arch  # fetch specific source
    python -m comparisons.fetch_all --list       # list available sources
"""

import argparse
import sys

from comparisons.arch import ArchSource
from comparisons.freebsd import FreebsdSource
from comparisons.homebrew import HomebrewSource


SOURCES = [
    ArchSource(),
    FreebsdSource(),
    HomebrewSource(),
]


def get_source(slug):
    """Get a comparison source by slug."""
    for source in SOURCES:
        if source.slug == slug:
            return source
    return None


def main():
    parser = argparse.ArgumentParser(description="Fetch version data from comparison sources")
    parser.add_argument("--sources", nargs="*", help="Specific sources to fetch (default: all)")
    parser.add_argument("--list", action="store_true", help="List available sources")
    parser.add_argument("--cache-dir", default="data", help="Cache directory (default: data)")
    args = parser.parse_args()

    if args.list:
        print("Available sources:")
        for source in SOURCES:
            print(f"  {source.slug:<12} {source.name}")
        return

    if args.sources:
        sources = [get_source(s) for s in args.sources]
        sources = [s for s in sources if s is not None]
        if not sources:
            print(f"No matching sources found. Available: {', '.join(s.slug for s in SOURCES)}", file=sys.stderr)
            sys.exit(1)
    else:
        sources = SOURCES

    for source in sources:
        print(f"\nFetching {source.name}...", flush=True)
        try:
            packages = source.fetch(cache_dir=args.cache_dir)
            print(f"  Done: {len(packages)} packages", flush=True)
        except Exception as e:
            print(f"  Error: {e}", file=sys.stderr, flush=True)
            continue


if __name__ == "__main__":
    main()
