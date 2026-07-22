from __future__ import annotations

"""
ThinkWiki Module: utils

Purpose:
- Provide shared helpers for filesystem access, frontmatter parsing, output generation, and workspace summaries.

Usage:
- Imported by other ThinkWiki scripts; not intended for direct execution.
- Run `python scripts/<script> --help` for direct CLI details when the file exposes its own arguments.
"""


import sys
import hashlib
import json
import os
import re
import shutil
from datetime import date, datetime
from html import escape
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

from ai_config import embed_is_configured

ROOT_MARKER = ".wiki-schema.md"
WIKI_DIRS = ["concepts", "topics", "entities", "sources", "syntheses", "queries", "decisions"]
GENERIC_ENTITY_SUFFIXES = {
    "agent",
    "app",
    "engine",
    "framework",
    "platform",
    "project",
    "service",
    "stack",
    "suite",
    "system",
    "tool",
    "wiki",
    "workflow",
}
PAGE_TYPE_TO_DIR = {
    "concept": "concepts",
    "topic": "topics",
    "entity": "entities",
    "source": "sources",
    "synthesis": "syntheses",
    "query": "queries",
    "decision": "decisions",
}
SECTION_ORDER = [
    ("Topics", "topic"),
    ("Concepts", "concept"),
    ("Entities", "entity"),
    ("Sources", "source"),
    ("Syntheses", "synthesis"),
    ("Queries", "query"),
    ("Decisions", "decision"),
]
REQUIRED_FIELDS = ["title", "type", "created", "updated", "sources", "tags", "confidence", "status"]


def today_str() -> str:
    return date.today().isoformat()


def now_slug() -> str:
    return datetime.now().strftime("%Y%m%d%H%M%S")


def slugify(text: str, fallback_prefix: str = "item") -> str:
    text = (text or "").strip().lower()
    text = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")
    return text or f"{fallback_prefix}-{now_slug()}"


def entity_label_keys(label: str) -> list[str]:
    value = re.sub(r"\s+", " ", str(label or "").strip())
    if not value:
        return []
    keys: list[str] = [value.casefold()]
    compact = re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", value.casefold())
    if compact:
        keys.append(compact)
    tokens = [token for token in re.split(r"[\s\-_()/]+", value.casefold()) if token]
    if len(tokens) > 1 and tokens[-1] in GENERIC_ENTITY_SUFFIXES:
        stem_tokens = tokens[:-1]
        stem = " ".join(stem_tokens).strip()
        if stem:
            keys.append(stem)
        stem_compact = "".join(stem_tokens).strip()
        if stem_compact:
            keys.append(stem_compact)
    emb_digest = hashlib.sha256("|".join(keys).encode("utf-8")).hexdigest()[:16]
    keys.append(f"emb:{emb_digest}")
    return unique_strings(keys)


def clean_string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def ambiguous_entity_merge_candidates(
    entity_nodes: list[dict[str, object]],
    embedding_threshold: float = 0.85,
    embedding_enabled: bool = True,
) -> tuple[list[dict[str, object]], int]:
    key_to_entities: dict[str, dict[str, object]] = {}
    entity_labels: dict[str, str] = {}
    for node in entity_nodes:
        entity_id = str(node.get("id") or "")
        entity_title = str(node.get("label") or entity_id).strip() or entity_id
        entity_aliases = clean_string_list(node.get("aliases"))
        entity_labels[entity_id] = entity_title
        for label in [entity_title, *entity_aliases]:
            for key in entity_label_keys(label):
                record = key_to_entities.setdefault(key, {"ids": [], "labels": []})
                if entity_id not in record["ids"]:
                    record["ids"].append(entity_id)
                if label not in record["labels"]:
                    record["labels"].append(label)

    candidates: list[dict[str, object]] = []
    ambiguous_entity_ids: set[str] = set()
    for identity_key, record in key_to_entities.items():
        entity_ids = [str(item) for item in record["ids"] if str(item).strip()]
        if len(entity_ids) < 2:
            continue
        ambiguous_entity_ids.update(entity_ids)
        titles = [entity_labels.get(entity_id, entity_id) for entity_id in entity_ids]
        labels = [str(item) for item in record["labels"] if str(item).strip()]
        candidates.append({
            "identityKey": identity_key,
            "entityIds": entity_ids,
            "titles": titles,
            "labels": labels,
            "reason": f"Identity key `{identity_key}` matches {len(entity_ids)} entity pages. Review manually before merging.",
        })

    if (
        embedding_enabled
        and len(entity_labels) >= 2
        and embed_is_configured()
    ):
        try:
            from ai_config import resolve_embed_config
            from embed_client import cosine_similarity, embed_texts

            embed_config = resolve_embed_config()
            print(
                f"Notice: sending entity labels to configured embedding API at "
                f"{', '.join(embed_config.base_urls)} (model: {embed_config.model}).",
                file=sys.stderr,
            )

            string_grouped_pairs: set[frozenset[str]] = set()
            for candidate in candidates:
                ids = [str(item) for item in candidate["entityIds"]]
                for index, id_a in enumerate(ids):
                    for id_b in ids[index + 1:]:
                        string_grouped_pairs.add(frozenset({id_a, id_b}))

            entity_ids_ordered = list(entity_labels.keys())
            labels_ordered = [entity_labels[eid] for eid in entity_ids_ordered]
            vectors = embed_texts(labels_ordered)
            if vectors and len(vectors) == len(entity_ids_ordered):
                for i, id_a in enumerate(entity_ids_ordered):
                    for j in range(i + 1, len(entity_ids_ordered)):
                        id_b = entity_ids_ordered[j]
                        if frozenset({id_a, id_b}) in string_grouped_pairs:
                            continue
                        sim = cosine_similarity(vectors[i], vectors[j])
                        if sim >= embedding_threshold:
                            ambiguous_entity_ids.update({id_a, id_b})
                            candidates.append({
                                "identityKey": f"emb:{sim:.3f}",
                                "entityIds": [id_a, id_b],
                                "titles": [entity_labels.get(id_a, id_a), entity_labels.get(id_b, id_b)],
                                "labels": [entity_labels.get(id_a, id_a), entity_labels.get(id_b, id_b)],
                                "reason": f"Semantic similarity {sim:.3f} >= {embedding_threshold}. Review manually before merging.",
                            })
        except Exception as exc:
            print(
                f"Warning: embedding API unavailable, using string-only entity matching: {exc}",
                file=sys.stderr,
            )
    return sorted(
        candidates,
        key=lambda item: (
            -len(item["entityIds"]),
            str(item["identityKey"]).lower(),
        ),
    )[:8], len(ambiguous_entity_ids)


def unique_strings(items: Iterable[str]) -> list[str]:
    results: list[str] = []
    seen: set[str] = set()
    for item in items:
        value = str(item).strip()
        if not value or value in seen:
            continue
        seen.add(value)
        results.append(value)
    return results


def repo_root_from_script() -> Path:
    return Path(__file__).resolve().parents[1]


def unique_paths(paths: Iterable[Path]) -> list[Path]:
    results: list[Path] = []
    seen: set[str] = set()
    for path in paths:
        key = str(path.expanduser())
        if key in seen:
            continue
        seen.add(key)
        results.append(path.expanduser())
    return results


def candidate_dependency_paths(
    *,
    env_name: str,
    skill_name: str,
    relative_path: str,
    command_names: Iterable[str] = (),
    script_file: str | Path | None = None,
) -> list[Path]:
    candidates: list[Path] = []
    env_value = os.environ.get(env_name, "").strip()
    if env_value:
        candidates.append(Path(env_value))

    script_root = repo_root_from_script()
    if script_file is not None:
        script_root = Path(script_file).resolve().parents[1]
    cwd = Path.cwd().resolve()
    relative = Path(relative_path)

    # 1) Installed as sibling skills under the same `.trae/skills` directory.
    skill_containers = [script_root.parent, cwd.parent]

    # 2) Running from a project root that contains `.trae/skills`.
    for base in unique_paths([cwd, *cwd.parents, script_root, *script_root.parents]):
        skill_containers.append(base / ".trae" / "skills")

    # 3) Common "project directory next to this repo" layout used in local workspaces.
    sibling_roots = unique_paths([script_root.parent, cwd.parent])
    for parent in sibling_roots:
        try:
            for child in parent.iterdir():
                if child.is_dir():
                    skill_containers.append(child / ".trae" / "skills")
        except OSError:
            continue

    for container in unique_paths(skill_containers):
        candidates.append(container / skill_name / relative)

    for command_name in command_names:
        resolved = shutil.which(command_name)
        if resolved:
            candidates.append(Path(resolved))

    return unique_paths(candidates)


def find_repo_root(start: Path | None = None) -> Path:
    current = (start or Path.cwd()).resolve()
    for candidate in [current, *current.parents]:
        if (candidate / ROOT_MARKER).exists():
            return candidate
    raise FileNotFoundError(f"Cannot find {ROOT_MARKER} from {current}")


