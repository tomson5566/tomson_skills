#!/usr/bin/env python3
from __future__ import annotations

"""
ThinkWiki Script: correct

Purpose:
- Save a correction, pitfall, or operational lesson as durable wiki knowledge.

Usage:
- Prefer `python scripts/thinkwiki correct ...`.
- Run `python scripts/<script> --help` for direct CLI details when the file exposes its own arguments.
"""


import argparse
from pathlib import Path

from crystallize import first_meaningful_line, write_page
from utils import find_repo_root


def build_key_points(mistake: str, fix: str, apply_when: str) -> list[str]:
    points = [
        f"Avoid this mistake: {mistake.strip()}",
        f"Preferred correction: {fix.strip()}",
    ]
    if apply_when.strip():
        points.append(f"Apply when: {apply_when.strip()}")
    return points


def build_content(mistake: str, fix: str, apply_when: str, context: str) -> str:
    lines = [
        "## Error Pattern",
        "",
        mistake.strip() or "TODO",
        "",
        "## Correct Guidance",
        "",
        fix.strip() or "TODO",
    ]
    if apply_when.strip():
        lines.extend([
            "",
            "## When To Apply",
            "",
            apply_when.strip(),
        ])
    if context.strip():
        lines.extend([
            "",
            "## Context",
            "",
            context.strip(),
        ])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Persist a user correction as a reusable wiki page.")
    parser.add_argument("--root", default=".", help="Wiki root path")
    parser.add_argument("--mistake", required=True, help="What was wrong before")
    parser.add_argument("--fix", required=True, help="What should be done instead")
    parser.add_argument("--title", default="", help="Optional page title")
    parser.add_argument("--kind", choices=["concept", "decision"], default="concept", help="Target page type")
    parser.add_argument("--source-path", action="append", default=[], help="Supporting wiki or raw source path")
    parser.add_argument("--related-path", action="append", default=[], help="Related wiki page path")
    parser.add_argument("--apply-when", default="", help="When the correction applies")
    parser.add_argument("--context", default="", help="Extra context explaining the correction")
    parser.add_argument("--slug", default="", help="Explicit target slug")
    parser.add_argument("--update", action="store_true", help="Update an existing correction page")
    parser.add_argument("--merge-mode", choices=["append", "replace", "dedupe"], default="dedupe", help="How to merge content on update")
    parser.add_argument("--confidence", default="verified", help="Confidence label for the correction page")
    parser.add_argument("--status", default="active", help="Status label for the correction page")
    args = parser.parse_args()

    root = find_repo_root(Path(args.root))
    title = args.title.strip() or first_meaningful_line(args.fix, args.mistake)
    summary = args.fix.strip() or first_meaningful_line(args.mistake, title)
    content = build_content(args.mistake, args.fix, args.apply_when, args.context)
    key_points = build_key_points(args.mistake, args.fix, args.apply_when)

    default_sources = args.source_path or args.related_path or ["log.md"]

    page_path, action = write_page(
        root=root,
        kind=args.kind,
        title=title,
        summary=summary,
        content=content,
        source_paths=default_sources,
        related_paths=args.related_path,
        follow_ups=[],
        findings=[],
        tensions=[],
        key_points=key_points if args.kind == "concept" else [],
        action_label="correct",
        slug=args.slug,
        update=args.update,
        merge_mode=args.merge_mode,
        confidence=args.confidence,
        status=args.status,
    )
    print(f"{action.title()} {page_path.relative_to(root).as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
