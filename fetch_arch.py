#!/usr/bin/env python3
"""Download Arch Linux package databases and extract package versions."""

import io
import tarfile
import json
import sys
import urllib.request

REPOS = [
    "https://mirror.rackspace.com/archlinux/core/os/x86_64/core.db.tar.gz",
    "https://mirror.rackspace.com/archlinux/extra/os/x86_64/extra.db.tar.gz",
]


def fetch_repo(url):
    """Download and parse an Arch repo database, returning {name: version}."""
    print(f"Fetching {url}...", file=sys.stderr)
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


def main():
    all_packages = {}
    for url in REPOS:
        repo_packages = fetch_repo(url)
        print(f"  {len(repo_packages)} packages", file=sys.stderr)
        all_packages.update(repo_packages)

    print(f"Total: {len(all_packages)} packages", file=sys.stderr)

    output = {
        "arch_packages": all_packages,
        "repo_count": len(REPOS),
    }

    with open("data/arch_versions.json", "w") as f:
        json.dump(output, f, separators=(",", ":"))

    print("Wrote data/arch_versions.json", file=sys.stderr)


if __name__ == "__main__":
    main()
