#!/usr/bin/env python3
from __future__ import annotations

"""
ThinkWiki Script: batch_ingest

Purpose:
- Promote multiple inbox items into the wiki in one deterministic run.

Usage:
- Prefer `python scripts/thinkwiki batch-ingest ...`.
- Run `python scripts/<script> --help` for direct CLI details when the file exposes its own arguments.
"""


import argparse
import shutil
from pathlib import Path

import rebuild_index
from ingest import ingest_local_source
from utils import (
    append_log,
    collect_inbox_items,
    file_uri,
    find_repo_root,
    today_str,
    write_inbox_review,
    write_output_home,
    write_text,
)


def filter_inbox_items(root: Path, quality: str, limit: int) -> list[dict]:
    items = collect_inbox_items(root)
    if quality != "all":
        items = [item for item in items if str(item.get("quality_status", "") or "") == quality]
    if limit > 0:
        return items[:limit]
    return items


def cleanup_inbox_artifacts(root: Path, item: dict) -> list[str]:
    removed: list[str] = []
    normalized_path = root / str(item.get("path", "") or "")
    if normalized_path.exists():
        normalized_path.unlink()
        removed.append(normalized_path.relative_to(root).as_posix())

    metadata_path = str(item.get("metadata_path", "") or "").strip()
    if metadata_path:
        metadata_target = root / metadata_path
        if metadata_target.exists():
            metadata_target.unlink()
            removed.append(metadata_target.relative_to(root).as_posix())

    raw_inbox_dir = root / "raw" / "inbox"
    if raw_inbox_dir.exists() and normalized_path.name:
        for candidate in sorted(raw_inbox_dir.glob(f"{normalized_path.stem}.*")):
            if candidate.is_file():
                candidate.unlink()
                removed.append(candidate.relative_to(root).as_posix())

    media_dir = str(item.get("media_dir", "") or "").strip()
    if media_dir:
        media_target = root / media_dir
        if media_target.exists():
            shutil.rmtree(media_target)
            removed.append(media_target.relative_to(root).as_posix())

    return removed


def format_item_line(item: dict) -> str:
    return "- {title} | {path} | quality={quality}".format(
        title=str(item.get("title", "Untitled")),
        path=str(item.get("path", "") or ""),
        quality=str(item.get("quality_status", "") or "unknown"),
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Batch ingest inbox items into ThinkWiki, prioritizing quality-filtered entries."
    )
    parser.add_argument("--root", default=".", help="Wiki root path")
    parser.add_argument(
        "--quality",
        default="ready",
        choices=["ready", "review", "weak", "all"],
        help="Only process inbox items with the selected quality status",
    )
    parser.add_argument("--limit", default=0, type=int, help="Maximum number of inbox items to process (0 means no limit)")
    parser.add_argument("--dry-run", action="store_true", help="Show which inbox items would be ingested without changing files")
    args = parser.parse_args()

    root = find_repo_root(Path(args.root))
    selected = filter_inbox_items(root, args.quality, args.limit)

    lines = [
        "# ThinkWiki Batch Ingest",
        "",
        f"- Root: {root}",
        f"- Quality Filter: {args.quality}",
        f"- Limit: {'all' if args.limit <= 0 else args.limit}",
        f"- Dry Run: {'yes' if args.dry_run else 'no'}",
        f"- Matched Items: {len(selected)}",
        "",
    ]

    if not selected:
        lines.append("No inbox items matched the current filter.")
        print("\n".join(lines))
        return 0

    lines.append("## Selected Items")
    lines.append("")
    lines.extend(format_item_line(item) for item in selected)
    lines.append("")

    if args.dry_run:
        lines.append("Dry run complete. No files were changed.")
        print("\n".join(lines))
        return 0

    ingested: list[dict[str, str]] = []
    removed_paths: list[str] = []
    failures: list[str] = []
    for item in selected:
        source_path = root / str(item.get("path", "") or "")
        if not source_path.exists():
            failures.append(f"- missing source: {source_path.relative_to(root).as_posix()}")
            continue
        try:
            result = ingest_local_source(root, source_path)
        except SystemExit as exc:
            failures.append(f"- failed: {source_path.relative_to(root).as_posix()} | {exc}")
            continue
        ingested.append({
            "title": str(result["title"]),
            "source_page": Path(result["source_page"]).relative_to(root).as_posix(),
        })
        removed_paths.extend(cleanup_inbox_artifacts(root, item))

    write_text(root / "index.md", rebuild_index.build_index(root))
    inbox_page = write_inbox_review(root)
    output_home = write_output_home(root)

    append_log(
        root,
        f"[{today_str()}] batch-ingest | quality={args.quality}",
        [
            f"- matched: {len(selected)}",
            f"- ingested: {len(ingested)}",
            *[f"- created: {item['source_page']}" for item in ingested],
            *[f"- cleared: {path}" for path in removed_paths],
            *failures,
        ],
    )

    lines.extend([
        "## Results",
        "",
        f"- Ingested: {len(ingested)}",
        f"- Cleared Inbox Artifacts: {len(removed_paths)}",
        f"- Failed: {len(failures)}",
    ])
    lines.extend(f"- {item['title']} -> {item['source_page']}" for item in ingested)
    if failures:
        lines.append("")
        lines.append("## Failures")
        lines.append("")
        lines.extend(failures)
    lines.extend([
        "",
        "Inbox review: output/inbox/index.html",
        f"Inbox review URI: {file_uri(inbox_page)}",
        "Output hub: output/index.html",
        f"Output hub URI: {file_uri(output_home)}",
        f"Next: run `python scripts/thinkwiki viewer --root {root}` to refresh the local viewer page.",
        f"Next: run `python scripts/thinkwiki graph --root {root}` to refresh the knowledge graph page.",
    ])
    print("\n".join(lines))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
