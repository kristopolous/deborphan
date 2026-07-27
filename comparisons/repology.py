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
import re
import sys
import time
import urllib.request
from urllib.parse import quote

from comparisons import ComparisonSource

API_URL = "https://repology.org/api/v1/project/{name}"
SEARCH_URL = "https://repology.org/api/v1/projects/?search={name}"

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


def _levenshtein(s1, s2):
    """Levenshtein distance between two strings."""
    if len(s1) < len(s2):
        return _levenshtein(s2, s1)
    if len(s2) == 0:
        return len(s1)
    prev_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        curr_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = prev_row[j + 1] + 1
            deletions = curr_row[j] + 1
            substitutions = prev_row[j] + (c1 != c2)
            curr_row.append(min(insertions, deletions, substitutions))
        prev_row = curr_row
    return prev_row[-1]


# Repology prefixes to strip before comparison
REPOLOGY_PREFIXES = ("r:", "python:", "python3:", "ruby:", "perl:", "c:", "java:", "perl6:")


def _normalize_repology_name(name):
    """Strip Repology prefixes and trailing numbers for comparison."""
    n = name.lower()
    for prefix in REPOLOGY_PREFIXES:
        if n.startswith(prefix):
            n = n[len(prefix):]
            break
    # Strip trailing version-like numbers: vecmath1.2 -> vecmath
    n = re.sub(r"\d+(\.\d+)*$", "", n)
    return n


