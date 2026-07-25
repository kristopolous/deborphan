#!/usr/bin/env python3
"""Compare Debian package versions against Arch Linux to find packages behind upstream."""

import json
import re
import sys


def parse_debian_upstream(version_str):
    """Extract the upstream version from a Debian version string.

    Debian format: [epoch:]upstream[-debian_revision]
    Also strips +dfsg, ~git1234567, etc.

    Examples:
        "6.07-2"            -> "6.07"
        "1:1.3.4-1"         -> "1.3.4"
        "1.2.2+dfsg1-6"     -> "1.2.2"
        "1:5.3.2.1+dfsg-2"  -> "5.3.2.1"
        "0.32.15-1.1"       -> "0.32.15"
        "2.4-5"             -> "2.4"
        "7:8.1.2-2"         -> "8.1.2"
        "3.3.1-1"           -> "3.3.1"
        "1.14-1~exp2"       -> "1.14"
        "1:1.3.dfsg+really1.3.2-3" -> "1.3.2"
    """
    v = version_str
    # Strip epoch
    if ":" in v:
        v = v.split(":", 1)[1]
    # Strip Debian revision (last -NNN or -N.N or -N.N.N)
    v = re.sub(r"-[\d.]+$", "", v)
    # Strip +dfsg, +dfsg1, +really..., etc.
    v = re.sub(r"\+.*$", "", v)
    # Strip ~debian, ~ubuntu, ~deb, ~exp, etc.
    v = re.sub(r"~.*$", "", v)
    return v


def parse_arch_upstream(version_str):
    """Extract the upstream version from an Arch version string.

    Arch format: upstreamversion-packagingrevision

    Examples:
        "6.18-1"       -> "6.18"
        "3.3.1-1"      -> "3.3.1"
        "5.3.15-1"     -> "5.3.15"
        "1.0.8-6"      -> "1.0.8"
        "20260707.1-1" -> "20260707.1"
        "4.19.4.arch1-1" -> "4.19.4"
    """
    v = version_str
    # Strip .arch1, .arch2, etc.
    v = re.sub(r"\.arch\d+", "", v)
    # Strip packaging revision (-N at end)
    v = re.sub(r"-[\d]+$", "", v)
    return v


def normalize_version(v):
    """Normalize a version string for comparison."""
    v = v.strip()
    # Strip leading v
    v = re.sub(r"^v", "", v)
    return v


def version_to_tuple(v):
    """Convert a version string to a tuple of (int, str) parts for proper comparison.

    Handles混合 numeric and string parts, e.g. "1.2.3" -> [(1,""), (2,""), (3,"")]
    """
    parts = []
    for part in re.split(r"[.\-]", v):
        try:
            parts.append((0, int(part)))
        except ValueError:
            parts.append((1, part))
    return parts


def compare_versions(debian_upstream, arch_upstream):
    """Compare upstream versions. Returns:
    -  0 if equal
    -  1 if Arch is newer
    - -1 if Debian is newer
    - None if incomparable
    """
    d = normalize_version(debian_upstream)
    a = normalize_version(arch_upstream)

    if d == a:
        return 0

    d_tuple = version_to_tuple(d)
    a_tuple = version_to_tuple(a)

    try:
        if a_tuple > d_tuple:
            return 1
        elif a_tuple < d_tuple:
            return -1
    except TypeError:
        # Mixed types can't compare
        return None

    return 0


def main():
    with open("data/packages.json") as f:
        debian_data = json.load(f)

    with open("data/arch_versions.json") as f:
        arch_data = json.load(f)

    arch_packages = arch_data["arch_packages"]

    results = []
    not_found = []
    same_version = []
    debian_newer = []

    for pkg in debian_data["packages"]:
        source = pkg["source"]
        debian_version = pkg.get("last_upload_version", "")
        if not debian_version:
            continue

        debian_upstream = parse_debian_upstream(debian_version)

        # Try exact match first, then common naming conventions
        arch_version = None
        candidates = [
            source,
            source.replace("-", ""),
        ]
        for c in candidates:
            if c in arch_packages:
                arch_version = arch_packages[c]
                break

        if arch_version is None:
            not_found.append(source)
            continue

        arch_upstream = parse_arch_upstream(arch_version)

        result = compare_versions(debian_upstream, arch_upstream)
        if result == 0:
            same_version.append(source)
        elif result == 1:
            results.append({
                "source": source,
                "display_name": pkg.get("display_name", source),
                "debian_version": debian_version,
                "debian_upstream": debian_upstream,
                "arch_version": arch_version,
                "arch_upstream": arch_upstream,
                "insts": pkg.get("insts", 0),
                "vote": pkg.get("vote", 0),
                "days_since_upload": pkg.get("days_since_upload"),
            })
        elif result == -1:
            debian_newer.append({
                "source": source,
                "debian_upstream": debian_upstream,
                "arch_upstream": arch_upstream,
            })

    # Sort by installs descending
    results.sort(key=lambda x: -x["insts"])

    print(f"Behind upstream (Arch newer): {len(results)}", file=sys.stderr)
    print(f"Same version: {len(same_version)}", file=sys.stderr)
    print(f"Debian newer: {len(debian_newer)}", file=sys.stderr)
    print(f"Not found on Arch: {len(not_found)}", file=sys.stderr)

    # Write full results
    output = {
        "behind_upstream": results,
        "same_version_count": len(same_version),
        "debian_newer_count": len(debian_newer),
        "not_found_count": len(not_found),
    }

    with open("data/arch_comparison.json", "w") as f:
        json.dump(output, f, indent=2)

    print("\nWrote data/arch_comparison.json", file=sys.stderr)

    # Print top 30 behind upstream
    print(f"\nTop 30 packages behind Arch:", file=sys.stderr)
    print(f"{'Source':<30} {'Debian':<20} {'Arch':<20} {'Installs':<10}", file=sys.stderr)
    print("-" * 80, file=sys.stderr)
    for r in results[:30]:
        print(f"{r['source']:<30} {r['debian_upstream']:<20} {r['arch_upstream']:<20} {r['insts']:<10}", file=sys.stderr)

    # Verify our test cases
    print("\n--- Verification ---", file=sys.stderr)
    for test in ["clamtk", "lmms", "xzgv", "scribus", "gimp"]:
        d_ver = next((p["last_upload_version"] for p in debian_data["packages"] if p["source"] == test), None)
        a_ver = arch_packages.get(test)
        if d_ver and a_ver:
            d_up = parse_debian_upstream(d_ver)
            a_up = parse_arch_upstream(a_ver)
            cmp = compare_versions(d_up, a_up)
            status = {0: "SAME", 1: "ARCH NEWER", -1: "DEBIAN NEWER"}.get(cmp, "?")
            print(f"  {test}: Debian={d_up}  Arch={a_up}  -> {status}", file=sys.stderr)


if __name__ == "__main__":
    main()
