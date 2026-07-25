#!/usr/bin/env python3
"""Merge UDD data with Arch version comparison into a single precomputed JSON.

Usage:
    python fetch_data.py          # fetch UDD data -> data/packages_raw.json
    python fetch_arch.py          # fetch Arch DB   -> data/arch_versions.json
    python build.py               # merge + precompute -> data/packages.json

The output schema is documented in schema.json.
"""

import json
import re
import sys
from datetime import datetime, timezone

from semver import Version


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


def to_semver(version_str):
    """Try to parse a version string into a semver.Version.

    Handles versions that aren't strictly semver:
    - Strips leading 'v'
    - Strips leading zeros from numeric components (07 -> 7)
    - Pads missing components (1.0 -> 1.0.0)
    - Strips pre-release/build noise that semver can't handle
    """
    if not version_str:
        return None
    v = version_str.strip()
    v = re.sub(r"^v", "", v)
    # Strip leading zeros from numeric components (e.g. 6.07 -> 6.7)
    def strip_leading_zero(m):
        s = m.group(0)
        if len(s) > 1 and s.startswith("0"):
            return str(int(s))
        return s
    v = re.sub(r"\b0+(\d+)\b", strip_leading_zero, v)
    # Try strict parse first
    try:
        return Version.parse(v)
    except ValueError:
        pass
    # Try padding to 3 components
    parts = v.split(".")
    if len(parts) == 1:
        v = f"{v}.0.0"
    elif len(parts) == 2:
        v = f"{v}.0"
    try:
        return Version.parse(v)
    except ValueError:
        pass
    # Strip pre-release suffixes like -rc1, -beta, .dev1
    v = re.sub(r"[-.](rc|alpha|beta|dev|pre|post)\d*$", "", v, flags=re.IGNORECASE)
    # Strip trailing non-semver parts
    v = re.sub(r"[^+\-0-9.].*$", "", v)
    # Re-pad
    parts = v.split(".")
    if len(parts) == 2:
        v = f"{v}.0"
    try:
        return Version.parse(v)
    except ValueError:
        return None


def version_delta(debian_upstream, arch_upstream):
    """Compute how far behind Debian is from Arch as a single number.

    Uses semver major/minor/patch distance, weighted: major*100 + minor*10 + patch.
    Returns None if versions can't be compared, Arch is not newer, or versions
    look like dates (which shouldn't be compared as semver).
    """
    d = to_semver(debian_upstream)
    a = to_semver(arch_upstream)
    if not d or not a:
        return None
    if a <= d:
        return None
    # Filter out date-based versions (e.g. 20250320, 20260707.1)
    if d.major > 1900 or a.major > 1900:
        return None
    return (a.major - d.major) * 100 + (a.minor - d.minor) * 10 + (a.patch - d.patch)


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
        delta = version_delta(debian_upstream, arch_upstream)

        behind = delta is not None
        if behind:
            stats["behind"] += 1
        elif arch_upstream and debian_upstream:
            try:
                d = to_semver(debian_upstream)
                a = to_semver(arch_upstream)
                if d and a and d > a:
                    stats["debian_newer"] += 1
                else:
                    stats["same"] += 1
            except Exception:
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
            "version_delta": delta,
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
