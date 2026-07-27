#!/usr/bin/env python3
"""Fetch Debian package neglect data from UDD and write to static JSON.

Provenance:
  - UDD: udd-mirror.debian.net (public read-only PostgreSQL mirror)
  - Descriptions: deb.debian.org/debian/dists/sid/{main,contrib,non-free,non-free-firmware}/binary-amd64/Packages.xz
  - All sources are official, public, and reproducible.
  - Downloaded files cached in ~/.cache/orphan/ to avoid re-fetching.
"""

import csv
import io
import json
import lzma
import os
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

UDD_HOST = "udd-mirror.debian.net"
UDD_PORT = 5432
UDD_DB = "udd"
UDD_USER = "udd-mirror"
UDD_PASS = "udd-mirror"

SOURCES_BASE_URL = "http://deb.debian.org/debian/dists/sid"
SOURCES_COMPONENTS = ["main", "contrib", "non-free", "non-free-firmware"]
PACKAGES_URL_TEMPLATE = SOURCES_BASE_URL + "/{component}/binary-amd64/Packages.xz"

CACHE_DIR = Path.home() / ".cache" / "orphan"
CACHE_MAX_AGE = 86400  # 24 hours

SQL = r"""
COPY (
WITH latest_sources AS (
    SELECT DISTINCT ON (source)
        source, version, maintainer, homepage,
        (string_to_array(bin, ', '))[1] AS first_bin,
        bin
    FROM sources
    WHERE distribution = 'debian' AND release = 'sid'
    ORDER BY source, version DESC
),
latest_uploads AS (
    SELECT DISTINCT ON (uh.source)
        uh.source, uh.version, uh.date
    FROM upload_history uh
    INNER JOIN latest_sources ls ON uh.source = ls.source
    ORDER BY uh.source, uh.date DESC
),
rc_bugs AS (
    SELECT
        source,
        COUNT(*) AS rc_bug_count,
        MIN(arrival) AS oldest_rc_arrival
    FROM bugs
    WHERE severity IN ('critical', 'grave', 'serious')
      AND status IN ('open', 'pending', 'done')
    GROUP BY source
)
SELECT
    ls.source,
    CASE
        WHEN ls.source = ANY(string_to_array(ls.bin, ', ')) THEN ls.source
        WHEN regexp_replace(ls.source, '^rust-', '') = ANY(string_to_array(ls.bin, ', ')) THEN regexp_replace(ls.source, '^rust-', '')
        WHEN regexp_replace(ls.source, '^python3?-', '') = ANY(string_to_array(ls.bin, ', ')) THEN regexp_replace(ls.source, '^python3?-', '')
        WHEN regexp_replace(ls.source, '^perl-', '') = ANY(string_to_array(ls.bin, ', ')) THEN regexp_replace(ls.source, '^perl-', '')
        WHEN regexp_replace(ls.source, '^ruby-', '') = ANY(string_to_array(ls.bin, ', ')) THEN regexp_replace(ls.source, '^ruby-', '')
        ELSE ls.first_bin
    END AS display_name,
    COALESCE(ps.vote, 0) AS vote,
    COALESCE(ps.insts, 0) AS insts,
    EXTRACT(EPOCH FROM (now() - lu.date)) / 86400 AS days_since_upload,
    lu.date AS last_upload_date,
    lu.version AS last_upload_version,
    COALESCE(rb.rc_bug_count, 0) AS rc_bug_count,
    CASE WHEN rb.oldest_rc_arrival IS NOT NULL
         THEN EXTRACT(EPOCH FROM (now() - rb.oldest_rc_arrival)) / 86400
         ELSE NULL
    END AS oldest_rc_bug_age,
    ls.maintainer,
    ls.homepage,
    v.status AS vcs_status,
    v.url AS vcs_url
FROM latest_sources ls
LEFT JOIN popcon_src ps ON ls.source = ps.source
LEFT JOIN latest_uploads lu ON ls.source = lu.source
LEFT JOIN rc_bugs rb ON ls.source = rb.source
LEFT JOIN vcswatch v ON ls.source = v.source
ORDER BY ls.source
) TO STDOUT WITH CSV HEADER;
"""


