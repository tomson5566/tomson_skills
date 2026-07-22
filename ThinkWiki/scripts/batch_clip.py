#!/usr/bin/env python3
from __future__ import annotations

"""
ThinkWiki Script: batch_clip

Purpose:
- Clip many files, URLs, or text entries into the inbox from a directory scan or manifest.

Usage:
- Prefer `python scripts/thinkwiki batch-clip ...`.
- Run `python scripts/<script> --help` for direct CLI details when the file exposes its own arguments.
"""


import argparse
import json
from pathlib import Path

from clip import clip_local_source, clip_text_source, clip_web_source
from ingest import SUPPORTED_INGEST_EXTENSIONS
from utils import (
    append_log,
    batch_ingest_command,
    ensure_runtime_dirs,
    file_uri,
    find_repo_root,
    today_str,
    write_inbox_review,
    write_output_home,
)


def collect_source_dir_items(source_dir: Path) -> list[dict[str, object]]:
    items: list[dict[str, object]] = []
    for path in sorted(source_dir.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix.lower() not in SUPPORTED_INGEST_EXTENSIONS:
            continue
        items.append({
            "kind": "source",
            "source_path": path.resolve(),
            "display": str(path),
            "title": "",
        })
    return items


def load_manifest_items(manifest_path: Path) -> list[dict[str, object]]:
    raw = manifest_path.read_text(encoding="utf-8")
    if manifest_path.suffix.lower() == ".json":
        payload = json.loads(raw)
        if isinstance(payload, dict):
            payload = payload.get("items", [])
        if not isinstance(payload, list):
            raise SystemExit(f"Manifest must be a JSON array or an object with an `items` array: {manifest_path}")
        rows = payload
    else:
        rows = []
        for line in raw.splitlines():
            compact = line.strip()
            if not compact or compact.startswith("#"):
                continue
            rows.append(json.loads(compact))
    normalized: list[dict[str, object]] = []
    for index, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            raise SystemExit(f"Manifest item {index} must be an object")
        normalized.append(normalize_manifest_item(row, manifest_path.parent, index))
    return normalized


def normalize_manifest_item(row: dict[str, object], base_dir: Path, index: int) -> dict[str, object]:
    provided = [bool(str(row.get("source", "") or "").strip()), bool(str(row.get("url", "") or "").strip()), bool("text" in row and str(row.get("text", "") or "").strip())]
    if sum(provided) != 1:
        raise SystemExit(f"Manifest item {index} must provide exactly one of `source`, `url`, or `text`")
    title = str(row.get("title", "") or "").strip()
    if provided[0]:
        source_value = str(row.get("source", "") or "").strip()
        source_path = Path(source_value)
        if not source_path.is_absolute():
            source_path = (base_dir / source_path).resolve()
        return {
            "kind": "source",
            "source_path": source_path,
            "display": source_value,
            "title": title,
        }
    if provided[1]:
        url = str(row.get("url", "") or "").strip()
        return {
            "kind": "url",
            "url": url,
            "display": title or url,
            "title": title,
            "adapter": str(row.get("adapter", "auto") or "auto"),
            "mode": str(row.get("mode", "auto") or "auto"),
            "wait_seconds": int(row.get("waitSeconds", row.get("wait_seconds", 8)) or 8),
            "media": str(row.get("media", "ask") or "ask"),
        }
    text = str(row.get("text", "") or "")
    return {
        "kind": "text",
        "text": text,
        "display": title or f"manifest text #{index}",
        "title": title,
    }


def planned_items(args: argparse.Namespace) -> list[dict[str, object]]:
    items: list[dict[str, object]]
    if args.source_dir:
        source_dir = Path(args.source_dir).resolve()
        if not source_dir.exists() or not source_dir.is_dir():
            raise SystemExit(f"Source directory not found: {source_dir}")
        items = collect_source_dir_items(source_dir)
    else:
        manifest_path = Path(args.manifest).resolve()
        if not manifest_path.exists() or not manifest_path.is_file():
            raise SystemExit(f"Manifest file not found: {manifest_path}")
        items = load_manifest_items(manifest_path)
    if args.limit > 0:
        return items[: args.limit]
    return items


def format_item_line(item: dict[str, object]) -> str:
    return "- {kind}: {display}".format(
        kind=str(item.get("kind", "item")),
        display=str(item.get("display", "") or ""),
    )


def execute_item(root: Path, item: dict[str, object]) -> dict[str, str]:
    kind = str(item.get("kind", "") or "")
    if kind == "source":
        source_path = Path(item["source_path"])
        if not source_path.exists() or not source_path.is_file():
            raise SystemExit(f"Source file not found: {source_path}")
        title, raw_path, normalized_path = clip_local_source(root, source_path, str(item.get("title", "") or ""))
        return {
            "title": title,
            "raw_path": raw_path.relative_to(root).as_posix(),
            "normalized_path": normalized_path.relative_to(root).as_posix(),
            "metadata_path": "",
        }
    if kind == "url":
        title, raw_path, normalized_path, metadata_path, _metadata = clip_web_source(
            root,
            str(item.get("url", "") or ""),
            str(item.get("title", "") or ""),
            str(item.get("adapter", "auto") or "auto"),
            str(item.get("mode", "auto") or "auto"),
            int(item.get("wait_seconds", 8) or 8),
            str(item.get("media", "ask") or "ask"),
        )
        return {
            "title": title,
            "raw_path": raw_path.relative_to(root).as_posix(),
            "normalized_path": normalized_path.relative_to(root).as_posix(),
            "metadata_path": metadata_path.relative_to(root).as_posix(),
        }
    title, raw_path, normalized_path = clip_text_source(root, str(item.get("text", "") or ""), str(item.get("title", "") or ""))
    return {
        "title": title,
        "raw_path": raw_path.relative_to(root).as_posix(),
        "normalized_path": normalized_path.relative_to(root).as_posix(),
        "metadata_path": "",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Clip multiple files, webpages, or inline notes into the ThinkWiki inbox.")
    parser.add_argument("--root", default=".", help="Wiki root path")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--source-dir", help="Directory of local source files to clip into inbox")
    group.add_argument("--manifest", help="JSON or JSONL manifest that lists source/url/text items to clip")
    parser.add_argument("--limit", default=0, type=int, help="Maximum number of items to process (0 means no limit)")
    parser.add_argument("--dry-run", action="store_true", help="Show which items would be clipped without changing files")
    args = parser.parse_args()

    root = find_repo_root(Path(args.root))
    items = planned_items(args)
    lines = [
        "# ThinkWiki Batch Clip",
        "",
        f"- Root: {root}",
        f"- Input: {'source-dir' if args.source_dir else 'manifest'}",
        f"- Limit: {'all' if args.limit <= 0 else args.limit}",
        f"- Dry Run: {'yes' if args.dry_run else 'no'}",
        f"- Matched Items: {len(items)}",
        "",
    ]
    if not items:
        lines.append("No clip items matched the current input.")
        print("\n".join(lines))
        return 0

    lines.append("## Selected Items")
    lines.append("")
    lines.extend(format_item_line(item) for item in items)
    lines.append("")
    if args.dry_run:
        lines.append("Dry run complete. No files were changed.")
        print("\n".join(lines))
        return 0

    ensure_runtime_dirs(root)
    successes: list[dict[str, str]] = []
    failures: list[str] = []
    for item in items:
        try:
            successes.append(execute_item(root, item))
        except SystemExit as exc:
            failures.append(f"- failed: {item.get('display', '')} | {exc}")

    inbox_page = write_inbox_review(root)
    output_home = write_output_home(root)
    append_log(
        root,
        f"[{today_str()}] batch-clip | {'source-dir' if args.source_dir else 'manifest'}",
        [
            f"- matched: {len(items)}",
            f"- clipped: {len(successes)}",
            *[f"- normalized: {item['normalized_path']}" for item in successes],
            *[f"- metadata: {item['metadata_path']}" for item in successes if item["metadata_path"]],
            *failures,
        ],
    )

    lines.extend([
        "## Results",
        "",
        f"- Clipped: {len(successes)}",
        f"- Failed: {len(failures)}",
    ])
    lines.extend(
        "- {title} -> {path}".format(title=item["title"], path=item["normalized_path"])
        for item in successes
    )
    if failures:
        lines.extend(["", "## Failures", ""])
        lines.extend(failures)
    lines.extend([
        "",
        "Inbox review: output/inbox/index.html",
        f"Inbox review URI: {file_uri(inbox_page)}",
        "Output hub: output/index.html",
        f"Output hub URI: {file_uri(output_home)}",
        f"Next: run `{batch_ingest_command(root, quality='ready', dry_run=True)}` to preview batch ingest candidates.",
    ])
    print("\n".join(lines))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
