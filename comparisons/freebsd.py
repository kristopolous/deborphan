"""FreeBSD Ports version comparison source."""

import json
import re
import urllib.request

from comparisons import ComparisonSource


INDEX_URL = "https://download.FreeBSD.org/ports/index/INDEX-14"


class FreebsdSource(ComparisonSource):
    name = "FreeBSD Ports"
    slug = "freebsd"

    def fetch(self, cache_dir="data"):
        print(f"  Fetching {INDEX_URL}...", flush=True)
        req = urllib.request.Request(INDEX_URL, headers={"User-Agent": "debian-neglect-explorer/1.0"})
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = resp.read().decode("utf-8", errors="replace")

        packages = {}
        for line in data.splitlines():
            if not line.strip():
                continue
            # Format: portname-version|/path|/usr/local|description|...
            parts = line.split("|")
            if not parts:
                continue
            name_version = parts[0]
            # Split last -N from name (port version suffixes like _1, ,1)
            # FreeBSD uses name-version where version can have commas: jq-1.8.2, portname-1.0_1
            # The version part starts after the last hyphen followed by a digit
            m = re.match(r"^(.+)-(\d[^-]*)$", name_version)
            if m:
                name = m.group(1)
                version = m.group(2)
                # Normalize: strip trailing _N (port revision) and ,N (subpackages)
                version = re.sub(r"_\d+$", "", version)
                version = re.sub(r",\d+$", "", version)
                packages[name] = version

        cache_path = f"{cache_dir}/freebsd_versions.json"
        with open(cache_path, "w") as f:
            json.dump({"freebsd_packages": packages}, f, separators=(",", ":"))

        print(f"  Total: {len(packages)} packages", flush=True)
        return packages

    def load_cache(self, cache_dir="data"):
        try:
            with open(f"{cache_dir}/freebsd_versions.json") as f:
                return json.load(f).get("freebsd_packages", {})
        except FileNotFoundError:
            return {}

    def normalize_name(self, name):
        return name.lower()

    def match_candidates(self, debian_source_name):
        """FreeBSD uses similar naming to upstream, try common conventions."""
        return [
            debian_source_name,
            debian_source_name.replace("-", ""),
            debian_source_name.replace("-", "_"),
        ]

    def parse_upstream(self, version_str):
        """FreeBSD versions are upstream versions with port revisions stripped."""
        return version_str