def fetch():
    conn_str = f"postgresql://{UDD_USER}:{UDD_PASS}@{UDD_HOST}:{UDD_PORT}/{UDD_DB}"
    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".sql", delete=False) as f:
            f.write(SQL)
            sql_path = f.name
        try:
            result = subprocess.run(
                ["psql", conn_str, "-f", sql_path],
                capture_output=True,
                text=True,
                timeout=300,
                env={"PGSSLMODE": "require"},
            )
        finally:
            os.unlink(sql_path)
    except FileNotFoundError:
        print("psql not found. Install postgresql-client.", file=sys.stderr)
        sys.exit(1)
    except subprocess.TimeoutExpired:
        print("Query timed out after 300s.", file=sys.stderr)
        sys.exit(1)

    if result.returncode != 0:
        print(f"psql error:\n{result.stderr}", file=sys.stderr)
        sys.exit(1)

    reader = csv.DictReader(io.StringIO(result.stdout))

    def parse_float(v):
        try:
            return float(v)
        except (ValueError, TypeError):
            return None

    def parse_int(v):
        try:
            return int(v)
        except (ValueError, TypeError):
            return 0

    rows = []
    for r in reader:
        rows.append({
            "source": r["source"],
            "display_name": r["display_name"] or r["source"],
            "vote": parse_int(r["vote"]),
            "insts": parse_int(r["insts"]),
            "days_since_upload": parse_float(r["days_since_upload"]),
            "last_upload_date": r["last_upload_date"] or None,
            "last_upload_version": r["last_upload_version"] or None,
            "rc_bug_count": parse_int(r["rc_bug_count"]),
            "oldest_rc_bug_age": parse_float(r["oldest_rc_bug_age"]),
            "maintainer": r["maintainer"] or None,
            "homepage": r["homepage"] or None,
            "vcs_status": r["vcs_status"] or None,
            "vcs_url": r["vcs_url"] or None,
        })

    return rows


def _fetch_or_cached(url, cache_key):
    """Download a file, caching in ~/.cache/orphan/. Returns path to cached file."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = CACHE_DIR / cache_key

    if cache_path.exists():
        age = time.time() - cache_path.stat().st_mtime
        if age < CACHE_MAX_AGE:
            print(f"  Using cached {cache_key} ({age/3600:.1f}h old)", file=sys.stderr)
            return cache_path

    print(f"  Downloading {url}...", file=sys.stderr)
    req = urllib.request.Request(url, headers={"User-agent": "debian-neglect-explorer/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = resp.read()
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as e:
        print(f"  Warning: failed to download {url}: {e}", file=sys.stderr)
        if cache_path.exists():
            print(f"  Using stale cache {cache_key}", file=sys.stderr)
            return cache_path
        return None

    cache_path.write_bytes(data)
    print(f"  Cached {cache_key} ({len(data)} bytes)", file=sys.stderr)
    return cache_path


def _parse_packages_xz(path):
    """Stream-parse a Packages.xz file, yielding (package_name, short_description)."""
    with lzma.open(path, "rt", errors="replace") as f:
        current_pkg = None
        in_description = False
        for line in f:
            line = line.rstrip("\n")
            if line.startswith("Package: "):
                current_pkg = line[9:].strip()
                in_description = False
            elif line.startswith("Description: ") and current_pkg:
                yield current_pkg, line[13:].strip()
                in_description = True
            elif in_description and (line.startswith(" ") or line.startswith("\t")):
                continue
            else:
                in_description = False


def fetch_descriptions():
    """Fetch package descriptions from binary Packages.xz on the Debian mirror.

    Downloads one Packages.xz per component (~10MB each, cached 24h in
    ~/.cache/orphan/). Streams and parses Package: + Description: fields.
    ~76k binary packages across all components; some are duplicates.

    Returns a dict of {source_name: short_description}.
    """
    descriptions = {}

    for component in SOURCES_COMPONENTS:
        url = PACKAGES_URL_TEMPLATE.format(component=component)
        cache_key = f"sid_{component}_binary-amd64_Packages.xz"
        path = _fetch_or_cached(url, cache_key)
        if not path:
            continue

        count = 0
        for pkg_name, desc in _parse_packages_xz(path):
            if pkg_name not in descriptions:
                descriptions[pkg_name] = desc
            count += 1

        print(f"  Parsed {component}: {count} entries, {len(descriptions)} unique descriptions", file=sys.stderr)

    return descriptions


def main():
    print(f"Querying UDD at {UDD_HOST}...", file=sys.stderr)
    rows = fetch()
    print(f"Fetched {len(rows)} packages.", file=sys.stderr)

    print("Fetching Debian descriptions from binary Packages.xz files...", file=sys.stderr)
    descriptions = fetch_descriptions()
    print(f"Got {len(descriptions)} binary package descriptions.", file=sys.stderr)

    # Binary package names don't always match source names. Map source → description
    # using the first binary name that matches.
    source_to_desc = {}
    for row in rows:
        src = row["source"]
        if src in descriptions:
            source_to_desc[src] = descriptions[src]
        else:
            # Try display_name (first binary package name)
            dn = row["display_name"]
            if dn in descriptions:
                source_to_desc[src] = descriptions[dn]

    # Merge descriptions into rows
    for row in rows:
        row["description"] = source_to_desc.get(row["source"])

    filled = sum(1 for row in rows if row["description"])
    print(f"  Mapped {filled}/{len(rows)} source packages to descriptions.", file=sys.stderr)

    output = {
        "packages": rows,
    }

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    output_path = CACHE_DIR / "packages_raw.json"
    with open(output_path, "w") as f:
        json.dump(output, f, separators=(",", ":"))

    print(f"Wrote {output_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
