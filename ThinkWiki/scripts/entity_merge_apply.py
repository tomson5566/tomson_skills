#!/usr/bin/env python3
from __future__ import annotations

"""
ThinkWiki Script: entity_merge_apply

Purpose:
- Preview or apply a deterministic entity merge into a canonical entity page.

Usage:
- Prefer `python scripts/thinkwiki entity-merge-apply ...`.
- Run `python scripts/<script> --help` for direct CLI details when the file exposes its own arguments.
"""


import argparse
import json
import os
import subprocess
import sys
from html import escape
from pathlib import Path

from utils import (
    ambiguous_entity_merge_candidates,
    append_log,
    file_uri,
    find_repo_root,
    parse_frontmatter,
    read_text,
    today_str,
    unique_strings,
    write_output_home,
    write_text,
)

FRONTMATTER_ORDER = [
    "title",
    "type",
    "created",
    "updated",
    "summary",
    "canonical_entity",
    "sources",
    "aliases",
    "topics",
    "tags",
    "confidence",
    "status",
    "maturity",
]


def _load_graph(root: Path) -> dict[str, object]:
    graph_path = root / "output" / "graph" / "graph.json"
    if not graph_path.exists():
        raise SystemExit("Graph data not found. Run `python scripts/thinkwiki graph --root <wiki-root>` first.")
    try:
        return json.loads(graph_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise SystemExit(f"Invalid graph data: {graph_path} ({exc})") from exc


def _knowledge_entity_nodes(graph: dict[str, object]) -> list[dict[str, object]]:
    views = graph.get("views", {})
    if isinstance(views, dict):
        knowledge = views.get("knowledge", {})
        if isinstance(knowledge, dict):
            nodes = knowledge.get("nodes", [])
            if isinstance(nodes, list):
                return [
                    node for node in nodes
                    if isinstance(node, dict) and str(node.get("type", "") or "") == "entity"
                ]
    return []


def _meta_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if value:
        return [str(value).strip()]
    return []


def _relative_link(from_page: Path, to_page: Path) -> str:
    return Path(os.path.relpath(to_page, start=from_page.parent)).as_posix()


def _serialize_frontmatter(meta: dict[str, object]) -> str:
    lines = ["---"]
    handled: set[str] = set()
    for key in FRONTMATTER_ORDER:
        if key not in meta:
            continue
        handled.add(key)
        value = meta[key]
        if isinstance(value, list):
            lines.append(f"{key}:")
            for item in value:
                item_text = str(item).strip()
                if item_text:
                    lines.append(f"  - {item_text}")
        else:
            lines.append(f"{key}: {str(value).strip()}")
    for key in sorted(meta.keys()):
        if key in handled:
            continue
        value = meta[key]
        if isinstance(value, list):
            lines.append(f"{key}:")
            for item in value:
                item_text = str(item).strip()
                if item_text:
                    lines.append(f"  - {item_text}")
        else:
            lines.append(f"{key}: {str(value).strip()}")
    lines.append("---")
    return "\n".join(lines)


def _write_page(path: Path, meta: dict[str, object], body: str) -> None:
    write_text(path, _serialize_frontmatter(meta) + "\n\n" + body.strip())


def _merged_entity_body(merged_title: str, canonical_title: str, merged_page: Path, canonical_page: Path, aliases: list[str]) -> str:
    canonical_link = _relative_link(merged_page, canonical_page)
    alias_lines = "\n".join(f"- {alias}" for alias in aliases) or "- (none)"
    return "\n".join([
        f"# {merged_title}",
        "",
        "## Summary",
        "",
        f"This entity page has been merged into [{canonical_title}]({canonical_link}).",
        "",
        "## Canonical Entity",
        "",
        f"- [{canonical_title}]({canonical_link})",
        "",
        "## Aliases",
        "",
        alias_lines,
    ])


def _resolve_entity_id(candidates: list[dict[str, object]], selector: str) -> str:
    needle = selector.strip()
    if not needle:
        raise SystemExit("Canonical entity selector cannot be empty.")
    normalized = needle.casefold()
    matched_ids = []
    for item in candidates:
        for entity_id, title in zip(item.get("entityIds", []), item.get("titles", [])):
            entity_id_text = str(entity_id)
            title_text = str(title)
            if normalized in {entity_id_text.casefold(), title_text.casefold(), Path(entity_id_text).stem.casefold()}:
                matched_ids.append(entity_id_text)
    matched_ids = unique_strings(matched_ids)
    if len(matched_ids) != 1:
        raise SystemExit(f"Could not resolve canonical entity selector uniquely: {selector}")
    return matched_ids[0]


def _run_follow_up(root: Path, script_name: str) -> None:
    subprocess.run(
        [sys.executable, str(Path(__file__).with_name(script_name)), "--root", str(root)],
        check=True,
        cwd=root.parent,
        capture_output=True,
        text=True,
    )


def _build_merge_plan(
    *,
    root: Path,
    identity_key: str,
    canonical_entity_id: str,
    candidate: dict[str, object],
) -> dict[str, object]:
    entity_ids = [str(item) for item in candidate.get("entityIds", []) if str(item).strip()]
    merged_entity_ids = [entity_id for entity_id in entity_ids if entity_id != canonical_entity_id]
    if not merged_entity_ids:
        raise SystemExit("Nothing to merge: canonical entity is the only candidate.")

    canonical_page = root / canonical_entity_id
    if not canonical_page.exists():
        raise SystemExit(f"Canonical entity page not found: {canonical_entity_id}")
    canonical_meta, canonical_body = parse_frontmatter(read_text(canonical_page))
    canonical_title = str(canonical_meta.get("title") or canonical_page.stem).strip() or canonical_page.stem

    canonical_before_aliases = _meta_list(canonical_meta.get("aliases", []))
    canonical_before_sources = _meta_list(canonical_meta.get("sources", []))
    canonical_before_topics = _meta_list(canonical_meta.get("topics", []))
    merged_sources = list(canonical_before_sources)
    merged_topics = list(canonical_before_topics)
    merged_aliases = list(canonical_before_aliases)
    merged_pages: list[dict[str, object]] = []

    for merged_entity_id in merged_entity_ids:
        merged_page = root / merged_entity_id
        if not merged_page.exists():
            raise SystemExit(f"Merged entity page not found: {merged_entity_id}")
        merged_meta, _merged_body = parse_frontmatter(read_text(merged_page))
        merged_title = str(merged_meta.get("title") or merged_page.stem).strip() or merged_page.stem
        merged_sources.extend(_meta_list(merged_meta.get("sources", [])))
        merged_topics.extend(_meta_list(merged_meta.get("topics", [])))
        merged_aliases.extend([merged_title, *_meta_list(merged_meta.get("aliases", []))])
        merged_after_meta = dict(merged_meta)
        merged_after_meta["type"] = "entity"
        merged_after_meta["updated"] = today_str()
        merged_after_meta["status"] = "merged"
        merged_after_meta["canonical_entity"] = canonical_entity_id
        merged_after_meta["maturity"] = "merged"
        merged_after_meta["summary"] = f"This entity has been merged into {canonical_title}."
        merged_after_meta["sources"] = unique_strings(_meta_list(merged_meta.get("sources", [])) + merged_sources)
        merged_after_meta["topics"] = unique_strings(_meta_list(merged_meta.get("topics", [])) + merged_topics)
        merged_after_meta["aliases"] = unique_strings([merged_title, *_meta_list(merged_meta.get("aliases", []))])
        merged_after_body = _merged_entity_body(
            merged_title=merged_title,
            canonical_title=canonical_title,
            merged_page=merged_page,
            canonical_page=canonical_page,
            aliases=_meta_list(merged_after_meta.get("aliases", [])),
        )
        merged_pages.append({
            "id": merged_entity_id,
            "title": merged_title,
            "beforeStatus": str(merged_meta.get("status") or "").strip(),
            "afterStatus": "merged",
            "canonicalEntity": canonical_entity_id,
            "beforeAliases": _meta_list(merged_meta.get("aliases", [])),
            "afterAliases": _meta_list(merged_after_meta.get("aliases", [])),
            "afterMeta": merged_after_meta,
            "afterBody": merged_after_body,
        })

    canonical_after_meta = dict(canonical_meta)
    canonical_after_meta["type"] = "entity"
    canonical_after_meta["updated"] = today_str()
    canonical_after_meta["status"] = "active"
    canonical_after_meta["maturity"] = str(canonical_after_meta.get("maturity") or "emerging").strip() or "emerging"
    canonical_after_meta.pop("canonical_entity", None)
    canonical_after_meta["sources"] = unique_strings(merged_sources)
    canonical_after_meta["topics"] = unique_strings(merged_topics)
    canonical_after_meta["aliases"] = [
        item for item in unique_strings(merged_aliases)
        if item.casefold() != canonical_title.casefold()
    ]
    if not str(canonical_after_meta.get("summary") or "").strip():
        canonical_after_meta["summary"] = f"{canonical_title} is an entity tracked in ThinkWiki."

    return {
        "generated_at": today_str(),
        "identityKey": identity_key,
        "summary": "This is a dry-run merge preview." if merged_pages else "No entity pages will be merged.",
        "canonical": {
            "id": canonical_entity_id,
            "title": canonical_title,
            "before": {
                "status": str(canonical_meta.get("status") or "").strip(),
                "aliases": canonical_before_aliases,
                "sources": canonical_before_sources,
                "topics": canonical_before_topics,
            },
            "after": {
                "status": str(canonical_after_meta.get("status") or "").strip(),
                "aliases": _meta_list(canonical_after_meta.get("aliases", [])),
                "sources": _meta_list(canonical_after_meta.get("sources", [])),
                "topics": _meta_list(canonical_after_meta.get("topics", [])),
            },
            "addedAliases": [
                item for item in _meta_list(canonical_after_meta.get("aliases", []))
                if item not in canonical_before_aliases
            ],
            "addedSources": [
                item for item in _meta_list(canonical_after_meta.get("sources", []))
                if item not in canonical_before_sources
            ],
            "addedTopics": [
                item for item in _meta_list(canonical_after_meta.get("topics", []))
                if item not in canonical_before_topics
            ],
            "afterMeta": canonical_after_meta,
            "afterBody": canonical_body or f"# {canonical_title}",
        },
        "mergedPages": merged_pages,
        "stats": {
            "mergedPageCount": len(merged_pages),
            "addedAliasCount": len([
                item for item in _meta_list(canonical_after_meta.get("aliases", []))
                if item not in canonical_before_aliases
            ]),
            "addedSourceCount": len([
                item for item in _meta_list(canonical_after_meta.get("sources", []))
                if item not in canonical_before_sources
            ]),
            "addedTopicCount": len([
                item for item in _meta_list(canonical_after_meta.get("topics", []))
                if item not in canonical_before_topics
            ]),
        },
    }


def render_plan_markdown(plan: dict[str, object]) -> str:
    canonical = plan["canonical"]
    stats = plan["stats"]
    assert isinstance(canonical, dict)
    assert isinstance(stats, dict)
    lines = [
        "# ThinkWiki Entity Merge Plan",
        "",
        f"- Generated: {plan['generated_at']}",
        f"- Identity Key: {plan['identityKey']}",
        f"- Canonical: {canonical['id']}",
        f"- Merged Pages: {stats['mergedPageCount']}",
        f"- Added Aliases: {stats['addedAliasCount']}",
        f"- Added Sources: {stats['addedSourceCount']}",
        f"- Added Topics: {stats['addedTopicCount']}",
        "",
        "## Canonical Preview",
        "",
        f"- Title: {canonical['title']}",
        f"- Added Aliases: {', '.join(canonical['addedAliases']) or 'none'}",
        f"- Added Sources: {', '.join(canonical['addedSources']) or 'none'}",
        f"- Added Topics: {', '.join(canonical['addedTopics']) or 'none'}",
        "",
        "## Merged Pages",
        "",
    ]
    merged_pages = plan.get("mergedPages", [])
    if isinstance(merged_pages, list) and merged_pages:
        for item in merged_pages:
            lines.extend([
                f"- {item['id']}",
                f"  Title: {item['title']}",
                f"  Status: {item['beforeStatus'] or 'active'} -> {item['afterStatus']}",
                f"  Canonical: {item['canonicalEntity']}",
                "",
            ])
    else:
        lines.append("- No merged pages")
    return "\n".join(lines).rstrip()


def render_plan_html(plan: dict[str, object]) -> str:
    canonical = plan["canonical"]
    stats = plan["stats"]
    assert isinstance(canonical, dict)
    assert isinstance(stats, dict)
    merged_pages = plan.get("mergedPages", [])
    merged_cards = []
    if isinstance(merged_pages, list):
        for item in merged_pages:
            merged_cards.append(
                "<div class='record-card'>"
                "<strong>{title}</strong>"
                "<div class='record-meta'>{entity_id}</div>"
                "<p>Status {before_status} -> {after_status}</p>"
                "<p>Canonical: {canonical}</p>"
                "</div>".format(
                    title=escape(str(item.get("title") or "")),
                    entity_id=escape(str(item.get("id") or "")),
                    before_status=escape(str(item.get("beforeStatus") or "active")),
                    after_status=escape(str(item.get("afterStatus") or "merged")),
                    canonical=escape(str(item.get("canonicalEntity") or "")),
                )
            )
    merged_html = "\n".join(merged_cards) if merged_cards else "<div class='empty'>No merged pages.</div>"
    return """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>ThinkWiki Entity Merge Plan</title>
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
    body {{ margin: 0; min-height: 100vh; font-family: ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: linear-gradient(180deg, #0b1020 0%, #10172f 100%); color: var(--text); padding: 24px; }}
    .shell {{ width: min(1080px, 100%); margin: 0 auto; border: 1px solid var(--border); border-radius: 24px; background: rgba(9, 13, 28, 0.86); padding: 28px; }}
    .lead, p {{ color: var(--muted); line-height: 1.6; }}
    .meta {{ display: flex; gap: 10px; flex-wrap: wrap; margin: 16px 0 24px; }}
    .badge {{ border: 1px solid var(--border); border-radius: 999px; padding: 6px 12px; color: var(--muted); background: rgba(255,255,255,0.03); font-size: 0.92rem; }}
    .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; margin-bottom: 24px; }}
    .stat {{ border: 1px solid var(--border); background: var(--panel); border-radius: 18px; padding: 16px; }}
    .stat strong {{ display: block; font-size: 1.4rem; margin-bottom: 6px; }}
    .layout {{ display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }}
    .panel {{ border: 1px solid var(--border); background: rgba(255,255,255,0.02); border-radius: 18px; padding: 18px; }}
    .record-card {{ border: 1px solid var(--border); background: var(--panel); border-radius: 16px; padding: 14px; margin-bottom: 10px; }}
    .record-card strong {{ display: block; margin-bottom: 6px; }}
    .record-meta {{ color: var(--accent); font-size: 0.88rem; margin-bottom: 8px; }}
    .empty {{ border: 1px dashed var(--border); border-radius: 16px; padding: 14px; color: var(--muted); }}
    ul {{ margin: 0; padding-left: 18px; color: var(--muted); }}
    a {{ color: var(--accent); }}
    @media (max-width: 860px) {{ .layout {{ grid-template-columns: 1fr; }} }}
  </style>
</head>
<body>
  <main class="shell">
    <h1>ThinkWiki Entity Merge Plan</h1>
    <p class="lead">Dry-run preview for entity merge apply. Review the canonical changes before writing files.</p>
    <div class="meta">
      <span class="badge">Generated {generated_at}</span>
      <span class="badge">Identity Key {identity_key}</span>
      <span class="badge"><a href="entity-merge-review.html">Open Entity Merge Review</a></span>
      <span class="badge"><a href="../index.html">Open Workspace Home</a></span>
    </div>
    <section class="stats">
      <div class="stat"><strong>{merged_page_count}</strong><span>Merged Pages</span></div>
      <div class="stat"><strong>{added_alias_count}</strong><span>Added Aliases</span></div>
      <div class="stat"><strong>{added_source_count}</strong><span>Added Sources</span></div>
      <div class="stat"><strong>{added_topic_count}</strong><span>Added Topics</span></div>
    </section>
    <div class="layout">
      <section class="panel">
        <h2>Canonical Preview</h2>
        <p>{canonical_title}</p>
        <ul>
          <li>Canonical Page: {canonical_id}</li>
          <li>Added Aliases: {added_aliases}</li>
          <li>Added Sources: {added_sources}</li>
          <li>Added Topics: {added_topics}</li>
        </ul>
      </section>
      <section class="panel">
        <h2>Merged Pages</h2>
        {merged_cards}
      </section>
    </div>
  </main>
</body>
</html>
""".format(
        generated_at=escape(str(plan.get("generated_at") or "")),
        identity_key=escape(str(plan.get("identityKey") or "")),
        merged_page_count=escape(str(stats.get("mergedPageCount", 0) or 0)),
        added_alias_count=escape(str(stats.get("addedAliasCount", 0) or 0)),
        added_source_count=escape(str(stats.get("addedSourceCount", 0) or 0)),
        added_topic_count=escape(str(stats.get("addedTopicCount", 0) or 0)),
        canonical_title=escape(str(canonical.get("title") or "")),
        canonical_id=escape(str(canonical.get("id") or "")),
        added_aliases=escape(", ".join(canonical.get("addedAliases", [])) or "none"),
        added_sources=escape(", ".join(canonical.get("addedSources", [])) or "none"),
        added_topics=escape(", ".join(canonical.get("addedTopics", [])) or "none"),
        merged_cards=merged_html,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply a reviewed entity merge to canonicalize ambiguous entity pages.")
    parser.add_argument("--root", default=".", help="Wiki root path")
    parser.add_argument("--identity-key", required=True, help="Identity key from entity-merge-review")
    parser.add_argument("--canonical", required=True, help="Canonical entity page id or title")
    parser.add_argument("--dry-run", action="store_true", help="Preview the merge without writing entity pages")
    args = parser.parse_args()

    root = find_repo_root(Path(args.root))
    graph = _load_graph(root)
    entity_nodes = _knowledge_entity_nodes(graph)
    candidates, _ambiguous_entity_count = ambiguous_entity_merge_candidates(entity_nodes)
    selected = [
        item for item in candidates
        if str(item.get("identityKey") or "").casefold() == args.identity_key.strip().casefold()
    ]
    if len(selected) != 1:
        raise SystemExit(f"Identity key not found or ambiguous in current review: {args.identity_key}")
    candidate = selected[0]
    entity_ids = [str(item) for item in candidate.get("entityIds", []) if str(item).strip()]
    if len(entity_ids) < 2:
        raise SystemExit("Selected identity key does not contain enough entity pages to merge.")

    canonical_entity_id = _resolve_entity_id(selected, args.canonical)
    plan = _build_merge_plan(
        root=root,
        identity_key=args.identity_key.strip(),
        canonical_entity_id=canonical_entity_id,
        candidate=candidate,
    )
    canonical = plan["canonical"]
    merged_pages = plan["mergedPages"]
    assert isinstance(canonical, dict)
    assert isinstance(merged_pages, list)

    if args.dry_run:
        plan_dir = root / "output" / "graph"
        plan_json_path = plan_dir / "entity-merge-plan.json"
        plan_md_path = plan_dir / "entity-merge-plan.md"
        plan_html_path = plan_dir / "entity-merge-plan.html"
        write_text(plan_json_path, json.dumps(plan, ensure_ascii=False, indent=2))
        write_text(plan_md_path, render_plan_markdown(plan))
        write_text(plan_html_path, render_plan_html(plan))
        output_home = write_output_home(root)
        append_log(root, f"[{today_str()}] entity-merge-plan | {args.identity_key}", [
            f"- canonical: {canonical_entity_id}",
            *[f"- preview merge: {item['id']}" for item in merged_pages],
            "- plan html: output/graph/entity-merge-plan.html",
            "- hub: output/index.html",
        ])
        print("# ThinkWiki Entity Merge Plan")
        print("")
        print(f"- Root: {root}")
        print(f"- Identity Key: {args.identity_key}")
        print(f"- Canonical: {canonical_entity_id}")
        print(f"- Merged Pages: {plan['stats']['mergedPageCount']}")
        print(f"- Added Aliases: {plan['stats']['addedAliasCount']}")
        print(f"- Added Sources: {plan['stats']['addedSourceCount']}")
        print(f"- Added Topics: {plan['stats']['addedTopicCount']}")
        print("")
        for item in merged_pages:
            print(f"- preview merge: {item['id']} -> {canonical_entity_id}")
        print("")
        print("Entity merge plan: output/graph/entity-merge-plan.html")
        print(f"Entity merge plan URI: {file_uri(plan_html_path)}")
        print("Entity merge plan markdown: output/graph/entity-merge-plan.md")
        print("Entity merge plan data: output/graph/entity-merge-plan.json")
        print("Output hub: output/index.html")
        print(f"Output hub URI: {file_uri(output_home)}")
        return 0

    canonical_page = root / str(canonical["id"])
    _write_page(canonical_page, dict(canonical["afterMeta"]), str(canonical["afterBody"]))
    merged_page_paths: list[str] = []
    for item in merged_pages:
        merged_page = root / str(item["id"])
        _write_page(merged_page, dict(item["afterMeta"]), str(item["afterBody"]))
        merged_page_paths.append(str(item["id"]))

    _run_follow_up(root, "build_viewer.py")
    _run_follow_up(root, "build_graph.py")
    _run_follow_up(root, "graph_report.py")
    _run_follow_up(root, "entity_merge_review.py")

    append_log(root, f"[{today_str()}] entity-merge-apply | {args.identity_key}", [
        f"- canonical: {canonical_entity_id}",
        *[f"- merged: {item}" for item in merged_page_paths],
        "- viewer: output/viewer/index.html",
        "- graph: output/graph/index.html",
        "- graph report: output/graph/report.html",
        "- merge review: output/graph/entity-merge-review.html",
    ])
    print("# ThinkWiki Entity Merge Apply")
    print("")
    print(f"- Root: {root}")
    print(f"- Identity Key: {args.identity_key}")
    print(f"- Canonical: {canonical_entity_id}")
    print(f"- Merged Pages: {len(merged_page_paths)}")
    print("")
    for merged_page in merged_page_paths:
        print(f"- merged: {merged_page} -> {canonical_entity_id}")
    print("")
    print("Viewer: output/viewer/index.html")
    print("Graph: output/graph/index.html")
    print("Graph report: output/graph/report.html")
    print("Entity merge review: output/graph/entity-merge-review.html")
    print(f"Entity merge review URI: {file_uri(root / 'output' / 'graph' / 'entity-merge-review.html')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
