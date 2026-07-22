#!/usr/bin/env python3
from __future__ import annotations

"""
ThinkWiki Script: rebuild_index

Purpose:
- Rebuild the Markdown index page that summarizes wiki pages by section.

Usage:
- Prefer `python scripts/thinkwiki rebuild-index ...`.
- Run `python scripts/<script> --help` for direct CLI details when the file exposes its own arguments.
"""


import argparse
from pathlib import Path

from utils import SECTION_ORDER, collect_wiki_pages, extract_summary, find_repo_root, parse_frontmatter, read_text, write_text


def build_index(root: Path) -> str:
    type_to_section = {page_type: heading for heading, page_type in SECTION_ORDER}
    sections = {heading: [] for heading, _page_type in SECTION_ORDER}

    for page in collect_wiki_pages(root):
        meta, body = parse_frontmatter(read_text(page))
        page_type = str(meta.get("type") or page.parent.name[:-1])
        heading = type_to_section.get(page_type)
        if not heading:
            continue
        title = str(meta.get("title") or page.stem)
        summary = extract_summary(meta, body)
        updated = str(meta.get("updated") or "")
        link = page.relative_to(root).as_posix()
        sections[heading].append(f"| [{title}]({link}) | {page_type} | {summary} | {updated} |")

    lines = [
        "# Knowledge Base Index",
        "",
        "## Overview",
        "",
        "- 总览页：[overview.md](overview.md)",
        "- 操作日志：[log.md](log.md)",
        "- 目标说明：[purpose.md](purpose.md)",
        "",
    ]
    for heading, _page_type in SECTION_ORDER:
        lines.extend([
            f"## {heading}",
            "",
            "| Page | Type | Summary | Updated |",
            "| --- | --- | --- | --- |",
            *sections[heading],
            "",
        ])
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Rebuild index.md from wiki pages.")
    parser.add_argument("--root", default=".", help="Wiki root path")
    args = parser.parse_args()
    root = find_repo_root(Path(args.root))
    write_text(root / "index.md", build_index(root))
    print(f"Rebuilt {root / 'index.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