def ensure_runtime_dirs(root: Path) -> None:
    for relative in [
        "raw/articles",
        "raw/papers",
        "raw/books",
        "raw/conversations",
        "raw/web",
        "raw/assets",
        "raw/inbox",
        "normalized/articles",
        "normalized/papers",
        "normalized/books",
        "normalized/conversations",
        "normalized/web",
        "normalized/assets",
        "normalized/inbox",
        "wiki/concepts",
        "wiki/topics",
        "wiki/sources",
        "wiki/syntheses",
        "wiki/queries",
        "wiki/decisions",
        "output/graph",
        "output/viewer",
        "output/inbox",
        "output/exports",
    ]:
        (root / relative).mkdir(parents=True, exist_ok=True)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.rstrip() + "\n", encoding="utf-8")


def file_uri(path: Path) -> str:
    return path.resolve().as_uri()


DEFAULT_SERVE_HOST = "127.0.0.1"
DEFAULT_SERVE_PORT = 8765

OUTPUT_SERVE_PAGES = (
    ("Workspace Home", "index.html"),
    ("Inbox Review", "inbox/index.html"),
    ("Local Viewer", "viewer/index.html"),
    ("Knowledge Graph", "graph/index.html"),
    ("Graph Governance Report", "graph/report.html"),
    ("Entity Merge Review", "graph/entity-merge-review.html"),
    ("Entity Merge Plan", "graph/entity-merge-plan.html"),
)


def output_http_base(host: str = DEFAULT_SERVE_HOST, port: int = DEFAULT_SERVE_PORT) -> str:
    return f"http://{host}:{port}"


def output_http_url(
    relative_path: str,
    *,
    host: str = DEFAULT_SERVE_HOST,
    port: int = DEFAULT_SERVE_PORT,
) -> str:
    clean = relative_path.replace("\\", "/").lstrip("/")
    return f"{output_http_base(host, port)}/{clean}"


def output_dir_has_browsable_pages(output_dir: Path) -> bool:
    if not output_dir.is_dir():
        return False
    return any((output_dir / relative).exists() for _, relative in OUTPUT_SERVE_PAGES)


def output_serve_urls(
    root: Path,
    *,
    host: str = DEFAULT_SERVE_HOST,
    port: int = DEFAULT_SERVE_PORT,
) -> dict[str, str]:
    output_dir = root / "output"
    urls: dict[str, str] = {}
    for label, relative in OUTPUT_SERVE_PAGES:
        if (output_dir / relative).exists():
            urls[label] = output_http_url(relative, host=host, port=port)
    return urls


def format_output_serve_lines(
    root: Path,
    *,
    host: str = DEFAULT_SERVE_HOST,
    port: int = DEFAULT_SERVE_PORT,
) -> list[str]:
    urls = output_serve_urls(root, host=host, port=port)
    lines = [
        f"ThinkWiki output server: {output_http_base(host, port)}",
        f"Wiki root: {root.resolve()}",
        f"Serving directory: {(root / 'output').resolve()}",
    ]
    for label, url in urls.items():
        lines.append(f"{label}: {url}")
    if "Workspace Home" in urls:
        lines.append(f"OpenClaw browser: openclaw browser --browser-profile openclaw open {urls['Workspace Home']}")
    return lines


def output_serve_hint_line(root: Path) -> str | None:
    if not output_dir_has_browsable_pages(root / "output"):
        return None
    return (
        "Browse via HTTP: "
        f"run `python scripts/thinkwiki serve --root {display_root_arg(root)}` "
        f"-> {output_http_url('index.html')}"
    )


def print_output_serve_hint(root: Path) -> None:
    line = output_serve_hint_line(root)
    if line:
        print(line)


def display_root_arg(root: Path) -> str:
    repo_root = repo_root_from_script()
    demo_root = (repo_root / "docs" / "demo-wiki").resolve()
    try:
        if root.resolve() == demo_root:
            return "<wiki-root>"
    except OSError:
        pass
    return str(root)


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _first_markdown_heading(path: Path) -> str:
    if not path.exists():
        return ""
    try:
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if line.startswith("# "):
                return line[2:].strip()
    except OSError:
        return ""
    return ""


def _page_sort_key(page: dict) -> tuple[str, str]:
    return (str(page.get("updated", "") or ""), str(page.get("title", "") or ""))


def _humanize_label(value: str) -> str:
    text = re.sub(r"[-_]+", " ", value).strip()
    return text or value or "Untitled"


def _inbox_quality(item: dict) -> tuple[str, str]:
    kind = str(item.get("kind", "") or "")
    adapter = str(item.get("adapter", "") or "")
    summary = str(item.get("summary", "") or "").strip()
    title = str(item.get("title", "") or "").strip()
    site_name = str(item.get("site_name", "") or "").strip()
    source_url = str(item.get("source_url", "") or "").strip()
    author = str(item.get("author", "") or "").strip()
    publish_date = str(item.get("publish_date", "") or "").strip()

    score = 0
    if title and len(title) >= 4:
        score += 1
    if summary and summary not in {"(no summary)", "(no summary yet)"} and len(summary) >= 24:
        score += 2
    if source_url:
        score += 1
    if site_name:
        score += 1
    if author:
        score += 1
    if publish_date:
        score += 1
    if adapter == "wechat":
        score += 1
    if kind == "web" and not source_url:
        score -= 2

    if score >= 5:
        return "ready", "Web metadata looks complete enough for final review before formal ingest."
    if score >= 3:
        return "review", "The content is readable, but you should verify the source, author, or publish date first."
    return "weak", "Too little information was extracted. Check the article body and source details manually first."


def _capture_state_reason(state: str) -> str:
    if state == "wait_completed":
        return "Wait mode captured a fuller article body."
    if state == "wait_timeout":
        return "Wait mode finished, but the article body still looks unstable. Review it manually."
    if state == "needs_review":
        return "Capture finished, but the article body quality is only moderate."
    return "Capture status looks normal."


def _capture_reason_hint(reason: str, fallback: str) -> str:
    if reason == "loading_placeholder":
        return "The page still looks like a loading placeholder. Retry later or capture again with wait mode."
    if reason == "body_too_short":
        return "The article body is too short. Check whether this is the full article page."
    if reason == "sparse_structure":
        return "The body structure looks sparse. The capture may contain only a summary or page header."
    if reason == "metadata_sparse":
        return "Author, source, or publish date metadata is missing. Review it manually."
    return fallback or "The capture structure looks complete."


def collect_inbox_items(root: Path) -> list[dict]:
    inbox_dir = root / "normalized" / "inbox"
    if not inbox_dir.exists():
        return []

    def sort_key(path: Path) -> tuple[float, str]:
        try:
            return (path.stat().st_mtime, path.name)
        except OSError:
            return (0.0, path.name)

    paths = sorted(inbox_dir.glob("*.md"), key=sort_key, reverse=True)
    items: list[dict] = []
    for path in paths:
        text = read_text(path)
        meta, body = parse_frontmatter(text)
        repo_path = path.relative_to(root).as_posix()
        sidecar_path = path.with_suffix(".json")
        sidecar = _load_json(sidecar_path)
        title = (
            _first_markdown_heading(path)
            or str(meta.get("title", "") or "").strip()
            or _humanize_label(path.stem)
        )
        summary = extract_summary(meta, body)
        try:
            updated = datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
        except OSError:
            updated = "n/a"
        quality_status, quality_reason = _inbox_quality({
            "kind": str(sidecar.get("kind", "") or ""),
            "adapter": str(sidecar.get("adapter", "") or ""),
            "summary": summary,
            "title": title,
            "site_name": str(sidecar.get("siteName", "") or ""),
            "source_url": str(sidecar.get("url", "") or ""),
            "author": str(sidecar.get("author", "") or ""),
            "publish_date": str(sidecar.get("publishDate", "") or ""),
        })
        capture_state = str(sidecar.get("captureState", "") or "")
        capture_mode = str(sidecar.get("captureMode", "") or "")
        capture_reason = str(sidecar.get("captureReason", "") or "")
        review_hint = str(sidecar.get("reviewHint", "") or "")
        items.append({
            "title": title,
            "summary": summary,
            "updated": updated,
            "path": repo_path,
            "href": Path(os.path.relpath(path, start=root / "output")).as_posix(),
            "ingest_command": f"python scripts/thinkwiki ingest --root {display_root_arg(root)} --source {repo_path}",
            "kind": str(sidecar.get("kind", "") or ""),
            "adapter": str(sidecar.get("adapter", "") or ""),
            "site_name": str(sidecar.get("siteName", "") or ""),
            "author": str(sidecar.get("author", "") or ""),
            "publish_date": str(sidecar.get("publishDate", "") or ""),
            "source_url": str(sidecar.get("url", "") or ""),
            "metadata_path": sidecar_path.relative_to(root).as_posix() if sidecar_path.exists() else "",
            "capture_state": capture_state,
            "capture_mode": capture_mode,
            "capture_attempts": int(sidecar.get("captureAttempts", 0) or 0),
            "capture_elapsed_seconds": sidecar.get("captureElapsedSeconds", ""),
            "capture_state_reason": _capture_state_reason(capture_state),
            "capture_reason": capture_reason,
            "review_hint": _capture_reason_hint(capture_reason, review_hint),
            "media_policy": str(sidecar.get("mediaPolicy", "") or ""),
            "media_status": str(sidecar.get("mediaStatus", "") or ""),
            "media_count": int(sidecar.get("mediaCount", 0) or 0),
            "localized_media_count": int(sidecar.get("localizedMediaCount", 0) or 0),
            "media_dir": str(sidecar.get("mediaDir", "") or ""),
            "quality_status": quality_status,
            "quality_reason": quality_reason,
        })
    return items


