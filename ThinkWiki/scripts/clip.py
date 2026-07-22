#!/usr/bin/env python3
from __future__ import annotations

"""
ThinkWiki Script: clip

Purpose:
- Collect a webpage, file, or raw text into the inbox before formal ingest.

Usage:
- Prefer `python scripts/thinkwiki clip ...`.
- Run `python scripts/<script> --help` for direct CLI details when the file exposes its own arguments.
"""


import argparse
import json
import shutil
from pathlib import Path
from urllib import error as urllib_error
from urllib import request as urllib_request
from urllib.parse import urlparse

from url_safety import safe_urlopen, validate_fetch_url

from ingest import (
    clean_markdown,
    extract_title_from_markdown,
    fetch_webpage_capture,
    humanize_name,
    normalize_local_source,
)
from utils import (
    append_log,
    ensure_runtime_dirs,
    file_uri,
    find_repo_root,
    write_inbox_review,
    write_output_home,
    slugify,
    today_str,
    unique_path,
    write_text,
)


def next_ingest_command(root: Path, normalized_path: Path) -> str:
    repo_path = normalized_path.relative_to(root).as_posix()
    return f"python scripts/thinkwiki ingest --root {root} --source {repo_path}"


def write_clip_metadata(path: Path, payload: dict[str, object]) -> Path:
    metadata_path = path.with_suffix(".json")
    write_text(metadata_path, json.dumps(payload, ensure_ascii=False, indent=2))
    return metadata_path


def media_filename(url: str, index: int) -> str:
    parsed = urlparse(url)
    candidate = Path(parsed.path).name or f"image-{index}"
    suffix = Path(candidate).suffix.lower()
    if suffix not in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"}:
        suffix = ".bin"
    stem = slugify(Path(candidate).stem or f"image-{index}", "image")
    return f"{stem}{suffix}"


def download_media(url: str, target: Path) -> bool:
    try:
        validate_fetch_url(url)
    except ValueError:
        return False
    request = urllib_request.Request(url, headers={"User-Agent": "ThinkWiki/1.7.2"})
    try:
        with safe_urlopen(request, timeout=20) as response:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(response.read())
        return True
    except (urllib_error.URLError, ValueError, OSError):
        return False


def localize_markdown_media(root: Path, normalized_path: Path, markdown: str, media_urls: list[str]) -> tuple[str, dict[str, object]]:
    if not media_urls:
        return markdown, {
            "mediaStatus": "none",
            "mediaCount": 0,
            "localizedMediaCount": 0,
            "mediaDir": "",
        }

    asset_dir = root / "normalized" / "assets" / "inbox" / normalized_path.stem
    localized_count = 0
    rewritten = markdown
    for index, media_url in enumerate(media_urls, start=1):
        target = asset_dir / media_filename(media_url, index)
        if not download_media(media_url, target):
            continue
        localized_count += 1
        relative = Path("../assets") / "inbox" / normalized_path.stem / target.name
        rewritten = rewritten.replace(media_url, relative.as_posix())

    status = "localized" if localized_count == len(media_urls) else ("partial" if localized_count else "kept_remote")
    return rewritten, {
        "mediaStatus": status,
        "mediaCount": len(media_urls),
        "localizedMediaCount": localized_count,
        "mediaDir": asset_dir.relative_to(root).as_posix() if localized_count else "",
    }


def clip_local_source(root: Path, source_path: Path, title_override: str) -> tuple[str, Path, Path]:
    normalized_text = normalize_local_source(source_path)
    fallback_title = humanize_name(source_path.stem)
    title = title_override.strip() or extract_title_from_markdown(normalized_text, fallback_title)
    slug = slugify(title, "clip")
    while len(slug.encode("utf-8")) > 200:
        slug = slug[:-1]
    raw_path = unique_path(root / "raw" / "inbox" / f"{today_str()}-{slug}{source_path.suffix.lower()}")
    normalized_path = unique_path(root / "normalized" / "inbox" / f"{today_str()}-{slug}.md")
    shutil.copy2(source_path, raw_path)
    write_text(normalized_path, normalized_text)
    return title, raw_path, normalized_path


