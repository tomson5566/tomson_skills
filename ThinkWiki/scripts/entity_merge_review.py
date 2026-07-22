#!/usr/bin/env python3
from __future__ import annotations

"""
ThinkWiki Script: entity_merge_review

Purpose:
- Generate review artifacts for ambiguous entity alias groups in the current graph.

Usage:
- Prefer `python scripts/thinkwiki entity-merge-review ...`.
- Run `python scripts/<script> --help` for direct CLI details when the file exposes its own arguments.
"""


import argparse
import json
from html import escape
from pathlib import Path

from utils import (
    ambiguous_entity_merge_candidates,
    append_log,
    file_uri,
    find_repo_root,
    today_str,
    write_output_home,
    write_text,
)


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
    return [
        node for node in graph.get("nodes", [])
        if isinstance(node, dict) and str(node.get("type", "") or "") == "entity"
    ] if isinstance(graph.get("nodes"), list) else []


def build_review(graph: dict[str, object]) -> dict[str, object]:
    entity_nodes = _knowledge_entity_nodes(graph)
    candidates, ambiguous_entity_count = ambiguous_entity_merge_candidates(entity_nodes)
    summary = (
        f"Detected {len(candidates)} ambiguous entity merge groups involving {ambiguous_entity_count} entity pages."
        if candidates
        else "No new ambiguous entity merge groups were detected."
    )
    actions = (
        [
            "Start with the identity key that matches the most entity pages.",
            "Confirm which entity page should be canonical; convert the others into aliases or merge them into the same entity.",
            "Review sources, topics, and aliases before applying a merge to avoid overwriting existing governance data.",
        ]
        if candidates
        else ["No manual entity merge review is needed right now. You can keep expanding entity knowledge objects."]
    )
    return {
        "generated_at": today_str(),
        "schemaVersion": str(graph.get("schema_version") or "1"),
        "summary": summary,
        "stats": {
            "entityCount": len(entity_nodes),
            "ambiguousAliasGroupCount": len(candidates),
            "ambiguousEntityCount": ambiguous_entity_count,
        },
        "topActions": actions,
        "candidates": candidates,
    }


def render_review_markdown(review: dict[str, object]) -> str:
    stats = review["stats"]
    assert isinstance(stats, dict)
    lines = [
        "# ThinkWiki Entity Merge Review",
        "",
        f"- Generated: {review['generated_at']}",
        f"- Summary: {review['summary']}",
        f"- Entities: {stats['entityCount']}",
        f"- Ambiguous Alias Groups: {stats['ambiguousAliasGroupCount']}",
        f"- Ambiguous Entities: {stats['ambiguousEntityCount']}",
        "",
        "## Top Actions",
        "",
    ]
    lines.extend(f"- {item}" for item in review.get("topActions", []))
    lines.extend(["", "## Candidates", ""])
    candidates = review.get("candidates", [])
    if isinstance(candidates, list) and candidates:
        for item in candidates:
            titles = ", ".join(str(title) for title in item.get("titles", []))
            labels = ", ".join(str(label) for label in item.get("labels", []))
            entity_ids = ", ".join(str(entity_id) for entity_id in item.get("entityIds", []))
            lines.extend([
                f"- Identity Key: {item.get('identityKey', 'n/a')}",
                f"  Titles: {titles}",
                f"  Labels: {labels}",
                f"  Entity IDs: {entity_ids}",
                f"  Reason: {item.get('reason', '')}",
                "",
            ])
    else:
        lines.append("- No candidates")
    return "\n".join(lines).rstrip()


def _render_candidate_cards(candidates: list[dict[str, object]]) -> str:
    if not candidates:
        return "<div class='empty'>No ambiguous entity merge candidates.</div>"
    cards: list[str] = []
    for item in candidates:
        titles = ", ".join(str(title) for title in item.get("titles", [])[:4]) or "n/a"
        labels = ", ".join(str(label) for label in item.get("labels", [])[:6]) or "n/a"
        entity_ids = "<br>".join(escape(str(entity_id)) for entity_id in item.get("entityIds", [])) or "n/a"
        cards.append(
            "<div class='record-card'>"
            "<strong>{identity_key}</strong>"
            "<div class='record-meta'>entities={entity_count}</div>"
            "<p>{reason}</p>"
            "<div class='detail-row'><span class='detail-label'>Titles</span>{titles}</div>"
            "<div class='detail-row'><span class='detail-label'>Labels</span>{labels}</div>"
            "<div class='detail-row'><span class='detail-label'>Entity IDs</span>{entity_ids}</div>"
            "</div>".format(
                identity_key=escape(str(item.get("identityKey") or "n/a")),
                entity_count=escape(str(len(item.get("entityIds", [])))),
                reason=escape(str(item.get("reason") or "")),
                titles=escape(titles),
                labels=escape(labels),
                entity_ids=entity_ids,
            )
        )
    return "\n".join(cards)


