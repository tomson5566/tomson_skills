#!/usr/bin/env python3
from __future__ import annotations

"""
ThinkWiki Script: status

Purpose:
- Print a compact workspace snapshot with page, inbox, and output summary data.

Usage:
- Prefer `python scripts/thinkwiki status ...`.
- Run `python scripts/<script> --help` for direct CLI details when the file exposes its own arguments.
"""


import argparse
from pathlib import Path

from utils import find_repo_root
from workspace_status import collect_workspace_snapshot, format_status_lines


def main() -> int:
    parser = argparse.ArgumentParser(description="Show a compact operational status summary for the current ThinkWiki workspace.")
    parser.add_argument("--root", default=".", help="Wiki root path")
    args = parser.parse_args()

    root = find_repo_root(Path(args.root))
    snapshot = collect_workspace_snapshot(root)
    print("\n".join(format_status_lines(snapshot)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
