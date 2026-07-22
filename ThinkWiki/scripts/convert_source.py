#!/usr/bin/env python3
from __future__ import annotations

"""
ThinkWiki Script: convert_source

Purpose:
- Convert a source file or webpage into Markdown without writing into a wiki.

Usage:
- Prefer `python scripts/thinkwiki convert ...`.
- Run `python scripts/<script> --help` for direct CLI details when the file exposes its own arguments.
"""


import argparse
import sys
from pathlib import Path

from ingest import MARKDOWN_EXTENSIONS, fetch_webpage_as_markdown, normalize_local_source
from utils import write_text

DEFAULT_EXTENSIONS = MARKDOWN_EXTENSIONS | {".pdf", ".docx", ".xlsx", ".xls", ".pptx"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Convert local files or webpages into Markdown.")
    source_group = parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument("--source", help="Local file or directory to convert")
    source_group.add_argument("--url", help="Web page URL to convert")
    parser.add_argument("--output-file", default="", help="Optional target Markdown file for a single source")
    parser.add_argument("--output-dir", default="", help="Optional output directory for directory conversion")
    parser.add_argument("--title", default="", help="Optional title override for webpage conversion")
    parser.add_argument(
        "--ext",
        nargs="*",
        default=sorted(DEFAULT_EXTENSIONS),
        help="Extensions to include when --source points to a directory",
    )
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing outputs")
    return parser.parse_args()


def normalize_extensions(values: list[str]) -> set[str]:
    extensions: set[str] = set()
    for value in values:
        ext = value.lower()
        if not ext.startswith("."):
            ext = f".{ext}"
        extensions.add(ext)
    return extensions


def write_output(path: Path, content: str, overwrite: bool) -> None:
    if path.exists() and not overwrite:
        raise SystemExit(f"output file already exists: {path}")
    write_text(path, content.rstrip() + "\n")


def convert_single_file(source_path: Path, output_file: str, overwrite: bool) -> int:
    content = normalize_local_source(source_path)
    if output_file:
        target = Path(output_file).expanduser().resolve()
        write_output(target, content, overwrite)
        print(f"Converted {source_path} -> {target}")
        return 0
    print(content.rstrip())
    return 0


def convert_directory(source_dir: Path, output_dir: str, extensions: set[str], overwrite: bool) -> int:
    if not output_dir:
        raise SystemExit("--output-dir is required when --source points to a directory")
    target_root = Path(output_dir).expanduser().resolve()
    files = sorted(
        path for path in source_dir.rglob("*") if path.is_file() and path.suffix.lower() in extensions
    )
    if not files:
        print("No matching files found.")
        return 0

    converted = 0
    skipped = 0
    for source_file in files:
        target_file = target_root / source_file.relative_to(source_dir)
        target_file = target_file.with_suffix(".md")
        if target_file.exists() and not overwrite:
            skipped += 1
            print(f"[SKIP] {target_file}")
            continue
        content = normalize_local_source(source_file)
        write_output(target_file, content, True)
        converted += 1
        print(f"[OK] {source_file} -> {target_file}")

    print(f"Done. converted={converted} skipped={skipped}")
    return 0


def convert_url(url: str, output_file: str, overwrite: bool, title: str) -> int:
    content, _raw_html = fetch_webpage_as_markdown(url, title_override=title)
    if output_file:
        target = Path(output_file).expanduser().resolve()
        write_output(target, content, overwrite)
        print(f"Converted {url} -> {target}")
        return 0
    print(content.rstrip())
    return 0


def main() -> int:
    args = parse_args()
    if args.url:
        return convert_url(args.url, args.output_file, args.overwrite, args.title)

    source_path = Path(args.source).expanduser().resolve()
    if not source_path.exists():
        raise SystemExit(f"source not found: {source_path}")
    if source_path.is_dir():
        return convert_directory(source_path, args.output_dir, normalize_extensions(args.ext), args.overwrite)
    return convert_single_file(source_path, args.output_file, args.overwrite)


if __name__ == "__main__":
    raise SystemExit(main())