def clip_web_source(
    root: Path,
    url: str,
    title_override: str,
    adapter: str,
    mode: str,
    wait_seconds: int,
    media_policy: str,
) -> tuple[str, Path, Path, Path, dict[str, object]]:
    capture = fetch_webpage_capture(url, title_override, adapter=adapter, mode=mode, wait_seconds=wait_seconds)
    normalized_text = str(capture["markdown"])
    raw_html = str(capture["raw_html"])
    parsed = urlparse(url)
    fallback_title = humanize_name(Path(parsed.path).stem or parsed.netloc or "web-clip")
    title = title_override.strip() or extract_title_from_markdown(normalized_text, fallback_title)
    slug = slugify(title, "clip")
    raw_path = unique_path(root / "raw" / "inbox" / f"{today_str()}-{slug}.html")
    normalized_path = unique_path(root / "normalized" / "inbox" / f"{today_str()}-{slug}.md")
    media_urls = json.loads(str(capture.get("media_urls", "[]") or "[]"))
    media_result: dict[str, object]
    if media_policy == "always":
        normalized_text, media_result = localize_markdown_media(root, normalized_path, normalized_text, media_urls)
    elif media_policy == "ask":
        media_result = {
            "mediaStatus": "review_needed" if media_urls else "none",
            "mediaCount": len(media_urls),
            "localizedMediaCount": 0,
            "mediaDir": "",
        }
    else:
        media_result = {
            "mediaStatus": "kept_remote" if media_urls else "none",
            "mediaCount": len(media_urls),
            "localizedMediaCount": 0,
            "mediaDir": "",
        }
    write_text(raw_path, raw_html or f"URL: {url}")
    write_text(normalized_path, normalized_text)
    metadata = {
        "kind": "web",
        "adapter": capture["adapter"],
        "title": capture["title"],
        "siteName": capture["site_name"],
        "author": capture["author"],
        "publishDate": capture["publish_date"],
        "url": capture["url"],
        "captureMode": capture["capture_mode"],
        "captureState": capture["capture_state"],
        "captureReason": capture["capture_reason"],
        "reviewHint": capture["review_hint"],
        "captureAttempts": int(capture["capture_attempts"]),
        "captureElapsedSeconds": float(capture["capture_elapsed_seconds"]),
        "mediaPolicy": media_policy,
        "mediaStatus": media_result["mediaStatus"],
        "mediaCount": media_result["mediaCount"],
        "localizedMediaCount": media_result["localizedMediaCount"],
        "mediaDir": media_result["mediaDir"],
        "normalizedPath": normalized_path.relative_to(root).as_posix(),
        "rawPath": raw_path.relative_to(root).as_posix(),
    }
    metadata_path = write_clip_metadata(normalized_path, metadata)
    return title, raw_path, normalized_path, metadata_path, metadata


