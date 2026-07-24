#!/usr/bin/env python3
"""Fetch Debian package neglect data from UDD and write to static JSON."""

import json
import subprocess
import sys
from datetime import datetime, timezone

UDD_HOST = "udd-mirror.debian.net"
UDD_PORT = 5432
UDD_DB = "udd"
UDD_USER = "udd"

SQL = """
WITH latest_uploads AS (
    SELECT DISTINCT ON (source)
        source, version, date
    FROM upload_history
    WHERE distribution = 'debian'
    ORDER BY source, date DESC
),
rc_bugs AS (
    SELECT
        source,
        COUNT(*) AS rc_bug_count,
        MIN(arrival) AS oldest_rc_arrival
    FROM all_bugs
    WHERE severity IN ('critical', 'grave', 'serious')
      AND status IN ('open', 'pending', 'done')
    GROUP BY source
)
SELECT
    s.source,
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
    s.maintainer,
    v.status AS vcs_status,
    v.url AS vcs_url
FROM sources s
LEFT JOIN popcon_src ps ON s.source = ps.source
LEFT JOIN latest_uploads lu ON s.source = lu.source
LEFT JOIN rc_bugs rb ON s.source = rb.source
LEFT JOIN vcswatch v ON s.source = v.source
WHERE s.distribution = 'debian'
  AND s.release = 'sid'
  AND s.component = 'main'
ORDER BY s.source;
"""

def fetch():
    try:
        result = subprocess.run(
            [
                "psql",
                "-h", UDD_HOST,
                "-p", str(UDD_PORT),
                "-U", UDD_USER,
                "-d", UDD_DB,
                "--no-align",
                "-t",
                "-A",
                "-F", "\t",
                "-c", SQL,
            ],
            capture_output=True,
            text=True,
            timeout=300,
            env={"PGSSLMODE": "require"},
        )
    except FileNotFoundError:
        print("psql not found. Install postgresql-client.", file=sys.stderr)
        sys.exit(1)
    except subprocess.TimeoutExpired:
        print("Query timed out after 300s.", file=sys.stderr)
        sys.exit(1)

    if result.returncode != 0:
        print(f"psql error:\n{result.stderr}", file=sys.stderr)
        sys.exit(1)

    rows = []
    for line in result.stdout.strip().split("\n"):
        if not line:
            continue
        fields = line.split("\t")
        if len(fields) < 10:
            continue
        source, vote, insts, days_since_upload, last_upload_date, \
            last_upload_version, rc_bug_count, oldest_rc_bug_age, \
            maintainer, vcs_status, vcs_url = fields[:11]

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

        rows.append({
            "source": source,
            "vote": parse_int(vote),
            "insts": parse_int(insts),
            "days_since_upload": parse_float(days_since_upload),
            "last_upload_date": last_upload_date if last_upload_date else None,
            "last_upload_version": last_upload_version if last_upload_version else None,
            "rc_bug_count": parse_int(rc_bug_count),
            "oldest_rc_bug_age": parse_float(oldest_rc_bug_age),
            "maintainer": maintainer if maintainer else None,
            "vcs_status": vcs_status if vcs_status else None,
            "vcs_url": vcs_url if vcs_url else None,
        })

    return rows


def main():
    print(f"Querying UDD at {UDD_HOST}...", file=sys.stderr)
    rows = fetch()
    print(f"Fetched {len(rows)} packages.", file=sys.stderr)

    output = {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "package_count": len(rows),
        "packages": rows,
    }

    with open("data/packages.json", "w") as f:
        json.dump(output, f, separators=(",", ":"))

    print("Wrote data/packages.json", file=sys.stderr)


if __name__ == "__main__":
    main()
