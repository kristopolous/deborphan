#!/usr/bin/env python3
"""Merge UDD data with version comparisons into a single precomputed JSON.

Usage:
    python fetch_data.py              # fetch UDD data -> data/packages_raw.json
    python -m comparisons.fetch_all   # fetch all sources -> data/*_versions.json
    python build.py                   # merge + precompute -> data/packages.json

The output schema is documented in schema.json.
"""

import json
import sys
from datetime import datetime, timezone

from comparisons import parse_debian_upstream, to_semver, compute_version_delta
from comparisons.arch import ArchSource
from comparisons.freebsd import FreebsdSource
from comparisons.homebrew import HomebrewSource
from comparisons.pkgsrc import PkgsrcSource
from comparisons.repology import RepologySource


SOURCES = [ArchSource(), FreebsdSource(), HomebrewSource(), PkgsrcSource(), RepologySource()]


def build():
    with open("data/packages_raw.json") as f:
        raw = json.load(f)

    # Load all available comparison caches
    source_data = {}
    for source in SOURCES:
        data = source.load_cache()
        if data:
            print(f"Loaded {source.name}: {len(data)} packages", file=sys.stderr)
            source_data[source.slug] = (source, data)
        else:
            print(f"No cache for {source.name}, skipping.", file=sys.stderr)

    packages = []
    stats = {
        "total": 0,
        "behind_any": 0,
        "same_all": 0,
        "not_found_all": 0,
    }

    for pkg in raw["packages"]:
        stats["total"] += 1
        source_name = pkg["source"]
        debian_version = pkg.get("last_upload_version") or ""
        debian_upstream = parse_debian_upstream(debian_version) if debian_version else None

        entry = {
            "source": source_name,
            "display_name": pkg.get("display_name") or source_name,
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
        }

        # Compare against each source, keep the "best" (biggest delta)
        best_delta = None
        best_source_slug = None

        for slug, (source, packages_dict) in source_data.items():
            result = source.compare(source_name, debian_version, packages_dict)
            if result:
                entry[f"{slug}_version"] = result[f"{slug}_version"]
                entry[f"{slug}_upstream_version"] = result[f"{slug}_upstream_version"]
                delta = result["version_delta"]
                if delta is not None and (best_delta is None or delta > best_delta):
                    best_delta = delta
                    best_source_slug = slug

        entry["behind_upstream"] = best_delta is not None
        entry["version_delta"] = best_delta
        entry["best_comparison"] = best_source_slug

        if best_delta is not None:
            stats["behind_any"] += 1
        else:
            stats["same_all"] += 1

        packages.append(entry)

    # Aggregate by maintainer
    maintainer_map = {}
    for pkg in packages:
        maint = pkg.get("maintainer")
        if not maint:
            continue
        if maint not in maintainer_map:
            maintainer_map[maint] = {"maintainer": maint, "packages": [], "deltas": [], "total_bugs": 0, "total_insts": 0}
        m = maintainer_map[maint]
        m["packages"].append(pkg["source"])
        m["total_bugs"] += pkg.get("rc_bug_count", 0)
        m["total_insts"] += pkg.get("insts", 0)
        if pkg.get("version_delta") is not None:
            m["deltas"].append(pkg["version_delta"])

    maintainers = []
    for m in maintainer_map.values():
        if len(m["packages"]) < 2:
            continue
        maintainers.append({
            "maintainer": m["maintainer"],
            "package_count": len(m["packages"]),
            "avg_version_delta": round(sum(m["deltas"]) / len(m["deltas"]), 1) if m["deltas"] else None,
            "total_bugs": m["total_bugs"],
            "total_insts": m["total_insts"],
            "packages": m["packages"],
        })

    maintainers.sort(key=lambda m: m["package_count"], reverse=True)

    output = {
        "package_count": len(packages),
        "packages": packages,
        "maintainers": maintainers,
    }

    with open("data/packages.json", "w") as f:
        json.dump(output, f, separators=(",", ":"))

    print(f"\nWrote {len(packages)} packages to data/packages.json", file=sys.stderr)
    print(f"  Behind upstream (any source): {stats['behind_any']}", file=sys.stderr)
    print(f"  Same / not found:             {stats['same_all']}", file=sys.stderr)


if __name__ == "__main__":
    build()
