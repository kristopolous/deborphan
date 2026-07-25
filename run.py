#!/usr/bin/env python3
"""Debian Neglect Explorer — CLI entry point.

Usage:
    python run.py fetch                      # fetch all data (UDD + comparison sources)
    python run.py fetch --sources arch       # fetch only Arch
    python run.py fetch --sources arch homebrew
    python run.py build                      # build data/packages.json
    python run.py repology --limit 500       # query top 500 via Repology
    python run.py serve                      # serve on localhost:8080
    python run.py list                       # list comparison sources
    python run.py sample                     # generate sample data
"""

import argparse
import subprocess
import sys


def run(cmd, label=None):
    if label:
        print(f"\n{'='*60}", flush=True)
        print(f"  {label}", flush=True)
        print(f"{'='*60}", flush=True)
    result = subprocess.run(cmd, shell=True)
    if result.returncode != 0:
        sys.exit(result.returncode)


def get_python():
    venv = sys.prefix
    return f"{venv}/bin/python" if venv != sys.base_prefix else sys.executable


def main():
    python = get_python()

    parser = argparse.ArgumentParser(
        prog="run.py",
        description="Debian Neglect Explorer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
commands:
  fetch       Fetch data from UDD and comparison sources
  build       Merge cached data into data/packages.json
  repology    Query Repology (re-entrant, sorted by popularity)
  serve       Start local dev server
  list        List available comparison sources
  sample      Generate sample data for testing
""",
    )
    parser.add_argument("command", nargs="?", default="fetch", help="Command to run (default: fetch)")

    # fetch args
    fetch_parser = argparse.ArgumentParser(add_help=False)
    fetch_parser.add_argument("--sources", nargs="*", help="Bulk sources to fetch (default: all)")
    fetch_parser.add_argument("--no-udd", action="store_true", help="Skip UDD fetch")

    # repology args
    repology_parser = argparse.ArgumentParser(add_help=False)
    repology_parser.add_argument("--limit", type=int, default=None, help="Max packages to query")
    repology_parser.add_argument("--no-resume", action="store_true", help="Clear cache and start fresh")

    # serve args
    serve_parser = argparse.ArgumentParser(add_help=False)
    serve_parser.add_argument("--port", type=int, default=8080, help="Port (default: 8080)")

    sub, _ = parser.parse_known_args()

    if sub.command == "fetch":
        args = fetch_parser.parse_args(sys.argv[2:])
        if not args.no_udd:
            run(f"{python} fetch_data.py", "Fetching Debian data from UDD")
        sources = f" --sources {' '.join(args.sources)}" if args.sources else ""
        run(f"{python} -m comparisons.fetch_all{sources}", "Fetching comparison sources")

    elif sub.command == "build":
        run(f"{python} build.py", "Building data/packages.json")

    elif sub.command == "repology":
        args = repology_parser.parse_args(sys.argv[2:])
        cmd = f"{python} -m comparisons.repology"
        if args.limit:
            cmd += f" --limit {args.limit}"
        if args.no_resume:
            cmd += " --no-resume"
        run(cmd, "Querying Repology")

    elif sub.command == "serve":
        args = serve_parser.parse_args(sys.argv[2:])
        print(f"Serving at http://localhost:{args.port}")
        run(f"{python} -m http.server {args.port}")

    elif sub.command == "list":
        run(f"{python} -m comparisons.fetch_all --list")

    elif sub.command == "sample":
        run(f"{python} generate_sample_data.py", "Generating sample data")

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
