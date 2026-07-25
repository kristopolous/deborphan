#!/usr/bin/env python3
"""Merge UDD data with Arch version comparison into a single precomputed JSON.

Usage:
    python3 fetch_data.py          # fetch UDD data -> data/packages_raw.json
    python3 fetch_arch.py          # fetch Arch DB   -> data/arch_versions.json
    python3 build.py               # merge + precompute -> data/packages.json

The output schema is documented in schema.json.
"""

import json
import re
import sys
from datetime import datetime, timezone


def parse_debian_upstream(version_str):
    """Extract upstream version from a Debian version string."""
    if not version_str:
        return None
    v = version_str
    if ":" in v:
        v = v.split(":", 1)[1]
    v = re.sub(r"-[\d.]+$", "", v)
    v = re.sub(r"\+.*$", "", v)
    v = re.sub(r"~.*$", "", v)
    return v


def parse_arch_upstream(version_str):
    """Extract upstream version from an Arch version string."""
    if not version_str:
        return None
    v = version_str
    v = re.sub(r"\.arch\d+", "", v)
    v = re.sub(r"-[\d]+$", "", v)
    return v


def normalize_version(v):
    v = v.strip()
    v = re.sub(r"^v", "", v)
    return v


def version_to_tuple(v):
    parts = []
    for part in re.split(r"[.\-]", v):
        try:
            parts.append((0, int(part)))
        except ValueError:
            parts.append((1, part))
    return parts


def parse_semver(v):
    """Extract (major, minor, patch) as ints from a version string.

    Non-numeric components are treated as 0.
    Missing components default to 0.
    """
    v = normalize_version(v)
    # Split on dots and hyphens, keep only numeric parts
    nums = []
    for part in re.split(r"[.\-]", v):
        try:
            nums.append(int(part))
        except ValueError:
            break  # stop at first non-numeric (e.g. "rc1", "beta")
    while len(nums) < 3:
        nums.append(0)
    return tuple(nums[:3])


def version_delta(debian_upstream, arch_upstream):
    """Compute how far behind Debian is from Arch as a single number.

    Uses weighted semver distance: major*100 + minor*10 + patch.
    Returns None if versions can't be compared.
    """
    if not debian_upstream or not arch_upstream:
        return None
    try:
        d = parse_semver(debian_upstream)
        a = parse_semver(arch_upstream)
    except (ValueError, TypeError):
        return None
    # Only return positive deltas (Arch newer)
    if a <= d:
        return None
    return (a[0] - d[0]) * 100 + (a[1] - d[1]) * 10 + (a[2] - d[2])


def compare_versions(debian_upstream, arch_upstream):
    """Returns True if Arch is newer, False if same/Debian-newer, None if incomparable."""
    if not debian_upstream or not arch_upstream:
        return None
    d = normalize_version(debian_upstream)
    a = normalize_version(arch_upstream)
    if d == a:
        return False
    try:
        d_tuple = version_to_tuple(d)
        a_tuple = version_to_tuple(a)
        return a_tuple > d_tuple
    except TypeError:
        return None


def build():
    with open("data/packages_raw.json") as f:
        raw = json.load(f)

    try:
        with open("data/arch_versions.json") as f:
            arch_data = json.load(f)
        arch_packages = arch_data.get("arch_packages", {})
    except FileNotFoundError:
        print("No arch_versions.json found, skipping Arch comparison.", file=sys.stderr)
        arch_packages = {}

    packages = []
    stats = {"behind": 0, "same": 0, "not_found": 0, "debian_newer": 0}

    for pkg in raw["packages"]:
        source = pkg["source"]
        debian_version = pkg.get("last_upload_version") or ""
        debian_upstream = parse_debian_upstream(debian_version) if debian_version else None

        # Find Arch version
        arch_version = None
        if arch_packages:
            for candidate in [source, source.replace("-", "")]:
                if candidate in arch_packages:
                    arch_version = arch_packages[candidate]
                    break

        arch_upstream = parse_arch_upstream(arch_version) if arch_version else None
        behind = compare_versions(debian_upstream, arch_upstream) if debian_upstream and arch_upstream else None

        if behind is True:
            stats["behind"] += 1
        elif behind is False:
            if arch_upstream and debian_upstream and normalize_version(arch_upstream) != normalize_version(debian_upstream):
                stats["debian_newer"] += 1
            else:
                stats["same"] += 1
        else:
            stats["not_found"] += 1

        entry = {
            "source": source,
            "display_name": pkg.get("display_name") or source,
            "insts": pkg.get("insts", 0),
            "vote": pkg.get("vote", 0),
            "days_since_upload": pkg.get("days_since_upload"),
            "last_upload_date": pkg.get("last_upload_date"),
            "last_upload_version": debian_version or None,
            "debian_upstream_version": debian_upstream,
            "rc_bug_count": pkg.get("rc_bug_count", 0),
            "oldest_rc_bug_age": pkg.get("oldest_rc_bug_age"),
            "maintainer": pkg.get("maintainer"),
            "vcs_status": pkg.get("vcs_status"),
            "vcs_url": pkg.get("vcs_url"),
            "arch_version": arch_version,
            "arch_upstream_version": arch_upstream,
            "behind_upstream": behind,
        }
        packages.append(entry)

    output = {
        "fetched_at": raw.get("fetched_at", datetime.now(timezone.utc).isoformat()),
        "package_count": len(packages),
        "packages": packages,
    }

    with open("data/packages.json", "w") as f:
        json.dump(output, f, separators=(",", ":"))

    print(f"Wrote {len(packages)} packages to data/packages.json", file=sys.stderr)
    print(f"  Behind upstream: {stats['behind']}", file=sys.stderr)
    print(f"  Same version:    {stats['same']}", file=sys.stderr)
    print(f"  Debian newer:    {stats['debian_newer']}", file=sys.stderr)
    print(f"  Not on Arch:     {stats['not_found']}", file=sys.stderr)


if __name__ == "__main__":
    build()