def render_review_html(review: dict[str, object]) -> str:
    stats = review["stats"]
    assert isinstance(stats, dict)
    candidates = review.get("candidates", [])
    cards = _render_candidate_cards(candidates if isinstance(candidates, list) else [])
    actions = review.get("topActions", [])
    action_html = (
        "<ul class='bullet-list'>{}</ul>".format(
            "".join(f"<li>{escape(str(item))}</li>" for item in actions)
        )
        if isinstance(actions, list) and actions
        else "<div class='empty'>No actions.</div>"
    )
    return """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>ThinkWiki Entity Merge Review</title>
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
      border: 1px solid var(--border);
      border-radius: 24px;
      background: rgba(9, 13, 28, 0.86);
      padding: 28px;
    }}
    .lead {{
      color: var(--muted);
      line-height: 1.6;
    }}
    .meta {{
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
      margin: 16px 0 24px;
    }}
    .badge {{
      border: 1px solid var(--border);
      border-radius: 999px;
      padding: 6px 12px;
      color: var(--muted);
      background: rgba(255,255,255,0.03);
      font-size: 0.92rem;
    }}
    .stats {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
      gap: 12px;
      margin-bottom: 24px;
    }}
    .stat {{
      border: 1px solid var(--border);
      background: var(--panel);
      border-radius: 18px;
      padding: 16px;
    }}
    .stat strong {{
      display: block;
      font-size: 1.4rem;
      margin-bottom: 6px;
    }}
    .layout {{
      display: grid;
      gap: 14px;
      grid-template-columns: 320px 1fr;
    }}
    .panel {{
      border: 1px solid var(--border);
      background: rgba(255,255,255,0.02);
      border-radius: 18px;
      padding: 18px;
    }}
    .bullet-list {{
      margin: 0;
      padding-left: 18px;
      color: var(--muted);
      display: grid;
      gap: 10px;
      line-height: 1.5;
    }}
    .records {{
      display: grid;
      gap: 10px;
    }}
    .record-card {{
      border: 1px solid var(--border);
      background: var(--panel);
      border-radius: 16px;
      padding: 14px;
    }}
    .record-card strong {{
      display: block;
      margin-bottom: 6px;
    }}
    .record-meta {{
      color: var(--accent);
      font-size: 0.88rem;
      margin-bottom: 8px;
    }}
    .record-card p {{
      color: var(--muted);
      line-height: 1.55;
    }}
    .detail-row {{
      margin-top: 10px;
      color: var(--muted);
      line-height: 1.5;
    }}
    .detail-label {{
      display: block;
      color: var(--text);
      margin-bottom: 4px;
    }}
    .empty {{
      border: 1px dashed var(--border);
      border-radius: 16px;
      padding: 14px;
      color: var(--muted);
    }}
    a {{ color: var(--accent); }}
    @media (max-width: 900px) {{
      .layout {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <main class="shell">
    <h1>ThinkWiki Entity Merge Review</h1>
    <p class="lead">{summary}</p>
    <div class="meta">
      <span class="badge">Generated {generated_at}</span>
      <span class="badge"><a href="report.html">Open Graph Report</a></span>
      <span class="badge"><a href="index.html">Open Graph</a></span>
      <span class="badge"><a href="../index.html">Open Workspace Home</a></span>
    </div>
    <section class="stats">
      <div class="stat"><strong>{entity_count}</strong><span>Entities</span></div>
      <div class="stat"><strong>{group_count}</strong><span>Ambiguous Alias Groups</span></div>
      <div class="stat"><strong>{ambiguous_entity_count}</strong><span>Ambiguous Entities</span></div>
    </section>
    <div class="layout">
      <section class="panel">
        <h2>Top Actions</h2>
        {actions}
      </section>
      <section class="panel">
        <h2>Candidates</h2>
        <div class="records">{cards}</div>
      </section>
    </div>
  </main>
</body>
</html>
""".format(
        summary=escape(str(review.get("summary") or "")),
        generated_at=escape(str(review.get("generated_at") or "")),
        entity_count=escape(str(stats.get("entityCount", 0) or 0)),
        group_count=escape(str(stats.get("ambiguousAliasGroupCount", 0) or 0)),
        ambiguous_entity_count=escape(str(stats.get("ambiguousEntityCount", 0) or 0)),
        actions=action_html,
        cards=cards,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a deterministic entity merge review from the current ThinkWiki graph data.")
    parser.add_argument("--root", default=".", help="Wiki root path")
    args = parser.parse_args()

    root = find_repo_root(Path(args.root))
    graph = _load_graph(root)
    review = build_review(graph)

    review_dir = root / "output" / "graph"
    review_json_path = review_dir / "entity-merge-review.json"
    review_md_path = review_dir / "entity-merge-review.md"
    review_html_path = review_dir / "entity-merge-review.html"
    write_text(review_json_path, json.dumps(review, ensure_ascii=False, indent=2))
    write_text(review_md_path, render_review_markdown(review))
    write_text(review_html_path, render_review_html(review))
    output_home = write_output_home(root)

    append_log(root, f"[{today_str()}] entity-merge-review | {review['stats']['ambiguousAliasGroupCount']} groups", [
        "- review html: output/graph/entity-merge-review.html",
        "- review: output/graph/entity-merge-review.md",
        "- data: output/graph/entity-merge-review.json",
        "- hub: output/index.html",
    ])
    print("# ThinkWiki Entity Merge Review")
    print("")
    print(f"- Root: {root}")
    print(f"- Summary: {review['summary']}")
    print(f"- Ambiguous Alias Groups: {review['stats']['ambiguousAliasGroupCount']}")
    print(f"- Ambiguous Entities: {review['stats']['ambiguousEntityCount']}")
    print("")
    print("Top Actions:")
    for item in review.get("topActions", []):
        print(f"- {item}")
    print("")
    print("Entity merge review: output/graph/entity-merge-review.html")
    print(f"Entity merge review URI: {file_uri(review_html_path)}")
    print("Entity merge review markdown: output/graph/entity-merge-review.md")
    print("Entity merge review data: output/graph/entity-merge-review.json")
    print("Output hub: output/index.html")
    print(f"Output hub URI: {file_uri(output_home)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