def _strip_homepage(url):
    """Normalize a homepage URL for comparison: strip protocol, www., trailing slash."""
    if not url:
        return ""
    u = url.lower().strip()
    u = u.replace("https://", "").replace("http://", "")
    u = u.replace("www.", "")
    u = u.rstrip("/")
    return u


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
        """Query Repology for a single project by exact name.

        Returns the best version string from fast repos, or None.
        """
        url = API_URL.format(name=name)
        req = urllib.request.Request(url, headers={"User-Agent": "debian-neglect-explorer/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read())
        except (urllib.error.HTTPError, urllib.error.URLError, json.JSONDecodeError, TimeoutError):
            return None

        return self._pick_best_version(data)

    def _search_fuzzy(self, name, homepage=None):
        """Search Repology for fuzzy name matches, cross-check with summary.

        Returns (version, project_name) or (None, None).
        Prints match details for manual review.
        """
        url = SEARCH_URL.format(name=quote(name))
        req = urllib.request.Request(url, headers={"User-Agent": "debian-neglect-explorer/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read())
        except (urllib.error.HTTPError, urllib.error.URLError, json.JSONDecodeError, TimeoutError):
            return None, None

        name_norm = _normalize_repology_name(name)

        # data is {project_name: [packages...]}
        candidates = []
        for project_name, packages in data.items():
            version = self._pick_best_version(packages)
            if not version:
                continue
            proj_norm = _normalize_repology_name(project_name)

            # If normalized names match exactly, auto-accept
            if name_norm == proj_norm:
                candidates.insert(0, (0, project_name, version))
                continue

            dist = _levenshtein(name_norm, proj_norm)
            candidates.append((dist, project_name, version))

        if not candidates:
            return None, None

        # Sort by Levenshtein distance (exact normalized matches first)
        candidates.sort(key=lambda c: c[0])

        best_dist, best_name, best_version = candidates[0]

        # Get summary from best match
        summary = ""
        for entry in data.get(best_name, []):
            if entry.get("version") == best_version:
                summary = entry.get("summary", "")
                break

        # Acceptance logic:
        # - normalized names match exactly: auto-accept
        # - dist <= 2: auto-accept
        # - dist > 2: reject
        if best_dist == 0 or best_dist <= 2:
            accepted = True
        else:
            accepted = False

        tag = "ACCEPTED" if accepted else "REJECTED"
        print(f"    FUZZY {tag}: '{name}' -> '{best_name}' (dist={best_dist})")
        print(f"      Normalized: '{name_norm}' vs '{_normalize_repology_name(best_name)}'")
        print(f"      Repology summary: {summary}")
        if len(candidates) > 1:
            others = ", ".join(f"'{c[1]}' (d={c[0]})" for c in candidates[:3])
            print(f"      Other candidates: {others}")

        if not accepted:
            return None, None
        return best_version, best_name

    def _pick_best_version(self, packages):
        """Pick the best version from a list of Repology package entries."""
        for entry in packages:
            repo = entry.get("repo", "")
            if repo not in FAST_REPOS:
                continue
            status = entry.get("status", "")
            version = entry.get("version", "")
            if not version or status == "rolling":
                continue
            if status == "newest":
                return version
        # No newest found, try outdated
        for entry in packages:
            repo = entry.get("repo", "")
            if repo not in FAST_REPOS:
                continue
            status = entry.get("status", "")
            version = entry.get("version", "")
            if not version or status == "rolling":
                continue
            if status == "outdated":
                return version
        return None

    def fetch_incremental(self, packages_raw, cache_dir="data", limit=None, resume=True, check_none=False):
        """Query Repology for packages not yet cached, sorted by popularity.

        Args:
            packages_raw: list of package dicts from packages_raw.json
            cache_dir: where to cache results
            limit: max number of packages to query this run (None = all)
            resume: if True, skip packages already in cache
            check_none: if True, try fuzzy search for packages that returned None
        """
        cache = self.load_cache(cache_dir) if resume else {}
        already_cached = set(cache.keys())

        # Build homepage lookup
        homepages = {p["source"]: p.get("homepage") for p in packages_raw}

        # Sort by installs descending (most popular first)
        sorted_pkgs = sorted(packages_raw, key=lambda p: -(p.get("insts") or 0))

        # Filter to unmatched only
        to_query = [p for p in sorted_pkgs if p["source"] not in already_cached]

        # If check_none, also re-query None entries
        if check_none:
            none_entries = [p for p in sorted_pkgs if p["source"] in already_cached and cache.get(p["source"]) is None]
            to_query = to_query + none_entries
            print(f"  Re-checking {len(none_entries)} None entries with fuzzy search", flush=True)

        if limit:
            to_query = to_query[:limit]

        print(f"  Cache has {len(already_cached)} packages", flush=True)
        print(f"  Querying {len(to_query)} new packages from Repology...", flush=True)

        queried = 0
        found = 0
        fuzzy = 0
        errors = 0

        for i, pkg in enumerate(to_query):
            name = pkg["source"]
            homepage = homepages.get(name)

            # Try exact name first
            version = self._query_project(name)
            matched_name = name if version else None

            # Fuzzy fallback only if --check-none
            if not version and check_none:
                version, matched_name = self._search_fuzzy(name, homepage)
                if version:
                    fuzzy += 1

            queried += 1

            # Cache result (version or None)
            cache[name] = {"version": version, "matched": matched_name} if version else None
            if version:
                found += 1

            if (i + 1) % 50 == 0:
                # Save incrementally every 50 queries
                self._save_cache(cache, cache_dir)
                print(f"    {i + 1}/{len(to_query)} queried, {found} found, {fuzzy} fuzzy, {errors} errors", flush=True)

            # Rate limit: ~1 req/sec (search endpoint is heavier)
            time.sleep(1.0)

        # Final save
        self._save_cache(cache, cache_dir)
        print(f"  Done: {queried} queried, {found} found, {fuzzy} fuzzy, {len(cache)} total cached", flush=True)

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

    def compare(self, debian_source_name, debian_version, packages_dict):
        """Override to handle both old (string) and new (dict) cache formats."""
        from comparisons import parse_debian_upstream, compute_version_delta
        upstream = parse_debian_upstream(debian_version)
        if not upstream:
            return None

        entry = packages_dict.get(debian_source_name)
        if not entry:
            # Try normalized names
            for candidate in self.match_candidates(debian_source_name):
                entry = packages_dict.get(candidate)
                if entry:
                    break

        if not entry:
            return None

        # Handle old format (string) and new format (dict)
        if isinstance(entry, str):
            other_version = entry
            matched_name = debian_source_name
        else:
            other_version = entry.get("version")
            matched_name = entry.get("matched", debian_source_name)

        if not other_version:
            return None

        delta = compute_version_delta(upstream, other_version)
        return {
            f"{self.slug}_version": other_version,
            f"{self.slug}_upstream_version": self.parse_upstream(other_version),
            f"{self.slug}_matched": matched_name,
            "behind_upstream": delta is not None,
            "version_delta": delta,
        }

    def parse_upstream(self, version_str):
        return version_str


def main():
    parser = argparse.ArgumentParser(description="Query Repology for package versions (re-entrant)")
    parser.add_argument("--limit", type=int, default=None, help="Max packages to query this run")
    parser.add_argument("--no-resume", action="store_true", help="Clear cache and start fresh")
    parser.add_argument("--check-none", action="store_true", help="Try fuzzy search for packages that returned None")
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
        check_none=args.check_none,
    )


if __name__ == "__main__":
    main()
