"""Homebrew version comparison source."""

import json
import re
import urllib.request

from comparisons import ComparisonSource, CACHE_DIR


FORMULAE_URL = "https://formulae.brew.sh/api/formula.json"


class HomebrewSource(ComparisonSource):
    name = "Homebrew"
    slug = "homebrew"

    def fetch(self, cache_dir=None):
        cache_dir = cache_dir or CACHE_DIR
        print(f"  Fetching {FORMULAE_URL}...", flush=True)
        req = urllib.request.Request(FORMULAE_URL, headers={"User-Agent": "debian-neglect-explorer/1.0"})
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read())

        packages = {}
        for formula in data:
            name = formula.get("name")
            version = formula.get("versions", {}).get("stable")
            if name and version:
                packages[name] = version

        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_path = f"{cache_dir}/homebrew_versions.json"
        with open(cache_path, "w") as f:
            json.dump({"homebrew_packages": packages}, f, separators=(",", ":"))

        print(f"  Total: {len(packages)} packages", flush=True)
        return packages

    def load_cache(self, cache_dir=None):
        cache_dir = cache_dir or CACHE_DIR
        try:
            with open(f"{cache_dir}/homebrew_versions.json") as f:
                return json.load(f).get("homebrew_packages", {})
        except FileNotFoundError:
            return {}

    def normalize_name(self, name):
        return name.lower()

    def match_candidates(self, debian_source_name):
        """Homebrew uses upstream names directly, so try common conventions."""
        return [
            debian_source_name,
            debian_source_name.replace("-", ""),
            debian_source_name.replace("-", "_"),
        ]

    def parse_upstream(self, version_str):
        """Homebrew versions are already upstream versions."""
        return version_str
