"""Arch Linux version comparison source."""

import io
import json
import re
import tarfile
import urllib.request

from comparisons import ComparisonSource, CACHE_DIR


REPOS = [
    "https://mirror.rackspace.com/archlinux/core/os/x86_64/core.db.tar.gz",
    "https://mirror.rackspace.com/archlinux/extra/os/x86_64/extra.db.tar.gz",
]


def fetch_repo(url):
    """Download and parse an Arch repo database, returning {name: version}."""
    print(f"  Fetching {url}...", flush=True)
    req = urllib.request.Request(url, headers={"User-Agent": "debian-neglect-explorer/1.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = resp.read()

    packages = {}
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tf:
        for member in tf.getmembers():
            if member.name.endswith("/desc"):
                f = tf.extractfile(member)
                if f:
                    lines = f.read().decode("utf-8", errors="replace").splitlines()
                    name = None
                    version = None
                    for i, line in enumerate(lines):
                        if line == "%NAME%":
                            name = lines[i + 1].strip() if i + 1 < len(lines) else None
                        elif line == "%VERSION%":
                            version = lines[i + 1].strip() if i + 1 < len(lines) else None
                    if name and version:
                        packages[name] = version
    return packages


class ArchSource(ComparisonSource):
    name = "Arch Linux"
    slug = "arch"

    def fetch(self, cache_dir=None):
        cache_dir = cache_dir or CACHE_DIR
        all_packages = {}
        for url in REPOS:
            repo_packages = fetch_repo(url)
            print(f"    {len(repo_packages)} packages", flush=True)
            all_packages.update(repo_packages)

        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_path = f"{cache_dir}/arch_versions.json"
        with open(cache_path, "w") as f:
            json.dump({"arch_packages": all_packages}, f, separators=(",", ":"))

        print(f"  Total: {len(all_packages)} packages", flush=True)
        return all_packages

    def load_cache(self, cache_dir=None):
        cache_dir = cache_dir or CACHE_DIR
        try:
            with open(f"{cache_dir}/arch_versions.json") as f:
                return json.load(f).get("arch_packages", {})
        except FileNotFoundError:
            return {}

    def normalize_name(self, name):
        return name

    def match_candidates(self, debian_source_name):
        return [
            debian_source_name,
            debian_source_name.replace("-", ""),
        ]

    def parse_upstream(self, version_str):
        """Extract upstream version from an Arch version string.

        Arch format: upstreamversion-packagingrevision
        """
        if not version_str:
            return None
        v = version_str
        v = re.sub(r"\.arch\d+", "", v)
        v = re.sub(r"-[\d]+$", "", v)
        return v
