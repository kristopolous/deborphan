#!/usr/bin/env python3
"""Fetch Debian package neglect data from UDD and write to static JSON.

Provenance:
  - UDD: udd-mirror.debian.net (public read-only PostgreSQL mirror)
  - Descriptions: deb.debian.org/debian/dists/sid/{main,contrib,non-free,non-free-firmware}/source/Sources.xz
  - All sources are official, public, and reproducible.
"""

import csv
import io
import json
import os
import subprocess
import sys
import tempfile
import urllib.request
from datetime import datetime, timezone

UDD_HOST = "udd-mirror.debian.net"
UDD_PORT = 5432
UDD_DB = "udd"
UDD_USER = "udd-mirror"
UDD_PASS = "udd-mirror"

SOURCES_BASE_URL = "http://deb.debian.org/debian/dists/sid"
SOURCES_COMPONENTS = ["main", "contrib", "non-free", "non-free-firmware"]

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


def fetch_descriptions():
    """Fetch package descriptions from Debian Sources.xz files.

    Downloads one Sources.xz per component from the official Debian mirror,
    parses Description fields, and returns a dict of {source_name: description}.

    The short description (first line after Description:) is used.
    Long descriptions (indented continuation lines) are excluded.
    """
    descriptions = {}

    for component in SOURCES_COMPONENTS:
        url = f"{SOURCES_BASE_URL}/{component}/source/Sources.xz"
        print(f"  Downloading {url}...", file=sys.stderr)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "debian-neglect-explorer/1.0"})
            with urllib.request.urlopen(req, timeout=60) as resp:
                compressed = resp.read()
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as e:
            print(f"  Warning: failed to download {url}: {e}", file=sys.stderr)
            continue

        # Decompress and parse
        import lzma
        try:
            text = lzma.decompress(compressed).decode("utf-8", errors="replace")
        except lzma.LZMAError as e:
            print(f"  Warning: failed to decompress {url}: {e}", file=sys.stderr)
            continue

        # Parse Description fields from Sources format
        # Description: short description text
        #  continuation lines start with space or tab
        current_source = None
        in_description = False
        for line in text.split("\n"):
            if line.startswith("Package: "):
                current_source = line[len("Package: "):].strip()
                in_description = False
            elif line.startswith("Description: ") and current_source:
                # Short description is the text after "Description: "
                desc = line[len("Description: "):].strip()
                descriptions[current_source] = desc
                in_description = True
            elif in_description and (line.startswith(" ") or line.startswith("\t")):
                # Continuation line — skip (we only want short description)
                continue
            else:
                in_description = False

        print(f"  Parsed {component}: {sum(1 for s in descriptions if True)} total descriptions so far", file=sys.stderr)

    return descriptions


def main():
    print(f"Querying UDD at {UDD_HOST}...", file=sys.stderr)
    rows = fetch()
    print(f"Fetched {len(rows)} packages.", file=sys.stderr)

    print("Fetching Debian descriptions from Sources.xz...", file=sys.stderr)
    descriptions = fetch_descriptions()
    print(f"Got {len(descriptions)} descriptions.", file=sys.stderr)

    # Merge descriptions into rows
    for row in rows:
        row["description"] = descriptions.get(row["source"])

    output = {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "sources_mirror": SOURCES_BASE_URL,
        "package_count": len(rows),
        "description_count": len(descriptions),
        "packages": rows,
    }

    with open("data/packages_raw.json", "w") as f:
        json.dump(output, f, separators=(",", ":"))

    print("Wrote data/packages_raw.json", file=sys.stderr)


if __name__ == "__main__":
    main()