def batch_ingest_command(root: Path, quality: str = "ready", limit: int | None = None, dry_run: bool = False) -> str:
    command = f"python scripts/thinkwiki batch-ingest --root {display_root_arg(root)} --quality {quality}"
    if limit is not None and limit > 0:
        command += f" --limit {limit}"
    if dry_run:
        command += " --dry-run"
    return command


def _inbox_groups(items: list[dict]) -> dict[str, list[dict]]:
    groups: dict[str, list[dict]] = {"ready": [], "review": [], "weak": [], "other": []}
    for item in items:
        status = str(item.get("quality_status", "") or "")
        if status not in groups:
            status = "other"
        groups[status].append(item)
    return groups


def _inbox_quality_summary(items: list[dict]) -> dict[str, int]:
    groups = _inbox_groups(items)
    return {key: len(value) for key, value in groups.items()}


def _priority_inbox_items(items: list[dict], limit: int = 3) -> list[dict]:
    groups = _inbox_groups(items)
    ranked: list[dict] = []
    for status in ["ready", "review", "weak", "other"]:
        ranked.extend(groups.get(status, []))
    return ranked[:limit]


def _render_command_list(commands: list[str], empty_text: str) -> str:
    if not commands:
        return "<div class='empty small'>{}</div>".format(escape(empty_text))
    rows = [
        "<pre class='command-pre'>{}</pre>".format(escape(command))
        for command in commands
    ]
    return "\n".join(rows)


def _render_page_list(items: list[dict], empty_text: str) -> str:
    if not items:
        return "<div class='empty small'>{}</div>".format(escape(empty_text))
    cards: list[str] = []
    for item in items:
        page_id = str(item.get("id", ""))
        title = str(item.get("title", page_id or "Untitled"))
        summary = str(item.get("summary", "") or "(no summary yet)")
        page_type = str(item.get("type", "page") or "page")
        updated = str(item.get("updated", "") or "n/a")
        href = "viewer/index.html#page={}".format(escape(page_id, quote=True))
        cards.append(
            "<a class='mini-card' href='{href}' target='_blank' rel='noopener'>"
            "<div class='mini-meta'><span class='mini-type'>{page_type}</span><span>{updated}</span></div>"
            "<strong>{title}</strong>"
            "<span>{summary}</span>"
            "</a>".format(
                href=href,
                page_type=escape(page_type),
                updated=escape(updated),
                title=escape(title),
                summary=escape(summary),
            )
        )
    return "\n".join(cards)


def _render_bullet_list(items: list[str], empty_text: str) -> str:
    if not items:
        return "<div class='empty small'>{}</div>".format(escape(empty_text))
    rows = [
        "<li>{}</li>".format(item)
        for item in items
    ]
    return "<ul class='bullet-list'>{}</ul>".format("".join(rows))


def _render_action_cards(items: list[dict], empty_text: str) -> str:
    if not items:
        return "<div class='empty small'>{}</div>".format(escape(empty_text))
    cards: list[str] = []
    for item in items:
        href = str(item.get("href", "") or "")
        title = str(item.get("title", "Untitled"))
        summary = str(item.get("summary", "") or "")
        label = str(item.get("label", "") or "")
        target_attrs = " target='_blank' rel='noopener'" if href else ""
        tag_html = "<span class='action-tag'>{}</span>".format(escape(label)) if label else ""
        cards.append(
            "<a class='action-card' href='{href}'{target_attrs}>"
            "{tag_html}"
            "<strong>{title}</strong>"
            "<span>{summary}</span>"
            "</a>".format(
                href=escape(href or "#", quote=True),
                target_attrs=target_attrs,
                tag_html=tag_html,
                title=escape(title),
                summary=escape(summary),
            )
        )
    return "\n".join(cards)


def _render_inbox_list(items: list[dict], empty_text: str) -> str:
    if not items:
        return "<div class='empty small'>{}</div>".format(escape(empty_text))
    cards: list[str] = []
    for item in items:
        kind = str(item.get("kind", "") or "")
        adapter = str(item.get("adapter", "") or "")
        mini_type = adapter or kind or "inbox"
        detail_parts = [
            str(item.get("site_name", "") or ""),
            str(item.get("author", "") or ""),
        ]
        detail_text = " · ".join(part for part in detail_parts if part)
        detail_html = "<span>{}</span>".format(escape(detail_text)) if detail_text else ""
        quality_status = str(item.get("quality_status", "") or "")
        quality_html = ""
        if quality_status:
            quality_html = "<span class='quality quality-{status}'>{label}</span>".format(
                status=escape(quality_status),
                label=escape(f"quality: {quality_status}"),
            )
        capture_state = str(item.get("capture_state", "") or "")
        capture_html = ""
        if capture_state:
            capture_html = "<span class='quality quality-{status}'>{label}</span>".format(
                status=escape(capture_state),
                label=escape(f"capture: {capture_state}"),
            )
        capture_reason = str(item.get("capture_reason", "") or "")
        reason_html = ""
        if capture_reason and capture_reason != "ready":
            reason_html = "<span class='quality quality-media'>{label}</span>".format(
                label=escape(f"reason: {capture_reason}"),
            )
        media_status = str(item.get("media_status", "") or "")
        media_html = ""
        if media_status:
            media_html = "<span class='quality quality-media'>{label}</span>".format(
                label=escape(f"media: {media_status}"),
            )
        cards.append(
            "<a class='mini-card' href='{href}' target='_blank' rel='noopener'>"
            "<div class='mini-meta'><span class='mini-type'>{mini_type}</span><span>{updated}</span></div>"
            "<strong>{title}</strong>"
            "<span>{summary}</span>"
            "{detail_html}"
            "{quality_html}"
            "{capture_html}"
            "{reason_html}"
            "{media_html}"
            "<code>{path}</code>"
            "</a>".format(
                href=escape(str(item.get("href", "") or "#"), quote=True),
                mini_type=escape(mini_type),
                updated=escape(str(item.get("updated", "") or "n/a")),
                title=escape(str(item.get("title", "Untitled"))),
                summary=escape(str(item.get("summary", "") or "(no summary yet)")),
                detail_html=detail_html,
                quality_html=quality_html,
                capture_html=capture_html,
                reason_html=reason_html,
                media_html=media_html,
                path=escape(str(item.get("path", "") or "")),
            )
        )
    return "\n".join(cards)


def _render_inbox_review_cards(items: list[dict], inbox_dir: Path, root: Path) -> str:
    cards: list[str] = []
    for item in items:
        normalized_target = root / str(item.get("path", ""))
        normalized_href = Path(os.path.relpath(normalized_target, start=inbox_dir)).as_posix()
        metadata_path = str(item.get("metadata_path", "") or "")
        metadata_target = root / metadata_path if metadata_path else None
        metadata_href = ""
        if metadata_target is not None and metadata_target.exists():
            metadata_href = Path(os.path.relpath(metadata_target, start=inbox_dir)).as_posix()
        meta_rows: list[str] = []
        for label, value in [
            ("Adapter", str(item.get("adapter", "") or "")),
            ("Mode", str(item.get("capture_mode", "") or "")),
            ("State", str(item.get("capture_state", "") or "")),
            ("Reason", str(item.get("capture_reason", "") or "")),
            ("Media", str(item.get("media_status", "") or "")),
            ("Source", str(item.get("site_name", "") or "")),
            ("Author", str(item.get("author", "") or "")),
            ("Published", str(item.get("publish_date", "") or "")),
            ("Quality", str(item.get("quality_status", "") or "")),
        ]:
            if value:
                meta_rows.append(
                    "<span class='fact'><strong>{label}</strong>{value}</span>".format(
                        label=escape(label + ": "),
                        value=escape(value),
                    )
                )
        attempts = int(item.get("capture_attempts", 0) or 0)
        elapsed = str(item.get("capture_elapsed_seconds", "") or "")
        if attempts:
            meta_rows.append(
                "<span class='fact'><strong>Attempts: </strong>{value}</span>".format(value=escape(str(attempts)))
            )
        if elapsed:
            meta_rows.append(
                "<span class='fact'><strong>Elapsed: </strong>{value}s</span>".format(value=escape(elapsed))
            )
        media_count = int(item.get("media_count", 0) or 0)
        localized_media_count = int(item.get("localized_media_count", 0) or 0)
        if media_count:
            meta_rows.append(
                "<span class='fact'><strong>Media files: </strong>{value}</span>".format(
                    value=escape(f"{localized_media_count}/{media_count}")
                )
            )
        media_dir = str(item.get("media_dir", "") or "")
        if media_dir:
            meta_rows.append(
                "<span class='fact'><strong>Media dir: </strong>{value}</span>".format(value=escape(media_dir))
            )
        source_url = str(item.get("source_url", "") or "")
        if source_url:
            meta_rows.append(
                "<a class='fact fact-link' href='{href}' target='_blank' rel='noopener'><strong>URL: </strong>{value}</a>".format(
                    href=escape(source_url, quote=True),
                    value=escape(source_url),
                )
            )
        cards.append(
            "<article class='card'>"
            "<div class='meta'><span class='tag'>{tag}</span><span>{updated}</span></div>"
            "<h3>{title}</h3>"
            "<p>{summary}</p>"
            "<div class='facts'>{facts}</div>"
            "<div class='path'><code>{path}</code></div>"
            "<div class='quality-note'>{capture_reason}</div>"
            "<div class='quality-note'>{review_hint}</div>"
            "<div class='quality-note'>{quality_reason}</div>"
            "<div class='actions'>"
            "<a href='{normalized_href}' target='_blank' rel='noopener'>Open normalized note</a>"
            "<a href='../index.html' target='_blank' rel='noopener'>Open workspace home</a>"
            "{metadata_link}"
            "</div>"
            "<div class='command-label'>Next ingest command</div>"
            "<pre>{command}</pre>"
            "</article>".format(
                tag=escape(str(item.get("adapter", "") or item.get("kind", "") or "inbox")),
                updated=escape(str(item.get("updated", "") or "n/a")),
                title=escape(str(item.get("title", "Untitled"))),
                summary=escape(str(item.get("summary", "") or "(no summary yet)")),
                facts="".join(meta_rows),
                path=escape(str(item.get("path", "") or "")),
                capture_reason=escape(str(item.get("capture_state_reason", "") or "")),
                review_hint=escape(str(item.get("review_hint", "") or "")),
                quality_reason=escape(str(item.get("quality_reason", "") or "")),
                normalized_href=escape(normalized_href, quote=True),
                metadata_link=(
                    "<a href='{href}' target='_blank' rel='noopener'>Open metadata</a>".format(
                        href=escape(metadata_href, quote=True)
                    )
                    if metadata_href
                    else ""
                ),
                command=escape(str(item.get("ingest_command", "") or "")),
            )
        )
    return "\n".join(cards)


