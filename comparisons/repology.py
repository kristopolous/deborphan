#!/usr/bin/env python3
"""Repology version comparison source.

Queries per-project API. Slow (~2s/query) so runs as a re-entrant background task.
Populates data/repology_versions.json incrementally, sorted by popularity.

Usage:
    python -m comparisons.repology                   # query all unmatched, most popular first
    python -m comparisons.repology --limit 500       # query top 500 only
    python -m comparisons.repology --resume           # skip already-queried packages
"""

import argparse
import json
import sys
import time
import urllib.request

from comparisons import ComparisonSource

API_URL = "https://repology.org/api/v1/project/{name}"

# Repos that track upstream closely (rolling release or very fast updates)
FAST_REPOS = {
    "nix_unstable",
    "void_x86_64",
    "arch",
    "fedora_rawhide",
    "opensuse_tumbleweed",
    "chimera",
    "alpine_edge",
    "alpine_edge",
    "gentoo",
    "slackware_current",
    "slackware64_current",
    "openbsd",
    "parabola",
    "manjaro_unstable",
}


class RepologySource(ComparisonSource):
    name = "Repology"
    slug = "repology"

    def fetch(self, cache_dir="data"):
        """Not used directly — use fetch_incremental instead."""
        return self.load_cache(cache_dir)

    def load_cache(self, cache_dir="data"):
        try:
            with open(f"{cache_dir}/repology_versions.json") as f:
                return json.load(f).get("repology_packages", {})
        except FileNotFoundError:
            return {}

    def _query_project(self, name):
        """Query Repology for a single project.

        Returns the best version string from fast repos, or None if:
        - Package not found on Repology (404)
        - All matching versions have status "rolling" (immutable snapshots, not tracked)
        - Network error / timeout

        None results are cached to avoid re-querying on resume.
        """
        url = API_URL.format(name=name)
        req = urllib.request.Request(url, headers={"User-Agent": "debian-neglect-explorer/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read())
        except (urllib.error.HTTPError, urllib.error.URLError, json.JSONDecodeError, TimeoutError):
            return None

        best_version = None
        best_status = None
        for entry in data:
            repo = entry.get("repo", "")
            if repo not in FAST_REPOS:
                continue
            status = entry.get("status", "")
            version = entry.get("version", "")
            if not version or status == "rolling":
                continue
            if status == "newest":
                return version  # Found newest, no need to keep looking
            if status == "outdated" and best_version is None:
                best_version = version
                best_status = status

        return best_version

    def fetch_incremental(self, packages_raw, cache_dir="data", limit=None, resume=True):
        """Query Repology for packages not yet cached, sorted by popularity.

        Args:
            packages_raw: list of package dicts from packages_raw.json
            cache_dir: where to cache results
            limit: max number of packages to query this run (None = all)
            resume: if True, skip packages already in cache
        """
        cache = self.load_cache(cache_dir) if resume else {}
        already_cached = set(cache.keys())

        # Sort by installs descending (most popular first)
        sorted_pkgs = sorted(packages_raw, key=lambda p: -(p.get("insts") or 0))

        # Filter to unmatched only
        to_query = [p for p in sorted_pkgs if p["source"] not in already_cached]

        if limit:
            to_query = to_query[:limit]

        print(f"  Cache has {len(already_cached)} packages", flush=True)
        print(f"  Querying {len(to_query)} new packages from Repology...", flush=True)

        queried = 0
        found = 0
        errors = 0

        for i, pkg in enumerate(to_query):
            name = pkg["source"]
            version = self._query_project(name)
            queried += 1

            cache[name] = version  # cache None too (negative cache)
            if version:
                found += 1

            if (i + 1) % 50 == 0:
                # Save incrementally every 50 queries
                self._save_cache(cache, cache_dir)
                print(f"    {i + 1}/{len(to_query)} queried, {found} found, {errors} errors", flush=True)

            # Rate limit: ~2 req/sec
            time.sleep(0.5)

        # Final save
        self._save_cache(cache, cache_dir)
        print(f"  Done: {queried} queried, {found} found, {len(cache)} total cached", flush=True)

        return cache

    def _save_cache(self, cache, cache_dir):
        path = f"{cache_dir}/repology_versions.json"
        with open(path, "w") as f:
            json.dump({"repology_packages": cache}, f, separators=(",", ":"))

    def normalize_name(self, name):
        return name.lower()

    def match_candidates(self, debian_source_name):
        return [
            debian_source_name,
            debian_source_name.replace("-", ""),
            debian_source_name.replace("-", "_"),
        ]

    def parse_upstream(self, version_str):
        return version_str


def main():
    parser = argparse.ArgumentParser(description="Query Repology for package versions (re-entrant)")
    parser.add_argument("--limit", type=int, default=None, help="Max packages to query this run")
    parser.add_argument("--no-resume", action="store_true", help="Clear cache and start fresh")
    parser.add_argument("--cache-dir", default="data", help="Cache directory")
    args = parser.parse_args()

    with open(f"{args.cache_dir}/packages_raw.json") as f:
        raw = json.load(f)

    source = RepologySource()
    source.fetch_incremental(
        raw["packages"],
        cache_dir=args.cache_dir,
        limit=args.limit,
        resume=not args.no_resume,
    )


if __name__ == "__main__":
    main()
