#!/usr/bin/env python3
from __future__ import annotations

"""
ThinkWiki Script: build_inbox

Purpose:
- Build the HTML inbox review page from the current inbox contents.

Usage:
- Prefer `python scripts/thinkwiki inbox ...`.
- Run `python scripts/<script> --help` for direct CLI details when the file exposes its own arguments.
"""


import argparse
from pathlib import Path

from utils import append_log, file_uri, find_repo_root, print_output_serve_hint, today_str, write_inbox_review, write_output_home


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a lightweight static HTML inbox review page for the current wiki.")
    parser.add_argument("--root", default=".", help="Wiki root path")
    args = parser.parse_args()

    root = find_repo_root(Path(args.root))
    inbox_page = write_inbox_review(root)
    output_home = write_output_home(root)

    append_log(
        root,
        f"[{today_str()}] inbox | review page",
        [
            "- review: output/inbox/index.html",
            "- hub: output/index.html",
        ],
    )
    print("Inbox review: output/inbox/index.html")
    print(f"Inbox review URI: {file_uri(inbox_page)}")
    print("Output hub: output/index.html")
    print(f"Output hub URI: {file_uri(output_home)}")
    print_output_serve_hint(root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