def _render_inbox_review_section(
    *,
    anchor: str,
    title: str,
    description: str,
    items: list[dict],
    inbox_dir: Path,
    root: Path,
    empty_text: str,
) -> str:
    cards_html = _render_inbox_review_cards(items, inbox_dir, root) if items else "<div class='empty'>{}</div>".format(escape(empty_text))
    commands = [str(item.get("ingest_command", "") or "") for item in items[:3] if str(item.get("ingest_command", "") or "")]
    if anchor == "ready" and items:
        commands = [
            batch_ingest_command(root, quality="ready", dry_run=True),
            batch_ingest_command(root, quality="ready"),
            *commands,
        ]
    command_html = _render_command_list(commands, "No recommended commands for this section yet.")
    return (
        "<section class='group' id='{anchor}'>"
        "<div class='group-head'>"
        "<div><h2>{title}</h2><p>{description}</p></div>"
        "<span class='badge'>Items {count}</span>"
        "</div>"
        "<div class='group-commands'>"
        "<div class='command-label'>Recommended next commands</div>"
        "{commands}"
        "</div>"
        "<div class='cards'>{cards}</div>"
        "</section>"
    ).format(
        anchor=escape(anchor, quote=True),
        title=escape(title),
        description=escape(description),
        count=escape(str(len(items))),
        commands=command_html,
        cards=cards_html,
    )


def _recent_pages(pages: list[dict], limit: int = 4) -> list[dict]:
    return sorted(pages, key=_page_sort_key, reverse=True)[:limit]


def _generated_pages(pages: list[dict], limit: int = 4) -> list[dict]:
    generated = [
        page
        for page in pages
        if str(page.get("type", "")) in {"concept", "decision", "synthesis", "query"}
    ]
    return sorted(generated, key=_page_sort_key, reverse=True)[:limit]


def _featured_pages(pages: list[dict], limit: int = 4) -> list[dict]:
    featured = [
        page
        for page in pages
        if str(page.get("type", "")) in {"concept", "decision", "synthesis", "source"}
    ]
    return sorted(featured, key=_page_sort_key, reverse=True)[:limit]


def _attention_items(pages: list[dict], graph_insights: dict, graph_report: dict) -> list[str]:
    items: list[str] = []
    isolated_nodes = graph_insights.get("isolatedNodes", []) if isinstance(graph_insights, dict) else []
    weak_pages = [item for item in isolated_nodes if str(item.get("severity", "")) == "weak"]
    isolated_pages = [item for item in isolated_nodes if str(item.get("severity", "")) == "isolated"]
    if isolated_pages:
        items.append("There are <strong>{}</strong> isolated pages. Add links or source references first.".format(len(isolated_pages)))
    if weak_pages:
        items.append("There are <strong>{}</strong> weakly connected pages. They need more context.".format(len(weak_pages)))

    report_stats = graph_report.get("stats", {}) if isinstance(graph_report.get("stats"), dict) else {}
    hub_stubs = int(report_stats.get("hubStubCount", 0) or 0)
    fragile_bridges = int(report_stats.get("fragileBridgeCount", 0) or 0)
    isolated_clusters = int(report_stats.get("isolatedClusterCount", 0) or 0)
    ambiguous_alias_groups = int(report_stats.get("ambiguousAliasGroupCount", 0) or 0)
    if hub_stubs:
        items.append("There are <strong>{}</strong> high-degree thin pages. Improve their summaries and context first.".format(hub_stubs))
    if fragile_bridges:
        items.append("There are <strong>{}</strong> fragile bridge pages. Strengthen cross-topic connections.".format(fragile_bridges))
    if isolated_clusters:
        items.append("There are <strong>{}</strong> page clusters disconnected from the main graph. Reconnect them soon.".format(isolated_clusters))
    if ambiguous_alias_groups:
        items.append("There are <strong>{}</strong> ambiguous alias groups. Review whether those entities should be merged.".format(ambiguous_alias_groups))

    missing_summary = [
        page for page in pages
        if str(page.get("summary", "") or "").strip() in {"", "(no summary)", "(no summary yet)"}
    ]
    if missing_summary:
        items.append("There are <strong>{}</strong> pages without reliable summaries.".format(len(missing_summary)))

    missing_sources = [
        page for page in pages
        if not isinstance(page.get("sources"), list) or not list(page.get("sources") or [])
    ]
    if missing_sources:
        items.append("There are <strong>{}</strong> pages without source references.".format(len(missing_sources)))

    return items[:4]


def _recommended_actions(
    *,
    viewer_exists: bool,
    graph_exists: bool,
    graph_insights: dict,
    graph_report: dict,
    graph_report_exists: bool,
    entity_merge_review_exists: bool,
    recent_pages: list[dict],
    inbox_page_exists: bool,
    inbox_count: int,
    inbox_items: list[dict],
) -> list[dict]:
    actions: list[dict] = []
    ready_items = [item for item in inbox_items if str(item.get("quality_status", "") or "") == "ready"]
    if ready_items:
        actions.append({
            "label": "Ingest",
            "title": "Prioritize Ready Inbox",
            "summary": "There are {} inbox items ready for final review and formal ingest. Start with the Ready section.".format(len(ready_items)),
            "href": "inbox/index.html#ready" if inbox_page_exists else str(ready_items[0].get("href", "") or "#"),
        })
    if inbox_count:
        actions.append({
            "label": "Review",
            "title": "Review Inbox Queue",
            "summary": "There are {} captured items. Review the latest one before deciding whether to ingest it.".format(inbox_count),
            "href": "inbox/index.html" if inbox_page_exists else str((inbox_items[0] if inbox_items else {}).get("href", "") or "#"),
        })
    if viewer_exists:
        actions.append({
            "label": "Read",
            "title": "Open Local Viewer",
            "summary": "Browse the whole wiki by page type, status, and confidence.",
            "href": "viewer/index.html",
        })
    if graph_exists:
        summary = "Open the graph to inspect key pages, bridge pages, and suggested links."
        actions.append({
            "label": "Explore",
            "title": "Open Knowledge Graph",
            "summary": summary,
            "href": "graph/index.html",
        })
    if graph_report_exists:
        report_actions = graph_report.get("topActions", []) if isinstance(graph_report.get("topActions"), list) else []
        actions.append({
            "label": "Govern",
            "title": "Open Graph Governance Report",
            "summary": str(report_actions[0]) if report_actions else "See the governance summary for isolated pages, fragile bridges, and suggested links.",
            "href": "graph/report.html",
        })
    ambiguous_groups = int(graph_report.get("stats", {}).get("ambiguousAliasGroupCount", 0) or 0) if isinstance(graph_report.get("stats"), dict) else 0
    if entity_merge_review_exists and ambiguous_groups:
        actions.append({
            "label": "Review",
            "title": "Review Entity Merge Candidates",
            "summary": "There are {} ambiguous entity alias groups. Confirm the canonical entity page first.".format(ambiguous_groups),
            "href": "graph/entity-merge-review.html",
        })

    stats = graph_insights.get("stats", {}) if isinstance(graph_insights, dict) else {}
    isolated_count = int(stats.get("isolatedCount", 0) or 0)
    if graph_exists and isolated_count:
        actions.append({
            "label": "Fix",
            "title": "Fix Isolated Pages",
            "summary": "There are {} isolated pages. Inspect them in the graph and add links first.".format(isolated_count),
            "href": "graph/index.html",
        })

    suggested_links = graph_insights.get("suggestedLinks", []) if isinstance(graph_insights, dict) else []
    if graph_exists and suggested_links:
        actions.append({
            "label": "Link",
            "title": "Review Suggested Links",
            "summary": "The graph identified {} high-confidence suggested links.".format(len(suggested_links)),
            "href": "graph/index.html",
        })

    if recent_pages:
        page_id = str(recent_pages[0].get("id", "") or "")
        if page_id:
            actions.append({
                "label": "Latest",
                "title": "Open Latest Page",
                "summary": "Continue reading or refining the most recently updated page.",
                "href": "viewer/index.html#page={}".format(escape(page_id, quote=True)),
            })

    if not actions:
        actions.append({
            "label": "Build",
            "title": "Build Viewer and Graph",
            "summary": "Run viewer and graph first so the workspace home can show the full workbench.",
            "href": "",
        })
    return actions[:4]