def clip_text_source(root: Path, text: str, title_override: str) -> tuple[str, Path, Path]:
    cleaned_text = clean_markdown(text)
    title = title_override.strip() or extract_title_from_markdown(cleaned_text, "Inbox Clip")
    slug = slugify(title, "clip")
    raw_path = unique_path(root / "raw" / "inbox" / f"{today_str()}-{slug}.md")
    normalized_path = unique_path(root / "normalized" / "inbox" / f"{today_str()}-{slug}.md")
    write_text(raw_path, cleaned_text)
    write_text(normalized_path, cleaned_text)
    return title, raw_path, normalized_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Clip a webpage, file, or pasted text into the ThinkWiki inbox.")
    parser.add_argument("--root", default=".", help="Wiki root path")
    parser.add_argument("--source", help="Path to a local source file to clip into inbox")
    parser.add_argument("--url", help="Webpage URL to clip into inbox")
    parser.add_argument("--text", help="Inline text to clip into inbox")
    parser.add_argument("--title", default="", help="Human readable title")
    parser.add_argument("--adapter", default="auto", choices=["auto", "wechat", "generic"], help="Web extraction adapter when using --url")
    parser.add_argument("--mode", default="auto", choices=["auto", "wait"], help="Web capture mode when using --url")
    parser.add_argument("--wait-seconds", default=8, type=int, help="Maximum seconds to poll when --mode wait is used")
    parser.add_argument("--media", default="ask", choices=["ask", "always", "never"], help="How to handle webpage images when using --url")
    args = parser.parse_args()

    provided = [bool(args.source), bool(args.url), bool(args.text)]
    if sum(provided) != 1:
        raise SystemExit("Provide exactly one of --source, --url, or --text")

    root = find_repo_root(Path(args.root))
    ensure_runtime_dirs(root)
    metadata_path: Path | None = None
    metadata: dict[str, object] | None = None
    if args.source:
        source_path = Path(args.source).resolve()
        if not source_path.exists() or not source_path.is_file():
            raise SystemExit(f"Source file not found: {source_path}")
        title, raw_path, normalized_path = clip_local_source(root, source_path, args.title)
    elif args.url:
        title, raw_path, normalized_path, metadata_path, metadata = clip_web_source(
            root,
            args.url,
            args.title,
            args.adapter,
            args.mode,
            args.wait_seconds,
            args.media,
        )
    else:
        title, raw_path, normalized_path = clip_text_source(root, args.text or "", args.title)

    log_lines = [
        f"- raw: {raw_path.relative_to(root).as_posix()}",
        f"- normalized: {normalized_path.relative_to(root).as_posix()}",
        "- next: review the inbox item, then ingest it into wiki/sources when ready",
    ]
    if metadata_path is not None and metadata is not None:
        log_lines.insert(2, f"- metadata: {metadata_path.relative_to(root).as_posix()}")
        log_lines.insert(3, f"- adapter: {metadata.get('adapter', 'auto')}")
        log_lines.insert(4, f"- mode: {metadata.get('captureMode', 'auto')}")
        log_lines.insert(5, f"- state: {metadata.get('captureState', 'ok')}")
        log_lines.insert(6, f"- reason: {metadata.get('captureReason', 'ready')}")
        log_lines.insert(7, f"- media: {metadata.get('mediaStatus', 'none')} ({metadata.get('localizedMediaCount', 0)}/{metadata.get('mediaCount', 0)})")
    append_log(root, f"[{today_str()}] clip | {title}", log_lines)
    print(f"Clipped {title} into inbox")
    print(f"Inbox raw: {raw_path.relative_to(root).as_posix()}")
    print(f"Inbox normalized: {normalized_path.relative_to(root).as_posix()}")
    if metadata_path is not None and metadata is not None:
        print(f"Inbox metadata: {metadata_path.relative_to(root).as_posix()}")
        print(f"Web adapter: {metadata.get('adapter', 'auto')}")
        print(f"Capture mode: {metadata.get('captureMode', 'auto')}")
        print(f"Capture state: {metadata.get('captureState', 'ok')}")
        print(f"Capture reason: {metadata.get('captureReason', 'ready')}")
        print(f"Media status: {metadata.get('mediaStatus', 'none')} ({metadata.get('localizedMediaCount', 0)}/{metadata.get('mediaCount', 0)})")
    inbox_page = write_inbox_review(root)
    output_home = write_output_home(root)
    print("Inbox review: output/inbox/index.html")
    print(f"Inbox review URI: {file_uri(inbox_page)}")
    print("Output hub: output/index.html")
    print(f"Output hub URI: {file_uri(output_home)}")
    print(f"Next: run `{next_ingest_command(root, normalized_path)}`")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
