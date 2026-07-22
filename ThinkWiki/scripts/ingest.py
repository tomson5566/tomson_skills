#!/usr/bin/env python3
from __future__ import annotations

"""
ThinkWiki Script: ingest

Purpose:
- Import a source file, webpage, or inbox item into the wiki and materialize knowledge pages.

Usage:
- Prefer `python scripts/thinkwiki ingest ...`.
- Run `python scripts/<script> --help` for direct CLI details when the file exposes its own arguments.
"""


import argparse
import gzip
import html as html_lib
import json
import os
import re
import shutil
import time
import zlib
from datetime import datetime
from pathlib import Path
from urllib import error as urllib_error
from urllib import request as urllib_request
from urllib.parse import urljoin, urlparse

from url_safety import safe_urlopen, validate_fetch_url

import rebuild_index
from bs4 import BeautifulSoup
from markdownify import markdownify as md
from runtime_capabilities import missing_dependency_message, missing_modules_for_source
from utils import (
    append_log,
    classify_raw_dir,
    entity_label_keys,
    find_repo_root,
    load_template,
    output_access_lines,
    parse_frontmatter,
    read_text,
    render_template,
    slugify,
    today_str,
    unique_path,
    write_text,
)

MARKDOWN_EXTENSIONS = {".md", ".txt", ".markdown"}
META_PREFIXES = ("- 来源：", "- 作者：", "- 发布日期：", "- 原文链接：")
NOISE_MARKERS = (
    "<ama-doc>",
    "文件编号",
    "文档版本",
    "最后修改日期",
    "修订页",
    "编 写 人",
    "编写时间",
    "目录",
    "page ",
)
SUMMARY_SECTION_HINTS = {"摘要", "summary", "abstract", "概述", "方案结论"}
CONTINUATION_ENDINGS = tuple("的了和与及并而按把将向在于为是小会度案等其")
DECISION_SUMMARY_HINTS = ("不适合", "应按", "应采用", "建议采用", "推荐采用", "换句话说", "核心判断")
SKIP_CONCEPT_HEADINGS = {"summary", "key points", "connections", "open questions", "claims", "raw source", "extracted markdown", "extracted excerpt"}
SKIP_ENTITY_LABELS = {
    "summary",
    "key points",
    "key guidance",
    "connections",
    "knowledge connections",
    "claims",
    "open questions",
    "raw source",
    "extracted markdown",
    "extracted excerpt",
}
ENTITY_CANDIDATE_RE = re.compile(r"\b(?:[A-Z][A-Za-z0-9]+|[A-Z]{2,})(?:\s+(?:[A-Z][A-Za-z0-9]+|[A-Z]{2,})){0,2}\b")
WEB_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/137.0.0.0 Safari/537.36"
)
REMOVE_SELECTORS = (
    "script",
    "style",
    "noscript",
    "iframe",
    "form",
    "input",
    "button",
    "svg",
    "canvas",
    "footer",
    "nav",
    ".comment",
    ".comments",
    "#comments",
    ".sidebar",
    ".share",
    ".advertisement",
    ".ads",
    ".related",
)
CONTENT_SELECTORS = (
    "article",
    "main",
    '[role="main"]',
    ".post-content",
    ".entry-content",
    ".article-content",
    ".content",
    "#content",
    ".rich_media_content",
    "body",
)
SUPPORTED_INGEST_EXTENSIONS = MARKDOWN_EXTENSIONS | {".pdf", ".docx", ".xlsx", ".xls", ".pptx"}


def normalize_text(text: str) -> str:
    return " ".join(text.replace("\r\n", "\n").replace("\r", "\n").split())


def plain_text(text: str) -> str:
    text = re.sub(r"!\[[^\]]*\]\([^)]+\)", "", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"[*_`~#>]+", " ", text)
    return normalize_text(text).strip(" -|,;:*")


def body_lines(text: str) -> list[str]:
    lines = text.replace("\r\n", "\n").replace("\r", "\n").splitlines()
    start_index = 0
    if lines and lines[0].strip() == "---":
        for index in range(1, len(lines)):
            if lines[index].strip() == "---":
                start_index = index + 1
                break
    return lines[start_index:]