def write_output_home(root: Path) -> Path:
    output_dir = root / "output"
    viewer_path = output_dir / "viewer" / "index.html"
    graph_path = output_dir / "graph" / "index.html"
    graph_report_path = output_dir / "graph" / "report.html"
    entity_merge_review_path = output_dir / "graph" / "entity-merge-review.html"
    entity_merge_plan_path = output_dir / "graph" / "entity-merge-plan.html"
    inbox_path = output_dir / "inbox" / "index.html"
    viewer_data = _load_json(output_dir / "viewer" / "viewer.json")
    graph_data = _load_json(output_dir / "graph" / "graph.json")
    graph_report = _load_json(output_dir / "graph" / "report.json")
    wiki_title = _first_markdown_heading(root / "index.md") or root.name
    generated_at = str(
        graph_report.get("generated_at")
        or viewer_data.get("generatedAt")
        or graph_data.get("generated_at")
        or today_str()
    )
    page_count = int(viewer_data.get("pageCount", 0) or 0)
    graph_views = graph_data.get("views", {}) if isinstance(graph_data.get("views"), dict) else {}
    knowledge_view = graph_views.get("knowledge", {}) if isinstance(graph_views.get("knowledge"), dict) else {}
    suggested_view = graph_views.get("suggested", {}) if isinstance(graph_views.get("suggested"), dict) else {}
    node_count = len(knowledge_view.get("nodes", [])) if isinstance(knowledge_view.get("nodes"), list) else len(graph_data.get("nodes", [])) if isinstance(graph_data.get("nodes"), list) else 0
    edge_count = len(knowledge_view.get("edges", [])) if isinstance(knowledge_view.get("edges"), list) else len(graph_data.get("edges", [])) if isinstance(graph_data.get("edges"), list) else 0
    graph_insights = graph_data.get("insights", {}) if isinstance(graph_data.get("insights"), dict) else {}
    graph_schema_version = str(graph_data.get("schema_version", "") or "1")
    graph_default_view = str(graph_data.get("default_view", "") or "legacy")
    claim_count = sum(
        1 for node in knowledge_view.get("nodes", [])
        if isinstance(node, dict) and str(node.get("type", "") or "") == "claim"
    ) if isinstance(knowledge_view.get("nodes"), list) else 0
    entity_count = sum(
        1 for node in knowledge_view.get("nodes", [])
        if isinstance(node, dict) and str(node.get("type", "") or "") == "entity"
    ) if isinstance(knowledge_view.get("nodes"), list) else 0
    aliased_entity_count = sum(
        1 for node in knowledge_view.get("nodes", [])
        if isinstance(node, dict)
        and str(node.get("type", "") or "") == "entity"
        and isinstance(node.get("aliases"), list)
        and any(str(item).strip() for item in node.get("aliases", []))
    ) if isinstance(knowledge_view.get("nodes"), list) else 0
    alias_count = sum(
        len([str(item).strip() for item in node.get("aliases", []) if str(item).strip()])
        for node in knowledge_view.get("nodes", [])
        if isinstance(node, dict)
        and str(node.get("type", "") or "") == "entity"
        and isinstance(node.get("aliases"), list)
    ) if isinstance(knowledge_view.get("nodes"), list) else 0
    suggested_edge_count = len(suggested_view.get("edges", [])) if isinstance(suggested_view.get("edges"), list) else 0
    ready_outputs = (
        int(viewer_path.exists())
        + int(graph_path.exists())
        + int(graph_report_path.exists())
        + int(entity_merge_review_path.exists())
        + int(entity_merge_plan_path.exists())
        + int(inbox_path.exists())
    )
    pages = viewer_data.get("pages", []) if isinstance(viewer_data.get("pages"), list) else []
    all_inbox_items = collect_inbox_items(root)
    inbox_count = len(all_inbox_items)
    inbox_items = all_inbox_items[:4]
    inbox_summary = _inbox_quality_summary(all_inbox_items)
    recent_pages = _recent_pages(pages)
    generated_pages = _generated_pages(pages)
    featured_pages = _featured_pages(pages)
    attention_items = _attention_items(pages, graph_insights, graph_report)
    graph_summary = str(graph_insights.get("summary", "") or "").strip()
    graph_stats = graph_insights.get("stats", {}) if isinstance(graph_insights, dict) else {}
    graph_report_stats = graph_report.get("stats", {}) if isinstance(graph_report.get("stats"), dict) else {}
    key_pages = graph_insights.get("topNodes", []) if isinstance(graph_insights.get("topNodes"), list) else []
    output_items: list[str] = []
    for title, path, summary in [
        ("Inbox Review", inbox_path, "Review inbox items and copy the next ingest commands"),
        ("Local Viewer", viewer_path, "Browse the entire wiki by page type, confidence, and status"),
        ("Knowledge Graph", graph_path, "Switch between knowledge, document, and suggested views to inspect content relations and candidate edges"),
        ("Graph Governance Report", graph_report_path, "Inspect isolated pages, fragile bridges, disconnected clusters, and governance actions"),
        ("Entity Merge Review", entity_merge_review_path, "Review alias collision candidates and confirm which entity pages should be merged or downgraded to aliases"),
        ("Entity Merge Plan", entity_merge_plan_path, "Preview the canonical merge plan before writing aliases, sources, and topics back"),
    ]:
        if not path.exists():
            continue
        relative = path.relative_to(output_dir).as_posix()
        output_items.append(
            "<a class='card' href='{href}' target='_blank' rel='noopener'>"
            "<strong>{title}</strong>"
            "<span>{summary}</span>"
            "<code>{path}</code>"
            "</a>".format(
                href=escape(relative),
                title=escape(title),
                summary=escape(summary),
                path=escape(relative),
            )
        )
    if not output_items:
        output_items.append("<div class='empty'>No browsable outputs yet. Run viewer or graph first.</div>")

    stats: list[str] = []
    for label, value in [
        ("Outputs", ready_outputs),
        ("Inbox", inbox_count),
        ("Ready", inbox_summary.get("ready", 0)),
        ("Pages", page_count),
        ("Graph Nodes", node_count),
        ("Graph Edges", edge_count),
        ("Claims", claim_count),
        ("Entities", entity_count),
    ]:
        stats.append(
            "<div class='stat'><strong>{value}</strong><span>{label}</span></div>".format(
                value=escape(str(value)),
                label=escape(label),
            )
        )
    recent_pages_html = _render_page_list(recent_pages, "No recent pages to recommend yet. Run viewer to generate browseable outputs first.")
    generated_pages_html = _render_page_list(generated_pages, "No recently generated query, synthesis, decision, or concept pages yet.")
    featured_pages_html = _render_page_list(featured_pages, "No featured pages yet.")
    attention_html = _render_bullet_list(attention_items, "Nothing urgent needs attention right now.")
    actions_html = _render_action_cards(
        _recommended_actions(
            viewer_exists=viewer_path.exists(),
            graph_exists=graph_path.exists(),
            graph_insights=graph_insights,
            graph_report=graph_report,
            graph_report_exists=graph_report_path.exists(),
            entity_merge_review_exists=entity_merge_review_path.exists(),
            recent_pages=recent_pages,
            inbox_page_exists=inbox_path.exists(),
            inbox_count=inbox_count,
            inbox_items=all_inbox_items,
        ),
        "No recommended next actions yet.",
    )
    inbox_html = _render_inbox_list(inbox_items, "No inbox items yet. Run clip to collect webpages, text, or files first.")
    graph_snapshot_items: list[str] = []
    report_summary = str(graph_report.get("summary", "") or "").strip()
    if report_summary:
        graph_snapshot_items.append("<div class='snapshot-copy'>{}</div>".format(escape(report_summary)))
    elif graph_summary:
        graph_snapshot_items.append("<div class='snapshot-copy'>{}</div>".format(escape(graph_summary)))
    if key_pages:
        graph_snapshot_items.append(
            "<div class='snapshot-chip'>Current key page: <strong>{}</strong></div>".format(
                escape(str(key_pages[0].get("title", "") or "n/a"))
            )
        )
    graph_snapshot_items.append(
        "<div class='snapshot-chip'>Graph Schema v{schema}</div>"
        "<div class='snapshot-chip'>Default View {default_view}</div>"
        "<div class='snapshot-chip'>Knowledge Nodes {knowledge_nodes}</div>"
        "<div class='snapshot-chip'>Claims {claims}</div>"
        "<div class='snapshot-chip'>Entities {entities}</div>"
        "<div class='snapshot-chip'>Aliased Entities {aliased_entities}</div>"
        "<div class='snapshot-chip'>Aliases {aliases}</div>"
        "<div class='snapshot-chip'>Ambiguous Alias Groups {ambiguous_groups}</div>"
        "<div class='snapshot-chip'>Ambiguous Entities {ambiguous_entities}</div>"
        "<div class='snapshot-chip'>Suggested Edges {suggested_edges}</div>".format(
            schema=escape(graph_schema_version),
            default_view=escape(graph_default_view),
            knowledge_nodes=escape(str(node_count)),
            claims=escape(str(claim_count)),
            entities=escape(str(entity_count)),
            aliased_entities=escape(str(aliased_entity_count)),
            aliases=escape(str(alias_count)),
            ambiguous_groups=escape(str(int(graph_report_stats.get("ambiguousAliasGroupCount", 0) or 0))),
            ambiguous_entities=escape(str(int(graph_report_stats.get("ambiguousEntityCount", 0) or 0))),
            suggested_edges=escape(str(suggested_edge_count)),
        )
    )
    suggested_count = len(graph_insights.get("suggestedLinks", [])) if isinstance(graph_insights.get("suggestedLinks"), list) else 0
    hub_stub_count = int(graph_report_stats.get("hubStubCount", 0) or 0)
    fragile_bridge_count = int(graph_report_stats.get("fragileBridgeCount", 0) or 0)
    isolated_cluster_count = int(graph_report_stats.get("isolatedClusterCount", 0) or 0)
    isolated_entity_count = int(graph_report_stats.get("isolatedEntityCount", 0) or 0)
    ambiguous_alias_group_count = int(graph_report_stats.get("ambiguousAliasGroupCount", 0) or 0)
    graph_snapshot_items.append(
        "<div class='snapshot-chip'>Isolated Pages {isolated}</div>"
        "<div class='snapshot-chip'>Isolated Entities {isolated_entities}</div>"
        "<div class='snapshot-chip'>Suggested Links {links}</div>"
        "<div class='snapshot-chip'>Ambiguous Alias Groups {ambiguous_groups}</div>"
        "<div class='snapshot-chip'>Hub Stubs {hub_stubs}</div>"
        "<div class='snapshot-chip'>Fragile Bridges {fragile}</div>"
        "<div class='snapshot-chip'>Isolated Clusters {clusters}</div>".format(
            isolated=escape(str(int(graph_report_stats.get("isolatedPageCount", graph_stats.get("isolatedCount", 0)) or 0))),
            isolated_entities=escape(str(isolated_entity_count)),
            links=escape(str(suggested_count)),
            ambiguous_groups=escape(str(ambiguous_alias_group_count)),
            hub_stubs=escape(str(hub_stub_count)),
            fragile=escape(str(fragile_bridge_count)),
            clusters=escape(str(isolated_cluster_count)),
        )
    )
    report_actions = graph_report.get("topActions", []) if isinstance(graph_report.get("topActions"), list) else []
    if report_actions:
        graph_snapshot_items.append(_render_bullet_list(
            [escape(str(item)) for item in report_actions[:3]],
            "No additional governance actions.",
        ))
    graph_snapshot_html = "\n".join(graph_snapshot_items) if graph_snapshot_items else "<div class='empty small'>Graph insights will appear after you build the graph.</div>"

    html = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>ThinkWiki Outputs</title>
  <style>
    :root {{
      --bg: #0b1020;
      --panel: #121935;
      --text: #edf2ff;
      --muted: #a8b3cf;
      --border: rgba(255,255,255,0.1);
      --accent: #8ab4ff;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      min-height: 100vh;
      font-family: ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: linear-gradient(180deg, #0b1020 0%, #10172f 100%);
      color: var(--text);
      display: grid;
      place-items: center;
      padding: 24px;
    }}
    .shell {{
      width: min(880px, 100%);
      background: rgba(9, 13, 28, 0.86);
      border: 1px solid var(--border);
      border-radius: 24px;
      padding: 28px;
    }}
    h1, p {{ margin-top: 0; }}
    .lead {{
      color: var(--muted);
      line-height: 1.6;
      margin-bottom: 20px;
    }}
    .hero {{
      display: grid;
      gap: 18px;
      margin-bottom: 24px;
    }}
    .eyebrow {{
      color: var(--accent);
      text-transform: uppercase;
      letter-spacing: 0.08em;
      font-size: 0.82rem;
      margin-bottom: 10px;
    }}
    .hero-title {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      flex-wrap: wrap;
    }}
    .hero-title h1 {{
      margin-bottom: 0;
    }}
    .meta {{
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
    }}
    .badge {{
      border: 1px solid var(--border);
      border-radius: 999px;
      padding: 6px 12px;
      color: var(--muted);
      font-size: 0.92rem;
      background: rgba(255,255,255,0.03);
    }}
    .stats {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
      gap: 12px;
    }}
    .stat {{
      border: 1px solid var(--border);
      background: var(--panel);
      border-radius: 18px;
      padding: 16px;
    }}
    .stat strong {{
      display: block;
      font-size: 1.45rem;
      margin-bottom: 6px;
    }}
    .stat span {{
      color: var(--muted);
    }}
    .grid {{
      display: grid;
      gap: 14px;
    }}
    .workspace-grid {{
      display: grid;
      gap: 14px;
      grid-template-columns: 1.1fr 0.9fr;
      margin-top: 18px;
    }}
    .section-grid {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 14px;
      margin-top: 18px;
    }}
    .panel {{
      border: 1px solid var(--border);
      background: rgba(255,255,255,0.02);
      border-radius: 18px;
      padding: 18px;
    }}
    .panel h2 {{
      margin: 0 0 8px;
      font-size: 1rem;
    }}
    .panel p {{
      margin: 0 0 14px;
      color: var(--muted);
      line-height: 1.5;
    }}
    .card {{
      display: block;
      text-decoration: none;
      color: inherit;
      border: 1px solid var(--border);
      background: var(--panel);
      border-radius: 18px;
      padding: 18px;
    }}
    .card:hover {{
      border-color: rgba(138,180,255,0.55);
      box-shadow: 0 0 0 1px rgba(138,180,255,0.18);
    }}
    .card strong {{
      display: block;
      margin-bottom: 6px;
      font-size: 1.05rem;
    }}
    .card span {{
      display: block;
      color: var(--muted);
      margin-bottom: 10px;
    }}
    code {{
      color: var(--accent);
      font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
      word-break: break-word;
    }}
    .empty {{
      border: 1px dashed var(--border);
      border-radius: 18px;
      padding: 18px;
      color: var(--muted);
    }}
    .small {{
      padding: 14px;
      font-size: 0.95rem;
    }}
    .mini-card {{
      display: block;
      text-decoration: none;
      color: inherit;
      border: 1px solid var(--border);
      background: rgba(18, 25, 53, 0.85);
      border-radius: 16px;
      padding: 14px;
      margin-bottom: 10px;
    }}
    .mini-card:last-child {{
      margin-bottom: 0;
    }}
    .mini-card:hover {{
      border-color: rgba(138,180,255,0.55);
    }}
    .mini-card strong {{
      display: block;
      margin-bottom: 6px;
    }}
    .quality {{
      display: inline-block;
      margin-top: 8px;
      border-radius: 999px;
      padding: 4px 8px;
      font-size: 0.82rem;
      text-transform: uppercase;
      letter-spacing: 0.04em;
    }}
    .quality-ready {{
      background: rgba(47, 163, 91, 0.16);
      color: #8de2a7;
    }}
    .quality-review {{
      background: rgba(242, 166, 43, 0.16);
      color: #ffd08a;
    }}
    .quality-weak {{
      background: rgba(214, 77, 77, 0.16);
      color: #ff9f9f;
    }}
    .quality-media {{
      background: rgba(104, 114, 255, 0.16);
      color: #b9c0ff;
    }}
    .mini-card span {{
      display: block;
      color: var(--muted);
      line-height: 1.45;
    }}
    .mini-meta {{
      display: flex;
      justify-content: space-between;
      gap: 12px;
      margin-bottom: 8px;
      color: var(--muted);
      font-size: 0.88rem;
    }}
    .mini-type {{
      text-transform: uppercase;
      letter-spacing: 0.04em;
      color: var(--accent);
    }}
    .guide {{
      margin-top: 18px;
      border: 1px solid rgba(138,180,255,0.22);
      background: rgba(138,180,255,0.08);
      border-radius: 18px;
      padding: 16px 18px;
    }}
    .guide strong {{
      display: block;
      margin-bottom: 8px;
    }}
    .guide span {{
      color: var(--muted);
      line-height: 1.55;
    }}
    .bullet-list {{
      margin: 0;
      padding-left: 18px;
      color: var(--muted);
      display: grid;
      gap: 10px;
      line-height: 1.5;
    }}
    .bullet-list strong {{
      color: var(--text);
    }}
    .actions {{
      display: grid;
      gap: 10px;
    }}
    .action-card {{
      display: block;
      text-decoration: none;
      color: inherit;
      border: 1px solid var(--border);
      background: rgba(18, 25, 53, 0.85);
      border-radius: 16px;
      padding: 14px;
    }}
    .action-card:hover {{
      border-color: rgba(138,180,255,0.55);
    }}
    .action-card strong {{
      display: block;
      margin: 6px 0;
    }}
    .action-card span {{
      color: var(--muted);
      line-height: 1.45;
      display: block;
    }}
    .action-tag {{
      display: inline-block;
      font-size: 0.8rem;
      letter-spacing: 0.04em;
      text-transform: uppercase;
      color: var(--accent);
    }}
    .snapshot {{
      display: grid;
      gap: 10px;
    }}
    .snapshot-copy {{
      color: var(--muted);
      line-height: 1.55;
    }}
    .snapshot-chip {{
      border: 1px solid var(--border);
      border-radius: 14px;
      background: rgba(255,255,255,0.03);
      padding: 12px 14px;
      color: var(--muted);
    }}
    .snapshot-chip strong {{
      color: var(--text);
    }}
    @media (max-width: 720px) {{
      .stats {{
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }}
      .workspace-grid {{
        grid-template-columns: 1fr;
      }}
      .section-grid {{
        grid-template-columns: 1fr;
      }}
    }}
  </style>
