"""pkgsrc (NetBSD) version comparison source."""

import json
import re
import urllib.request

from comparisons import ComparisonSource


INDEX_URL = "https://ftp.NetBSD.org/pub/pkgsrc/current/pkgsrc/index-all.html"


class PkgsrcSource(ComparisonSource):
    name = "pkgsrc"
    slug = "pkgsrc"

    def fetch(self, cache_dir="data"):
        print(f"  Fetching {INDEX_URL}...", flush=True)
        req = urllib.request.Request(INDEX_URL, headers={"User-Agent": "debian-neglect-explorer/1.0"})
        with urllib.request.urlopen(req, timeout=120) as resp:
            html = resp.read().decode("utf-8", errors="replace")

        matches = re.findall(r'<a href="[^"]+/index\.html">([^<]+)</a>', html)
        packages = {}
        for m in matches:
            p = re.match(r"^(.+?)-(\d[^<]*)$", m)
            if p:
                name = p.group(1)
                ver = p.group(2)
                # Strip pkgsrc revision suffix (nbN)
                ver = re.sub(r"nb\d+$", "", ver)
                packages[name] = ver

        cache_path = f"{cache_dir}/pkgsrc_versions.json"
        with open(cache_path, "w") as f:
            json.dump({"pkgsrc_packages": packages}, f, separators=(",", ":"))

        print(f"  Total: {len(packages)} packages", flush=True)
        return packages

    def load_cache(self, cache_dir="data"):
        try:
            with open(f"{cache_dir}/pkgsrc_versions.json") as f:
                return json.load(f).get("pkgsrc_packages", {})
        except FileNotFoundError:
            return {}

    def normalize_name(self, name):
        return name.lower()

    def match_candidates(self, debian_source_name):
        return [
            debian_source_name,
            debian_source_name.replace("-", ""),
            debian_source_name.replace("-", "_"),
        ]

    def parse_upstream(self, version_str):
        """pkgsrc versions are upstream versions with nbN revision stripped."""
        return version_str