def clean_markdown(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\xa0", " ")
    lines = [line.rstrip() for line in text.splitlines()]
    cleaned: list[str] = []
    blank_count = 0
    for line in lines:
        if line.strip():
            cleaned.append(line)
            blank_count = 0
        else:
            blank_count += 1
            if blank_count <= 1:
                cleaned.append("")
    return "\n".join(cleaned).strip() + ("\n" if cleaned else "")


def is_table_like_text(text: str) -> bool:
    compact = text.strip()
    if not compact:
        return False
    if compact.count("|") >= 4:
        return True
    lines = [line.strip() for line in compact.splitlines() if line.strip()]
    if lines and sum(1 for line in lines if "|" in line) >= max(2, len(lines) // 2 + 1):
        return True
    return False


def is_toc_like_text(text: str) -> bool:
    compact = plain_text(text)
    if not compact:
        return False
    if compact.startswith(("1.", "1.1", "2.", "2.1")) and len(compact) <= 40:
        return True
    if re.match(r"^\d+(?:\.\d+){0,3}\s*[\u4e00-\u9fffA-Za-z].*\d+$", compact):
        return True
    return False


def is_page_marker(text: str) -> bool:
    compact = plain_text(text).lower()
    return bool(re.fullmatch(r"page\s+\d+", compact))


def is_noise_line(text: str) -> bool:
    compact = plain_text(text)
    if not compact:
        return True
    lowered = compact.lower()
    if lowered.startswith(NOISE_MARKERS):
        return True
    if compact in {"---", "***"}:
        return True
    if is_page_marker(compact):
        return True
    if is_table_like_text(text):
        return True
    if is_toc_like_text(compact):
        return True
    return False


def looks_like_list_item(text: str) -> bool:
    compact = plain_text(text)
    return bool(re.match(r"^(?:\d+[\.\)、]|[一二三四五六七八九十]+[、\.])", compact))


def is_cover_like_text(text: str) -> bool:
    compact = plain_text(text)
    if not compact:
        return True
    if compact.startswith(("日期：", "日期:")) and len(compact) <= 24:
        return True
    if re.match(r"^[一二三四五六七八九十]+、", compact) and len(compact) <= 20:
        return True
    if len(compact) <= 24 and not any(punct in compact for punct in ("。", "！", "？", "；", ":", "：")):
        return True
    return False


def cleaned_content_blocks(text: str) -> list[dict[str, object]]:
    blocks: list[dict[str, object]] = []
    block_lines: list[str] = []
    current_section = ""

    def flush_block() -> None:
        nonlocal block_lines
        if not block_lines:
            return
        joined = " ".join(block_lines).strip()
        block_lines = []
        if not joined:
            return
        blocks.append({
            "section": current_section,
            "text": joined,
            "index": len(blocks),
        })

    for raw in body_lines(text):
        stripped = raw.strip()
        if not stripped or stripped == "---":
            flush_block()
            continue
        if stripped.startswith("#"):
            flush_block()
            current_section = plain_text(stripped.lstrip("#").strip())
            continue
        if stripped.startswith("![]("):
            continue
        if stripped.startswith(META_PREFIXES):
            continue
        if stripped.startswith(("```", "<!--")):
            continue
        if stripped.startswith(("更新时间", "更新于", "Published:", "Updated:")):
            continue
        if stripped.startswith(("http://", "https://")) and len(stripped) > 80:
            continue
        cleaned = plain_text(stripped.lstrip("-* ").strip())
        if not cleaned or is_noise_line(cleaned):
            flush_block()
            continue
        block_lines.append(cleaned)
    flush_block()
    return blocks


def merge_adjacent_blocks(blocks: list[dict[str, object]]) -> list[dict[str, object]]:
    if not blocks:
        return []
    merged: list[dict[str, object]] = []
    current = dict(blocks[0])
    for block in blocks[1:]:
        current_text = str(current["text"])
        next_text = str(block["text"])
        same_section = str(current["section"]) == str(block["section"])
        current_ends_incomplete = not current_text.endswith(("。", "！", "？", "；", ".", "!", "?", ";", ":", "："))
        current_ends_incomplete = current_ends_incomplete or current_text.endswith(CONTINUATION_ENDINGS)
        next_is_continuation = not looks_like_list_item(next_text)
        next_is_short = len(next_text) <= 36
        if same_section and not is_cover_like_text(current_text) and not is_cover_like_text(next_text) and next_is_continuation and (current_ends_incomplete or next_is_short):
            current["text"] = f"{current_text} {next_text}".strip()
            continue
        merged.append(current)
        current = dict(block)
    merged.append(current)
    for index, block in enumerate(merged):
        block["index"] = index
    return merged


def cleaned_content_lines(text: str) -> list[str]:
    return [str(block["text"]) for block in merge_adjacent_blocks(cleaned_content_blocks(text))]


def summary_block_score(block: dict[str, object]) -> int:
    text = str(block["text"])
    section = str(block["section"]).strip().lower()
    index = int(block["index"])
    score = 0
    if section in SUMMARY_SECTION_HINTS:
        score += 14
    score += max(0, 6 - min(index, 6))
    if len(text) >= 40:
        score += 8
    if len(text) >= 80:
        score += 5
    if len(text) >= 160:
        score += 3
    if len(text) < 20:
        score -= 12
    elif len(text) < 40:
        score -= 4
    if looks_like_list_item(text):
        score -= 10
    if text.endswith(("：", ":")):
        score -= 6
    if any(punct in text for punct in ("。", "；", ":", "：")):
        score += 3
    if any(hint in text for hint in DECISION_SUMMARY_HINTS):
        score += 8
    if section and section in text.lower():
        score -= 2
    if index <= 2 and section not in SUMMARY_SECTION_HINTS:
        score -= 3
    if is_noise_line(text):
        score -= 20
    return score


def trim_summary_tail(text: str) -> str:
    trimmed = text.strip()
    trimmed = re.sub(r"\s+(?:建议采用|建议如下|如下|其中|包括|可分为)[:：]\s*$", "", trimmed)
    if trimmed.endswith(("：", ":")):
        sentence_end = max(trimmed.rfind("。"), trimmed.rfind("！"), trimmed.rfind("？"), trimmed.rfind(";"), trimmed.rfind("；"))
        if sentence_end != -1:
            trimmed = trimmed[: sentence_end + 1]
    return trimmed.strip()


def summarize(text: str) -> tuple[str, list[str]]:
    blocks = merge_adjacent_blocks(cleaned_content_blocks(text))
    if not blocks:
        return "Imported source.", []
    scored_blocks = [(summary_block_score(block), block) for block in blocks]
    high_quality_blocks = [block for score, block in scored_blocks if score >= 8]
    best_block = high_quality_blocks[0] if high_quality_blocks else max(scored_blocks, key=lambda item: item[0])[1]
    ranked_blocks = [block for _score, block in sorted(scored_blocks, key=lambda item: (-item[0], int(item[1]["index"])))]
    summary = trim_summary_tail(str(best_block["text"]))[:140] if summary_block_score(best_block) > -10 else "Imported source."
    bullets: list[str] = []
    used: set[str] = set()
    for block in ranked_blocks:
        text_value = str(block["text"])
        if text_value == summary or text_value in used:
            continue
        if summary_block_score(block) < 0:
            continue
        if len(text_value) < 12:
            continue
        bullets.append(text_value[:120])
        used.add(text_value)
        if len(bullets) >= 4:
            break
    if not bullets and summary != "Imported source.":
        bullets.append(summary[:120])
    return summary, bullets[:4]


def excerpt_markdown(text: str, max_lines: int = 18, max_chars: int = 1600) -> str:
    excerpt_lines: list[str] = []
    current_chars = 0
    content_started = False
    for raw in body_lines(text):
        line = raw.rstrip()
        stripped = line.strip()
        if stripped == "---":
            if content_started:
                break
            continue
        if stripped.startswith(META_PREFIXES):
            continue
        if stripped.startswith("![]("):
            continue
        if is_page_marker(stripped):
            continue
        if stripped.startswith(("http://", "https://")):
            continue
        if stripped and is_noise_line(stripped):
            continue
        if not stripped and not excerpt_lines:
            continue
        if stripped and not stripped.startswith("#"):
            content_started = True
        excerpt_lines.append(line)
        current_chars += len(line)
        if len(excerpt_lines) >= max_lines or current_chars >= max_chars:
            break
    excerpt = "\n".join(excerpt_lines).strip()
    return excerpt or "_No excerpt available._"


def extract_title_from_markdown(text: str, fallback: str) -> str:
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("# "):
            title = plain_text(line[2:].strip())
            if title:
                return title
    for block in cleaned_content_blocks(text):
        candidate = str(block["text"]).strip()
        if not candidate:
            continue
        if looks_like_list_item(candidate):
            continue
        if len(candidate) > 60:
            continue
        if candidate.endswith(("：", ":")):
            continue
        return candidate[:120]
    blocks = merge_adjacent_blocks(cleaned_content_blocks(text))
    if blocks:
        return str(blocks[0]["text"])[:60]
    return fallback


def humanize_name(value: str) -> str:
    return value.replace("-", " ").replace("_", " ").strip().title()


def ensure_local_source_dependencies(source_path: Path) -> None:
    missing = missing_modules_for_source(source_path)
    if missing:
        raise SystemExit(missing_dependency_message(source_path, missing))


def convert_with_markitdown(source_path: Path) -> str:
    ensure_local_source_dependencies(source_path)
    try:
        from markitdown import MarkItDown
    except Exception as exc:
        raise SystemExit(
            "markitdown Python package is not available. "
            "Install ThinkWiki runtime dependencies before converting office documents."
        ) from exc
    try:
        result = MarkItDown().convert(str(source_path))
    except Exception as exc:
        raise SystemExit(f"markitdown failed for {source_path.name}: {exc}") from exc
    content = getattr(result, "text_content", "") or getattr(result, "markdown", "")
    if not str(content).strip():
        raise SystemExit(f"markitdown failed for {source_path.name}: empty output")
    return clean_markdown(str(content))


def fetch_raw_html(url: str, timeout: int = 30) -> str:
    try:
        validate_fetch_url(url)
    except ValueError:
        return ""
    request = urllib_request.Request(
        url,
        headers={
            "User-Agent": WEB_USER_AGENT,
            "Accept-Encoding": "gzip, deflate",
        },
    )
    try:
        with safe_urlopen(request, timeout=timeout) as response:
            raw_bytes = response.read()
            content_encoding = (response.headers.get("Content-Encoding") or "").lower()
            if "gzip" in content_encoding:
                raw_bytes = gzip.decompress(raw_bytes)
            elif "deflate" in content_encoding:
                raw_bytes = zlib.decompress(raw_bytes)
            charset = response.headers.get_content_charset() or "utf-8"
            return raw_bytes.decode(charset, errors="replace")
    except (urllib_error.URLError, ValueError, OSError, gzip.BadGzipFile, zlib.error):
        return ""


def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def detect_wechat(url: str, soup: BeautifulSoup) -> bool:
    if "mp.weixin.qq.com" in url:
        return True
    return soup.select_one("#js_content") is not None


def resolve_web_adapter(url: str, soup: BeautifulSoup, requested: str = "auto") -> str:
    normalized = requested.strip().lower() or "auto"
    if normalized not in {"auto", "wechat", "generic"}:
        raise SystemExit(f"Unsupported web adapter: {requested}")
    if normalized != "auto":
        return normalized
    if detect_wechat(url, soup):
        return "wechat"
    return "generic"


def find_meta_content(soup: BeautifulSoup, key: str, attr: str = "name") -> str:
    node = soup.find("meta", attrs={attr: key})
    if node and node.get("content"):
        return clean_text(html_lib.unescape(str(node["content"])))
    return ""


def parse_publish_date_from_timestamp(raw: str) -> str:
    if not raw:
        return ""
    try:
        return datetime.fromtimestamp(int(raw)).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return raw


def extract_wechat_metadata(
    soup: BeautifulSoup, raw_html: str, url: str
) -> tuple[str, str, str, str, BeautifulSoup]:
    title_node = soup.select_one("#activity-name .js_title_inner") or soup.select_one("#activity-name")
    author_node = soup.select_one("#js_author_name_text") or soup.select_one("#js_author_name")
    account_node = soup.select_one("#js_name")
    content_node = soup.select_one("#js_content")

    title = clean_text(title_node.get_text(" ", strip=True)) if title_node else ""
    author = clean_text(author_node.get_text(" ", strip=True)) if author_node else ""
    account = clean_text(account_node.get_text(" ", strip=True)) if account_node else ""

    ts_match = re.search(r'var\s+ct\s*=\s*"(\d+)"', raw_html)
    publish_date = parse_publish_date_from_timestamp(ts_match.group(1) if ts_match else "")
    if content_node is None:
        raise SystemExit(f"Unable to locate WeChat content node for {url}")
    return title, author, account, publish_date, content_node


def extract_generic_metadata(soup: BeautifulSoup, url: str) -> tuple[str, str, str, str, BeautifulSoup]:
    title = ""
    h1 = soup.find("h1")
    if h1:
        title = clean_text(h1.get_text(" ", strip=True))
    if not title:
        title = find_meta_content(soup, "og:title", attr="property")
    if not title and soup.title:
        title = clean_text(soup.title.get_text(" ", strip=True))

    author = (
        find_meta_content(soup, "author")
        or find_meta_content(soup, "article:author", attr="property")
        or find_meta_content(soup, "og:article:author", attr="property")
    )
    site_name = find_meta_content(soup, "og:site_name", attr="property") or urlparse(url).netloc
    publish_date = (
        find_meta_content(soup, "article:published_time", attr="property")
        or find_meta_content(soup, "publish_date")
        or find_meta_content(soup, "pubdate")
        or find_meta_content(soup, "date")
    )

    content_node = None
    for selector in CONTENT_SELECTORS:
        content_node = soup.select_one(selector)
        if content_node and clean_text(content_node.get_text(" ", strip=True)):
            break
    if content_node is None:
        raise SystemExit(f"Unable to locate main content node for {url}")
    return title or "webpage", author, site_name, publish_date, content_node


def normalize_images(content_node: BeautifulSoup) -> None:
    for img in content_node.select("img"):
        src = (
            img.get("data-src")
            or img.get("data-original")
            or img.get("data-url")
            or img.get("data-croporisrc")
            or img.get("src")
        )
        if src:
            img["src"] = html_lib.unescape(src)
        alt = img.get("alt")
        if alt:
            img["alt"] = clean_text(alt)


def collect_media_urls(content_node: BeautifulSoup, base_url: str) -> list[str]:
    urls: list[str] = []
    seen: set[str] = set()
    for img in content_node.select("img"):
        src = clean_text(str(img.get("src", "") or ""))
        if not src:
            continue
        absolute = urljoin(base_url, src)
        img["src"] = absolute
        if absolute in seen:
            continue
        seen.add(absolute)
        urls.append(absolute)
    return urls


def normalize_wechat_code_blocks(content_node: BeautifulSoup) -> None:
    selectors = (
        ".js_code_area",
        ".code-snippet__js",
        ".code-snippet",
        "pre[data-lang]",
        "pre[data-language]",
    )
    seen: set[int] = set()
    for selector in selectors:
        for node in content_node.select(selector):
            marker = id(node)
            if marker in seen:
                continue
            seen.add(marker)
            code_node = node.select_one("code") or node.select_one("pre") or node
            code_text = code_node.get_text("\n", strip=False)
            if not clean_text(code_text):
                continue
            language = (
                node.get("data-lang")
                or node.get("data-language")
                or code_node.get("data-lang")
                or code_node.get("data-language")
                or ""
            )
            classes = list(node.get("class", [])) + list(code_node.get("class", []))
            for class_name in classes:
                if class_name.startswith("language-"):
                    language = class_name.split("-", 1)[1]
                    break
            pre = content_node.new_tag("pre")
            code = content_node.new_tag("code")
            if language:
                code["class"] = [f"language-{language.strip().lower()}"]
            code.string = code_text.strip("\n")
            pre.append(code)
            node.replace_with(pre)


def remove_noise(content_node: BeautifulSoup) -> None:
    for selector in REMOVE_SELECTORS:
        for node in content_node.select(selector):
            node.decompose()


def html_to_markdown(content_node: BeautifulSoup) -> str:
    raw_markdown = md(str(content_node), heading_style="ATX", bullets="-", strip=["script", "style"])
    return clean_markdown(raw_markdown)


def build_web_header(title: str, site_name: str, author: str, publish_date: str, url: str) -> str:
    lines = [f"# {title}", ""]
    if site_name:
        lines.append(f"- 来源：{site_name}")
    if author:
        lines.append(f"- 作者：{author}")
    if publish_date:
        lines.append(f"- 发布日期：{publish_date}")
    lines.append(f"- 原文链接：{url}")
    lines.extend(["", "---", ""])
    return "\n".join(lines)


def capture_ready(markdown: str) -> bool:
    blocks = cleaned_content_blocks(markdown)
    body = plain_text("\n".join(body_lines(markdown)))
    if len(body) >= 160:
        return True
    if len(body) >= 80 and len(blocks) >= 2:
        return True
    return False


def analyze_capture_reason(
    *,
    markdown: str,
    title: str,
    site_name: str,
    author: str,
    publish_date: str,
) -> tuple[str, str]:
    body = plain_text("\n".join(body_lines(markdown))).lower()
    blocks = cleaned_content_blocks(markdown)
    if any(marker in body for marker in ("loading", "加载中", "please wait", "稍后再试")):
        return "loading_placeholder", "页面内容看起来仍像加载占位，建议稍后重试或改用 wait 模式。"
    if len(body) < 40:
        return "body_too_short", "正文过短，建议优先人工检查页面是否真的完成加载。"
    if len(blocks) < 2 and len(body) < 120:
        return "sparse_structure", "正文结构较稀疏，建议复核是否抓到了真正的主内容区域。"
    meta_hits = sum(1 for value in (title, site_name, author, publish_date) if str(value).strip())
    if meta_hits <= 1:
        return "metadata_sparse", "来源元数据较少，建议核对标题、作者和发布时间。"
    return "ready", "采集结果结构完整，可继续复核后正式 ingest。"


def build_capture_result(
    *,
    url: str,
    raw_html: str,
    title_override: str,
    adapter: str,
) -> dict[str, str]:
    soup = BeautifulSoup(raw_html, "html.parser")
    resolved_adapter = resolve_web_adapter(url, soup, adapter)
    if resolved_adapter == "wechat":
        title, author, site_name, publish_date, content_node = extract_wechat_metadata(soup, raw_html, url)
    else:
        title, author, site_name, publish_date, content_node = extract_generic_metadata(soup, url)
    if title_override.strip():
        title = title_override.strip()
    remove_noise(content_node)
    if resolved_adapter == "wechat":
        normalize_wechat_code_blocks(content_node)
    normalize_images(content_node)
    media_urls = collect_media_urls(content_node, url)
    markdown = html_to_markdown(content_node)
    capture_state = "ok" if capture_ready(markdown) else "needs_review"
    capture_reason, review_hint = analyze_capture_reason(
        markdown=markdown,
        title=title,
        site_name=site_name,
        author=author,
        publish_date=publish_date,
    )
    return {
        "adapter": resolved_adapter,
        "title": title,
        "author": author,
        "site_name": site_name,
        "publish_date": publish_date,
        "url": url,
        "markdown": build_web_header(title, site_name, author, publish_date, url) + markdown,
        "raw_html": raw_html,
        "capture_state": capture_state,
        "capture_reason": capture_reason,
        "review_hint": review_hint,
        "media_urls": json.dumps(media_urls, ensure_ascii=False),
    }


def fetch_webpage_capture(
    url: str,
    title_override: str = "",
    adapter: str = "auto",
    mode: str = "auto",
    wait_seconds: int = 8,
) -> dict[str, str]:
    normalized_mode = mode.strip().lower() or "auto"
    if normalized_mode not in {"auto", "wait"}:
        raise SystemExit(f"Unsupported capture mode: {mode}")

    started = time.time()
    attempts = 0
    last_capture: dict[str, str] | None = None
    deadline = started + max(wait_seconds, 0)
    while True:
        attempts += 1
        raw_html = fetch_raw_html(url)
        if raw_html.strip():
            last_capture = build_capture_result(
                url=url,
                raw_html=raw_html,
                title_override=title_override,
                adapter=adapter,
            )
            if normalized_mode == "auto" or str(last_capture.get("capture_state", "")) == "ok":
                break
        if normalized_mode != "wait" or time.time() >= deadline:
            break
        time.sleep(1.0)

    if last_capture is None:
        raise SystemExit(f"Failed to fetch webpage HTML for {url}")
    elapsed = max(0.0, time.time() - started)
    final_state = str(last_capture.get("capture_state", "") or "needs_review")
    if normalized_mode == "wait":
        if final_state == "ok" and attempts > 1:
            final_state = "wait_completed"
        elif final_state != "ok":
            final_state = "wait_timeout"
    last_capture["capture_state"] = final_state
    last_capture["capture_mode"] = normalized_mode
    last_capture["capture_attempts"] = str(attempts)
    last_capture["capture_elapsed_seconds"] = "{:.1f}".format(elapsed)
    return last_capture


def fetch_webpage_as_markdown(url: str, title_override: str = "") -> tuple[str, str]:
    capture = fetch_webpage_capture(url, title_override)
    return capture["markdown"], capture["raw_html"]


def normalize_local_source(source_path: Path) -> str:
    suffix = source_path.suffix.lower()
    if suffix in MARKDOWN_EXTENSIONS:
        return clean_markdown(read_text(source_path))
    return convert_with_markitdown(source_path)


def build_link(path: Path, root: Path) -> str:
    repo_path = path.relative_to(root).as_posix()
    return f"- [{path.name}](../../{repo_path})"


def ordered_unique(items: list[str]) -> list[str]:
    results: list[str] = []
    seen: set[str] = set()
    for item in items:
        value = item.strip()
        if not value or value in seen:
            continue
        seen.add(value)
        results.append(value)
    return results


def extract_section(body: str, heading: str) -> str:
    lines = body.splitlines()
    capture = False
    collected: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("## "):
            current = stripped[3:].strip()
            if capture:
                break
            capture = current == heading
            continue
        if capture:
            collected.append(line)
    return "\n".join(collected).strip()


def source_items_block(source_paths: list[str]) -> str:
    return "\n".join(f"  - {path}" for path in source_paths)


def source_links_block(topic_path: Path, root: Path, source_paths: list[str]) -> str:
    lines: list[str] = []
    for source_path in source_paths:
        target_path = root / source_path
        relative = Path(os.path.relpath(target_path, start=topic_path.parent)).as_posix()
        lines.append(f"- [{target_path.stem}]({relative})")
    return "\n".join(lines)


def yaml_list_block(items: list[str]) -> str:
    if not items:
        return ""
    return "\n".join(f"  - {item}" for item in items)


def meta_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if value:
        return [str(value).strip()]
    return []


def existing_page_index(root: Path) -> dict[str, str]:
    index: dict[str, str] = {}
    for page in sorted((root / "wiki").rglob("*.md")):
        relative = page.relative_to(root).as_posix()
        meta, _body = parse_frontmatter(read_text(page))
        title = str(meta.get("title") or page.stem).strip()
        for key in {relative.casefold(), page.stem.casefold(), title.casefold()}:
            if key:
                index[key] = relative
    return index


def heading_candidates(text: str) -> list[str]:
    candidates: list[str] = []
    for raw in body_lines(text):
        stripped = raw.strip()
        if not stripped.startswith(("## ", "### ")):
            continue
        heading = plain_text(stripped.lstrip("#").strip())
        if not heading:
            continue
        lowered = heading.casefold()
        if lowered in SKIP_CONCEPT_HEADINGS:
            continue
        if len(heading) < 3 or len(heading) > 48:
            continue
        candidates.append(heading)
    return ordered_unique(candidates)[:4]


def resolve_related_concepts(root: Path, normalized_text: str) -> list[dict[str, str]]:
    page_index = existing_page_index(root)
    concepts: list[dict[str, str]] = []
    for heading in heading_candidates(normalized_text):
        target = page_index.get(heading.casefold(), "")
        if not target.startswith("wiki/concepts/"):
            continue
        concepts.append({"title": heading, "path": target})
    return concepts[:4]


def extract_entities(
    normalized_text: str,
    *,
    title: str,
    topic_name: str,
    concept_items: list[dict[str, str]],
) -> list[str]:
    concept_titles = {item["title"].casefold() for item in concept_items}
    blocked_labels = {
        title.strip().casefold(),
        topic_name.strip().casefold(),
        *concept_titles,
    }
    occurrence_count: dict[str, int] = {}
    segments = [str(block["text"]) for block in merge_adjacent_blocks(cleaned_content_blocks(normalized_text))]
    if not segments:
        segments = [normalized_text]
    for segment in segments:
        for match in ENTITY_CANDIDATE_RE.findall(segment):
            candidate = match.strip()
            if candidate:
                occurrence_count[candidate] = occurrence_count.get(candidate, 0) + 1

    entities: list[str] = []
    for candidate, count in occurrence_count.items():
        normalized = plain_text(candidate)
        if not normalized:
            continue
        lowered = normalized.casefold()
        if lowered in blocked_labels or lowered in SKIP_ENTITY_LABELS:
            continue
        if len(normalized) < 3 or len(normalized) > 40:
            continue
        parts = normalized.split()
        if len(parts) == 1:
            token = parts[0]
            strong_shape = (
                bool(re.search(r"[a-z][A-Z]", token))
                or token.isupper()
                or any(char.isdigit() for char in token)
                or token.endswith("AI")
                or token.startswith("Think")
            )
            if not strong_shape and count < 2:
                continue
        entities.append(normalized)
    return ordered_unique(entities)[:4]


def claim_items(summary: str, bullets: list[str]) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    if summary and summary != "Imported source.":
        items.append({"text": summary, "confidence": "high"})
    for bullet in bullets:
        if not bullet or bullet == summary:
            continue
        items.append({"text": bullet, "confidence": "medium"})
    deduped: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in items:
        key = item["text"].strip().casefold()
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped[:3]


def frontmatter_claim_block(items: list[dict[str, str]]) -> str:
    if not items:
        return ""
    lines: list[str] = []
    for item in items:
        lines.append(f"  - text: {item['text']}")
        lines.append(f"    confidence: {item['confidence']}")
    return "\n".join(lines)


def markdown_claim_block(items: list[dict[str, str]]) -> str:
    if not items:
        return "- (pending)"
    return "\n".join(f"- [{item['confidence']}] {item['text']}" for item in items)


def markdown_link_block(page_path: Path, items: list[tuple[str, Path | None]]) -> str:
    lines: list[str] = []
    for label, target_path in items:
        clean_label = label.strip()
        if not clean_label:
            continue
        if target_path is None:
            lines.append(f"- {clean_label}")
            continue
        relative = Path(os.path.relpath(target_path, start=page_path.parent)).as_posix()
        lines.append(f"- [{clean_label}]({relative})")
    return "\n".join(lines) if lines else "- (pending)"


def find_existing_entity_page(root: Path, entity_label: str) -> Path | None:
    entity_dir = root / "wiki" / "entities"
    normalized_label = plain_text(entity_label).strip()
    if not normalized_label:
        return None
    slug_candidate = entity_dir / f"{slugify(normalized_label, 'entity')}.md"
    if slug_candidate.exists():
        return slug_candidate
    if not entity_dir.exists():
        return None
    candidate_keys = set(entity_label_keys(normalized_label))
    if not candidate_keys:
        return None
    matches: list[tuple[int, Path]] = []
    for page in sorted(entity_dir.glob("*.md")):
        meta, _body = parse_frontmatter(read_text(page))
        canonical_target = str(meta.get("canonical_entity") or "").strip()
        candidate_page = page
        if str(meta.get("status") or "").strip().casefold() == "merged" and canonical_target:
            canonical_path = root / canonical_target
            if canonical_path.exists():
                candidate_page = canonical_path
        labels = [
            str(meta.get("title") or page.stem).strip(),
            *meta_list(meta.get("aliases", [])),
        ]
        page_keys: set[str] = set()
        for label in labels:
            page_keys.update(entity_label_keys(plain_text(label).strip()))
        overlap = candidate_keys & page_keys
        if overlap:
            matches.append((len(overlap), candidate_page))
    if not matches:
        return None
    matches.sort(key=lambda item: (-item[0], item[1].as_posix()))
    deduped_matches: list[tuple[int, Path]] = []
    seen_paths: set[str] = set()
    for score, match_path in matches:
        key = match_path.as_posix()
        if key in seen_paths:
            continue
        seen_paths.add(key)
        deduped_matches.append((score, match_path))
    matches = deduped_matches
    if len(matches) > 1 and matches[0][0] == matches[1][0]:
        return None
    return matches[0][1]


def ensure_entity_page(
    root: Path,
    entity_label: str,
    source_page: Path,
    topic_name: str,
    topic_page: Path | None,
) -> dict[str, str]:
    normalized_label = plain_text(entity_label).strip()
    existing_page = find_existing_entity_page(root, normalized_label)
    entity_path = existing_page or (root / "wiki" / "entities" / f"{slugify(normalized_label, 'entity')}.md")
    existing_meta: dict[str, object] = {}
    if entity_path.exists():
        existing_meta, _body = parse_frontmatter(read_text(entity_path))

    entity_title = str(existing_meta.get("title") or normalized_label).strip() or normalized_label
    entity_summary = str(existing_meta.get("summary") or "").strip() or f"{entity_title} is an entity tracked in ThinkWiki."
    created = str(existing_meta.get("created") or today_str()).strip() or today_str()
    source_repo_path = source_page.relative_to(root).as_posix()
    merged_sources = ordered_unique(meta_list(existing_meta.get("sources", [])) + [source_repo_path])
    merged_aliases = ordered_unique(
        meta_list(existing_meta.get("aliases", []))
        + ([normalized_label] if normalized_label.casefold() != entity_title.casefold() else [])
    )
    merged_topics = ordered_unique(
        meta_list(existing_meta.get("topics", []))
        + ([topic_name.strip()] if topic_name.strip() else [])
    )
    content = render_template(load_template("pages/entity.md"), {
        "TITLE": entity_title,
        "DATE": created,
        "UPDATED": today_str(),
        "SUMMARY": entity_summary,
        "SOURCE_ITEMS": source_items_block(merged_sources),
        "SOURCE_LINKS": source_links_block(entity_path, root, merged_sources),
        "ALIAS_ITEMS": yaml_list_block(merged_aliases),
        "ALIAS_MARKDOWN": "\n".join(f"- {item}" for item in merged_aliases) or "- (pending)",
        "TOPIC_ITEMS": yaml_list_block(merged_topics),
        "TOPIC_LINKS": markdown_link_block(
            entity_path,
            [(topic_name.strip(), topic_page)] if topic_name.strip() else [],
        ),
    })
    write_text(entity_path, content)
    return {
        "title": entity_title,
        "path": entity_path.relative_to(root).as_posix(),
    }


def source_connection_links(
    *,
    topic_name: str,
    topic_page: Path | None,
    concept_items: list[dict[str, str]],
    entity_pages: list[dict[str, str]],
) -> str:
    lines: list[str] = []
    if topic_name and topic_page is not None:
        lines.append(f"- belongs_to: [[{topic_name}]]")
    for item in concept_items:
        lines.append(f"- related_to: [[{item['title']}]]")
    for item in entity_pages:
        lines.append(f"- about: [[{item['title']}]]")
    return "\n".join(lines) if lines else "- (pending)"


def render_source_page_content(
    *,
    root: Path,
    source_page: Path,
    title: str,
    date: str,
    summary: str,
    raw_path: Path,
    normalized_path: Path,
    normalized_text: str,
    bullets: list[str],
    related_links: str,
    topic_name: str,
    concept_items: list[dict[str, str]],
    entity_items: list[str],
    entity_pages: list[dict[str, str]],
    topic_page: Path | None,
    confidence: str,
    status: str,
) -> str:
    claims = claim_items(summary, bullets)
    entity_markdown = markdown_link_block(
        source_page,
        [
            (
                item["title"],
                root / str(item["path"]),
            )
            for item in entity_pages
        ],
    ) if entity_pages else "\n".join(f"- {item}" for item in entity_items) or "- (pending)"
    return render_template(load_template("pages/source.md"), {
        "TITLE": title,
        "DATE": date,
        "SUMMARY": summary,
        "RAW_PATH": raw_path.relative_to(root).as_posix(),
        "TOPIC_ITEMS": yaml_list_block([topic_name] if topic_name else []),
        "ENTITY_ITEMS": yaml_list_block(entity_items),
        "CONCEPT_ITEMS": yaml_list_block([item["title"] for item in concept_items]),
        "CLAIM_ITEMS": frontmatter_claim_block(claims),
        "KEY_POINTS": "\n".join(f"- {item}" for item in bullets) or "- (pending)",
        "RAW_LINKS": build_link(raw_path, root),
        "NORMALIZED_LINKS": build_link(normalized_path, root),
        "EXTRACTED_EXCERPT": excerpt_markdown(normalized_text),
        "RELATED_LINKS": related_links,
        "ENTITY_MARKDOWN": entity_markdown,
        "CONNECTION_ITEMS": source_connection_links(
            topic_name=topic_name,
            topic_page=topic_page,
            concept_items=concept_items,
            entity_pages=entity_pages,
        ),
        "CLAIM_MARKDOWN": markdown_claim_block(claims),
        "OPEN_QUESTIONS": "",
        "CONFIDENCE": confidence,
        "STATUS": status,
    })


def find_existing_source_page(root: Path, title: str, slug: str) -> Path | None:
    page_dir = root / "wiki" / "sources"
    slug_candidate = page_dir / f"{slug}.md"
    if slug_candidate.exists():
        return slug_candidate
    for page in sorted(page_dir.glob("*.md")):
        meta, _body = parse_frontmatter(read_text(page))
        if str(meta.get("title") or "").strip() == title.strip():
            return page
    return None


def ensure_topic_page(root: Path, topic: str, source_page: Path, summary: str) -> Path:
    topic_slug = slugify(topic, "topic")
    topic_path = root / "wiki" / "topics" / f"{topic_slug}.md"
    source_repo_path = source_page.relative_to(root).as_posix()
    existing_meta: dict[str, object] = {}
    related_links = ""
    if topic_path.exists():
        existing_meta, body = parse_frontmatter(read_text(topic_path))
        related_links = extract_section(body, "Related Pages")

    raw_sources = existing_meta.get("sources", [])
    existing_sources = [str(item).strip() for item in raw_sources] if isinstance(raw_sources, list) else []
    merged_sources = ordered_unique(existing_sources + [source_repo_path])
    topic_title = str(existing_meta.get("title") or topic).strip() or topic
    topic_summary = str(existing_meta.get("summary") or "").strip() or summary
    created = str(existing_meta.get("created") or today_str()).strip() or today_str()
    content = render_template(load_template("pages/topic.md"), {
        "TITLE": topic_title,
        "DATE": created,
        "UPDATED": today_str(),
        "SUMMARY": topic_summary,
        "SOURCE_ITEMS": source_items_block(merged_sources),
        "SOURCE_LINKS": source_links_block(topic_path, root, merged_sources),
        "RELATED_LINKS": related_links,
    })
    write_text(topic_path, content)
    return topic_path


def ingest_local_source(
    root: Path,
    source_path: Path,
    title_override: str = "",
    topic: str = "",
    confidence: str = "",
    status: str = "",
) -> dict[str, object]:
    raw_dir = classify_raw_dir(source_path)
    normalized_text = normalize_local_source(source_path)
    fallback_title = humanize_name(source_path.stem)
    title = title_override.strip() or extract_title_from_markdown(normalized_text, fallback_title)
    slug = slugify(title, "source")
    while len(slug.encode("utf-8")) > 200:
        slug = slug[:-1]
    raw_path = unique_path(root / "raw" / raw_dir / f"{today_str()}-{slug}{source_path.suffix.lower()}")
    normalized_path = unique_path(root / "normalized" / raw_dir / f"{today_str()}-{slug}.md")
    shutil.copy2(source_path, raw_path)
    write_text(normalized_path, normalized_text)

    summary, bullets = summarize(normalized_text)
    source_page = find_existing_source_page(root, title, slug) or (root / "wiki" / "sources" / f"{slug}.md")
    related_links = ""
    touched = [source_page.relative_to(root).as_posix()]
    topic_page: Path | None = None
    if topic.strip():
        topic_page = ensure_topic_page(root, topic.strip(), source_page, summary)
        related_links = f"- [{topic.strip()}](../topics/{topic_page.name})"
        touched.append(topic_page.relative_to(root).as_posix())

    resolved_confidence = confidence.strip() or "extracted"
    resolved_status = status.strip() or "active"
    concept_items = resolve_related_concepts(root, normalized_text)
    entity_items = extract_entities(
        normalized_text,
        title=title,
        topic_name=topic.strip(),
        concept_items=concept_items,
    )
    entity_pages = [
        ensure_entity_page(
            root,
            entity_label,
            source_page,
            topic.strip(),
            topic_page,
        )
        for entity_label in entity_items
    ]
    touched.extend(
        item["path"]
        for item in entity_pages
        if item["path"] not in touched
    )
    source_content = render_source_page_content(
        root=root,
        source_page=source_page,
        title=title,
        date=today_str(),
        summary=summary,
        raw_path=raw_path,
        normalized_path=normalized_path,
        normalized_text=normalized_text,
        bullets=bullets,
        related_links=related_links,
        topic_name=topic.strip(),
        concept_items=concept_items,
        entity_items=entity_items,
        entity_pages=entity_pages,
        topic_page=topic_page,
        confidence=resolved_confidence,
        status=resolved_status,
    )
    write_text(source_page, source_content)
    return {
        "title": title,
        "raw_path": raw_path,
        "normalized_path": normalized_path,
        "source_page": source_page,
        "touched": touched,
    }


def collect_directory_sources(source_dir: Path) -> tuple[list[Path], list[Path]]:
    supported: list[Path] = []
    skipped: list[Path] = []
    for path in sorted(source_dir.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix.lower() in SUPPORTED_INGEST_EXTENSIONS:
            supported.append(path)
        else:
            skipped.append(path)
    return supported, skipped


def infer_directory_topic(source_dir: Path, source_file: Path) -> str:
    relative = source_file.relative_to(source_dir)
    if len(relative.parts) > 1:
        return relative.parts[0]
    return source_dir.name


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest a local file, webpage, or text source into the wiki.")
    parser.add_argument("--root", default=".", help="Wiki root path")
    parser.add_argument("--source", help="Path to a local source file")
    parser.add_argument("--url", help="Webpage URL to ingest")
    parser.add_argument("--text", help="Inline text to ingest")
    parser.add_argument("--title", default="", help="Human readable title")
    parser.add_argument("--topic", default="", help="Optional topic page to create")
    parser.add_argument("--confidence", default="", help="Confidence label for the generated source page")
    parser.add_argument("--status", default="", help="Status label for the generated source page")
    args = parser.parse_args()

    provided = [bool(args.source), bool(args.url), bool(args.text)]
    if sum(provided) != 1:
        raise SystemExit("Provide exactly one of --source, --url, or --text")

    root = find_repo_root(Path(args.root))
    raw_path: Path
    normalized_path: Path
    if args.source:
        source_path = Path(args.source).resolve()
        if not source_path.exists():
            raise SystemExit(f"Source file not found: {source_path}")
        if source_path.is_dir():
            files, skipped = collect_directory_sources(source_path)
            if not files:
                raise SystemExit(f"No supported files found under: {source_path}")
            results = []
            for item in files:
                topic_name = args.topic.strip() or infer_directory_topic(source_path, item)
                results.append(ingest_local_source(root, item, topic=topic_name))
            write_text(root / "index.md", rebuild_index.build_index(root))
            log_lines = [
                f"- source_dir: {source_path}",
                f"- imported: {len(results)}",
                *[f"- created: {result['source_page'].relative_to(root).as_posix()}" for result in results],
            ]
            if skipped:
                log_lines.append(f"- skipped: {len(skipped)} unsupported files")
            append_log(root, f"[{today_str()}] ingest-dir | {source_path.name}", log_lines)
            print(f"Ingested {len(results)} files from {source_path}")
            for line in output_access_lines(root):
                print(line)
            return 0
        result = ingest_local_source(
            root,
            source_path,
            title_override=args.title,
            topic=args.topic,
            confidence=args.confidence,
            status=args.status,
        )
    elif args.url:
        normalized_text, raw_html = fetch_webpage_as_markdown(args.url, args.title)
        parsed = urlparse(args.url)
        fallback_title = humanize_name(Path(parsed.path).stem or parsed.netloc or "webpage")
        title = args.title.strip() or extract_title_from_markdown(normalized_text, fallback_title)
        slug = slugify(title, "source")
        raw_path = unique_path(root / "raw" / "web" / f"{today_str()}-{slug}.html")
        normalized_path = unique_path(root / "normalized" / "web" / f"{today_str()}-{slug}.md")
        write_text(raw_path, raw_html or f"URL: {args.url}")
        write_text(normalized_path, normalized_text)
        raw_text = normalized_text
    else:
        title = args.title.strip() or "Pasted Source"
        slug = slugify(title, "source")
        raw_path = unique_path(root / "raw" / "articles" / f"{today_str()}-{slug}.md")
        normalized_path = unique_path(root / "normalized" / "articles" / f"{today_str()}-{slug}.md")
        raw_text = clean_markdown(args.text or "")
        write_text(raw_path, raw_text)
        write_text(normalized_path, raw_text)

    if args.source:
        write_text(root / "index.md", rebuild_index.build_index(root))
        append_log(root, f"[{today_str()}] ingest | {result['title']}", [
            f"- raw: {result['raw_path'].relative_to(root).as_posix()}",
            f"- normalized: {result['normalized_path'].relative_to(root).as_posix()}",
            *[f"- created: {item}" for item in result["touched"]],
        ])
        print(f"Ingested {result['title']}")
        for line in output_access_lines(root):
            print(line)
        return 0

    summary, bullets = summarize(raw_text)
    confidence = args.confidence.strip() or ("mixed" if args.text else "extracted")
    status = args.status.strip() or "active"
    source_page = find_existing_source_page(root, title, slug) or (root / "wiki" / "sources" / f"{slug}.md")
    concept_items = resolve_related_concepts(root, raw_text)
    entity_items = extract_entities(
        raw_text,
        title=title,
        topic_name=args.topic.strip(),
        concept_items=concept_items,
    )
    entity_pages = [
        ensure_entity_page(
            root,
            entity_label,
            source_page,
            args.topic.strip(),
            None,
        )
        for entity_label in entity_items
    ]
    source_content = render_source_page_content(
        root=root,
        source_page=source_page,
        title=title,
        date=today_str(),
        summary=summary,
        raw_path=raw_path,
        normalized_path=normalized_path,
        normalized_text=raw_text,
        bullets=bullets,
        related_links="",
        topic_name=args.topic.strip(),
        concept_items=concept_items,
        entity_items=entity_items,
        entity_pages=entity_pages,
        topic_page=None,
        confidence=confidence,
        status=status,
    )
    write_text(source_page, source_content)
    write_text(root / "index.md", rebuild_index.build_index(root))
    append_log(root, f"[{today_str()}] ingest | {title}", [
        f"- raw: {raw_path.relative_to(root).as_posix()}",
        f"- normalized: {normalized_path.relative_to(root).as_posix()}",
        f"- created: {source_page.relative_to(root).as_posix()}",
        *[f"- created: {item['path']}" for item in entity_pages],
    ])
    print(f"Ingested {title}")
    for line in output_access_lines(root):
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