</head>
<body>
  <main class="shell">
    <section class="hero">
      <div class="eyebrow">Knowledge Workspace</div>
      <div class="hero-title">
        <h1>{wiki_title}</h1>
        <div class="meta">
          <span class="badge">Workspace Home</span>
          <span class="badge">Generated {generated_at}</span>
        </div>
      </div>
      <p class="lead">This is more than an output index. It is the current workspace home for the wiki, where you can see what changed, what needs attention, and what is still waiting in the inbox before deciding whether to open the viewer or the graph.</p>
      <div class="stats">
        {stats}
      </div>
    </section>
    <div class="workspace-grid">
      <section class="panel">
        <h2>What Changed</h2>
        <p>This section highlights recently updated and recently generated pages so you can quickly see what changed in the wiki.</p>
        {recent_pages}
        <div style="height: 12px;"></div>
        {generated_pages}
      </section>
      <section class="panel">
        <h2>Next Actions</h2>
        <p>Jump directly into the most valuable next step instead of manually deciding where to look first.</p>
        <div class="actions">
          {actions}
        </div>
      </section>
    </div>
    <div class="workspace-grid">
      <section class="panel">
        <h2>Needs Attention</h2>
        <p>This section highlights the weakest spots in the current knowledge base, such as isolated pages, weakly connected pages, or pages missing summaries and sources.</p>
        {attention}
      </section>
      <section class="panel">
        <h2>Graph Snapshot</h2>
        <p>Read structural graph insights directly from the knowledge graph so the home page can tell you what matters most right now.</p>
        <div class="snapshot">
          {graph_snapshot}
        </div>
      </section>
    </div>
    <div class="section-grid">
      <section class="panel">
        <h2>Featured Pages</h2>
        <p>Surface concept, decision, synthesis, and source pages first so you can spot the most valuable knowledge artifacts quickly.</p>
        {featured_pages}
      </section>
      <section class="panel">
        <h2>Outputs Overview</h2>
        <p>The viewer and graph remain the two most important outputs, but they now live inside one unified workspace view.</p>
        <div class="grid">
          {items}
        </div>
      </section>
      <section class="panel">
        <h2>Inbox Queue</h2>
        <p>This section shows the most recent inbox captures. Open the raw item first for a quick review, then decide whether to run ingest.</p>
        {inbox_items}
      </section>
    </div>
    <div class="guide">
      <strong>Start here</strong>
      <span>Start with `What Changed`, `Needs Attention`, and `Inbox Queue`, then decide whether to open the viewer or the graph. If you just imported or captured new material, rerun viewer and graph to refresh this home page.</span>
    </div>
  </main>
</body>
</html>
""".format(
        wiki_title=escape(wiki_title),
        generated_at=escape(generated_at),
        stats="\n".join(stats),
        items="\n".join(output_items),
        recent_pages=recent_pages_html,
        generated_pages=generated_pages_html,
        actions=actions_html,
        attention=attention_html,
        graph_snapshot=graph_snapshot_html,
        featured_pages=featured_pages_html,
        inbox_items=inbox_html,
    )
    target = output_dir / "index.html"
    write_text(target, html)
    return target


def write_inbox_review(root: Path) -> Path:
    output_dir = root / "output"
    inbox_dir = output_dir / "inbox"
    inbox_path = inbox_dir / "index.html"
    items = collect_inbox_items(root)
    groups = _inbox_groups(items)
    summary = _inbox_quality_summary(items)
    priority_items = _priority_inbox_items(items)
    priority_commands = [str(item.get("ingest_command", "") or "") for item in priority_items if str(item.get("ingest_command", "") or "")]
    priority_html = _render_inbox_list(priority_items, "No priority inbox items yet.")
    sections_html = "\n".join([
        _render_inbox_review_section(
            anchor="ready",
            title="Ready To Ingest",
            description="These captures have strong metadata and article-body quality. They are usually ready for final review before formal ingest.",
            items=groups.get("ready", []),
            inbox_dir=inbox_dir,
            root=root,
            empty_text="There are no Ready items for ingest yet.",
        ),
        _render_inbox_review_section(
            anchor="review",
            title="Needs Review",
            description="These captures are usually readable, but you should still verify the source, author, publish date, or article completeness.",
            items=groups.get("review", []),
            inbox_dir=inbox_dir,
            root=root,
            empty_text="There are no items in review right now.",
        ),
        _render_inbox_review_section(
            anchor="weak",
            title="Weak Captures",
            description="Review these captures manually first to confirm they are not loading pages, summary-only pages, or low-information captures.",
            items=groups.get("weak", []),
            inbox_dir=inbox_dir,
            root=root,
            empty_text="There are no weak captures right now.",
        ),
    ]) if items else "<div class='empty'>There are no inbox items yet. Run `python scripts/thinkwiki clip ...` to collect webpages, text, or files first.</div>"
    html = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>ThinkWiki Inbox Review</title>
  <style>
    :root {{
      --bg: #0b1020;
      --panel: #121935;
      --text: #edf2ff;
      --muted: #a8b3cf;
      --border: rgba(255,255,255,0.1);
      --accent: #8ab4ff;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      min-height: 100vh;
      font-family: ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: linear-gradient(180deg, #0b1020 0%, #10172f 100%);
      color: var(--text);
      padding: 24px;
    }}
    .shell {{
      width: min(1100px, 100%);
      margin: 0 auto;
    }}
    .hero {{
      margin-bottom: 22px;
      border: 1px solid var(--border);
      background: rgba(9, 13, 28, 0.86);
      border-radius: 24px;
      padding: 28px;
    }}
    .eyebrow {{
      color: var(--accent);
      text-transform: uppercase;
      letter-spacing: 0.08em;
      font-size: 0.82rem;
      margin-bottom: 10px;
    }}
    h1, h2, p {{ margin-top: 0; }}
    .lead {{
      color: var(--muted);
      line-height: 1.6;
      margin-bottom: 18px;
      max-width: 70ch;
    }}
    .hero-grid {{
      display: grid;
      grid-template-columns: minmax(0, 1.2fr) minmax(300px, 0.8fr);
      gap: 16px;
      align-items: start;
    }}
    .badges {{
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
    }}
    .badge {{
      border: 1px solid var(--border);
      border-radius: 999px;
      padding: 6px 12px;
      color: var(--muted);
      background: rgba(255,255,255,0.03);
    }}
    .cards {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
      gap: 14px;
    }}
    .panel {{
      border: 1px solid var(--border);
      background: rgba(255,255,255,0.03);
      border-radius: 18px;
      padding: 18px;
    }}
    .summary-grid {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 10px;
      margin: 18px 0 0;
    }}
    .summary-stat {{
      border: 1px solid var(--border);
      border-radius: 16px;
      padding: 14px;
      background: rgba(255,255,255,0.03);
    }}
    .summary-stat strong {{
      display: block;
      font-size: 1.4rem;
      margin-bottom: 6px;
    }}
    .summary-stat span {{
      color: var(--muted);
    }}
    .group {{
      margin-top: 18px;
      border: 1px solid var(--border);
      background: rgba(9, 13, 28, 0.78);
      border-radius: 22px;
      padding: 20px;
    }}
    .group-head {{
      display: flex;
      justify-content: space-between;
      gap: 16px;
      align-items: start;
      margin-bottom: 16px;
    }}
    .group-head p {{
      color: var(--muted);
      margin-bottom: 0;
      max-width: 70ch;
    }}
    .group-commands {{
      margin-bottom: 16px;
    }}
    .command-pre {{
      margin-bottom: 10px;
    }}
    .card {{
      border: 1px solid var(--border);
      background: rgba(255,255,255,0.03);
      border-radius: 18px;
      padding: 18px;
    }}
    .card h3 {{
      margin-top: 0;
    }}
    .meta {{
      display: flex;
      justify-content: space-between;
      gap: 12px;
      color: var(--muted);
      font-size: 0.9rem;
      margin-bottom: 10px;
    }}
    .tag {{
      color: var(--accent);
      text-transform: uppercase;
      letter-spacing: 0.04em;
    }}
    .card p {{
      color: var(--muted);
      line-height: 1.55;
    }}
    .facts {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-bottom: 14px;
    }}
    .fact {{
      border: 1px solid var(--border);
      border-radius: 999px;
      padding: 6px 10px;
      color: var(--muted);
      background: rgba(255,255,255,0.02);
      font-size: 0.9rem;
      text-decoration: none;
    }}
    .fact strong {{
      color: var(--text);
    }}
    .fact-link {{
      max-width: 100%;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }}
    .path {{
      margin: 14px 0;
    }}
    .quality-note {{
      color: var(--muted);
      line-height: 1.5;
      margin-bottom: 14px;
    }}
    .actions {{
      display: flex;
      gap: 14px;
      flex-wrap: wrap;
      margin-bottom: 14px;
    }}
    a {{
      color: var(--accent);
      text-decoration: none;
    }}
    a:hover {{
      text-decoration: underline;
    }}
    .command-label {{
      color: var(--muted);
      font-size: 0.92rem;
      margin-bottom: 8px;
    }}
    pre {{
      margin: 0;
      padding: 14px;
      border-radius: 14px;
      border: 1px solid var(--border);
      background: var(--panel);
      color: var(--accent);
      white-space: pre-wrap;
      word-break: break-word;
      font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    }}
    .empty {{
      border: 1px dashed var(--border);
      border-radius: 18px;
      padding: 18px;
      color: var(--muted);
      background: rgba(255,255,255,0.02);
    }}
    @media (max-width: 900px) {{
      .hero-grid {{
        grid-template-columns: 1fr;
      }}
      .summary-grid {{
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }}
    }}
    @media (max-width: 640px) {{
      .summary-grid {{
        grid-template-columns: 1fr;
      }}
      .group-head {{
        flex-direction: column;
      }}
    }}
  </style>
</head>
<body>
  <main class="shell">
    <section class="hero">
      <div class="eyebrow">Inbox Review</div>
      <div class="hero-grid">
        <div>
          <h1>{wiki_title}</h1>
          <p class="lead">This page gathers everything that has been clipped into the inbox but not formally ingested yet. Items are grouped into `ready / review / weak` so you can process the highest-value captures first and come back to the ones that need manual inspection.</p>
          <div class="badges">
            <span class="badge">Items {count}</span>
            <span class="badge"><a href="../index.html" target="_blank" rel="noopener">Open workspace home</a></span>
          </div>
          <div class="summary-grid">
            <div class="summary-stat"><strong>{count}</strong><span>Total</span></div>
            <div class="summary-stat"><strong>{ready_count}</strong><span>Ready</span></div>
            <div class="summary-stat"><strong>{review_count}</strong><span>Review</span></div>
            <div class="summary-stat"><strong>{weak_count}</strong><span>Weak</span></div>
          </div>
        </div>
        <div class="panel">
          <h2>Priority Queue</h2>
          <p>This section lists the items that deserve attention first. The usual priority is ready -> review -> weak.</p>
          {priority_items}
          <div class="command-label" style="margin-top: 14px;">Recommended priority commands</div>
          {priority_commands}
        </div>
      </div>
    </section>
    {sections}
  </main>
</body>
</html>
""".format(
        wiki_title=escape(_first_markdown_heading(root / "index.md") or root.name),
        count=escape(str(len(items))),
        ready_count=escape(str(summary.get("ready", 0))),
        review_count=escape(str(summary.get("review", 0))),
        weak_count=escape(str(summary.get("weak", 0))),
        priority_items=priority_html,
        priority_commands=_render_command_list(priority_commands[:3], "No ingest commands to recommend yet."),
        sections=sections_html,
    )
    write_text(inbox_path, html)
    return inbox_path


def refresh_output_home_if_present(root: Path) -> Path | None:
    output_dir = root / "output"
    viewer_exists = (output_dir / "viewer" / "index.html").exists()
    graph_exists = (output_dir / "graph" / "index.html").exists()
    inbox_exists = (output_dir / "inbox" / "index.html").exists()
    if not (viewer_exists or graph_exists or inbox_exists):
        return None
    return write_output_home(root)


def output_access_lines(root: Path) -> list[str]:
    output_dir = root / "output"
    viewer_exists = (output_dir / "viewer" / "index.html").exists()
    graph_exists = (output_dir / "graph" / "index.html").exists()
    output_home = refresh_output_home_if_present(root)

    lines: list[str] = []
    if output_home is not None:
        lines.append("Output hub: output/index.html")
        lines.append(f"Output hub URI: {file_uri(output_home)}")
        lines.append(
            "Browse via HTTP: "
            f"`python scripts/thinkwiki serve --root {display_root_arg(root)}` "
            f"-> {output_http_url('index.html')}"
        )
        if viewer_exists and not graph_exists:
            lines.append(f"Next: run `python scripts/thinkwiki graph --root {root}` to generate the graph page.")
        elif graph_exists and not viewer_exists:
            lines.append(f"Next: run `python scripts/thinkwiki viewer --root {root}` to generate the viewer page.")
        return lines

    lines.append(f"Next: run `python scripts/thinkwiki viewer --root {root}` to generate the local viewer page.")
    lines.append(f"Next: run `python scripts/thinkwiki graph --root {root}` to generate the knowledge graph page.")
    return lines


def render_template(template: str, values: Dict[str, str]) -> str:
    for key, value in values.items():
        template = template.replace("{{" + key + "}}", value)
    return template


def load_template(name: str) -> str:
    return read_text(repo_root_from_script() / "templates" / name)


def unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    counter = 2
    while True:
        candidate = path.with_name(f"{stem}-{counter}{suffix}")
        if not candidate.exists():
            return candidate
        counter += 1


def classify_raw_dir(source_path: Path | None, is_text: bool = False) -> str:
    if is_text or source_path is None:
        return "articles"
    suffix = source_path.suffix.lower()
    if suffix == ".pdf":
        return "papers"
    if suffix in {".epub", ".mobi"}:
        return "books"
    if suffix in {".json", ".jsonl"}:
        return "conversations"
    return "articles"


def parse_frontmatter(text: str) -> Tuple[Dict[str, object], str]:
    if not text.startswith("---\n"):
        return {}, text
    parts = text.split("\n---\n", 1)
    if len(parts) != 2:
        return {}, text
    frontmatter, body = parts
    lines = frontmatter.splitlines()[1:]
    meta: Dict[str, object] = {}
    current_list_key = None
    for raw in lines:
        line = raw.rstrip()
        if not line:
            continue
        if line.startswith("  - ") and current_list_key:
            meta.setdefault(current_list_key, []).append(line[4:].strip())
            continue
        if ": " in line:
            key, value = line.split(": ", 1)
            meta[key.strip()] = value.strip()
            current_list_key = None
        elif line.endswith(":"):
            key = line[:-1].strip()
            meta[key] = []
            current_list_key = key
    return meta, body


def extract_summary(meta: Dict[str, object], body: str) -> str:
    if meta.get("summary"):
        return str(meta["summary"])
    lines = [line.strip() for line in body.splitlines()]
    for line in lines:
        if not line or line.startswith("#") or line.startswith("- ") or line.startswith("```"):
            continue
        return line[:120]
    return "(no summary)"


def markdown_links(text: str) -> List[str]:
    return re.findall(r"\[[^\]]+\]\(([^)]+)\)", text)


def is_external_link(target: str) -> bool:
    return target.startswith(("http://", "https://", "mailto:", "#"))


def collect_wiki_pages(root: Path) -> List[Path]:
    pages: List[Path] = []
    for subdir in WIKI_DIRS:
        pages.extend(sorted((root / "wiki" / subdir).glob("*.md")))
    return pages


def normalize_repo_path(root: Path, value: str) -> str:
    path = Path(value)
    if path.is_absolute():
        resolved = path.resolve()
        try:
            path = resolved.relative_to(root.resolve())
        except ValueError:
            return resolved.as_posix()
    return path.as_posix().lstrip("./")


def relative_link(from_page: Path, root: Path, target: str) -> str:
    target_path = root / normalize_repo_path(root, target)
    return Path(os.path.relpath(target_path, start=from_page.parent)).as_posix()


def markdown_link_list(from_page: Path, root: Path, targets: Iterable[str]) -> str:
    items = []
    for target in targets:
        normalized = normalize_repo_path(root, target)
        label = Path(normalized).stem.replace("-", " ").replace("_", " ").strip() or normalized
        items.append(f"- [{label}]({relative_link(from_page, root, normalized)})")
    return "\n".join(items)


def frontmatter_list(items: Iterable[str], fallback: str) -> str:
    values = [item for item in items if item]
    if not values:
        values = [fallback]
    return "\n".join(f"  - {item}" for item in values)


def append_log(root: Path, heading: str, lines: Iterable[str]) -> None:
    log_path = root / "log.md"
    current = read_text(log_path).rstrip()
    block = "## " + heading + "\n" + "\n".join(lines)
    if current:
        current += "\n\n" + block
    else:
        current = "# Wiki Log\n\n" + block
    write_text(log_path, current)
