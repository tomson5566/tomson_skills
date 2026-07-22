#!/usr/bin/env python3
from __future__ import annotations

"""
ThinkWiki Script: graph_report

Purpose:
- Generate a governance report from the current graph outputs.

Usage:
- Prefer `python scripts/thinkwiki graph-report ...`.
- Run `python scripts/<script> --help` for direct CLI details when the file exposes its own arguments.
"""


import argparse
import json
from html import escape
from pathlib import Path

from build_graph import node_metrics
from utils import ambiguous_entity_merge_candidates, append_log, file_uri, find_repo_root, print_output_serve_hint, today_str, write_output_home, write_text


def _load_graph(root: Path) -> dict[str, object]:
    graph_path = root / "output" / "graph" / "graph.json"
    if not graph_path.exists():
        raise SystemExit("Graph data not found. Run `python scripts/thinkwiki graph --root <wiki-root>` first.")
    try:
        return json.loads(graph_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise SystemExit(f"Invalid graph data: {graph_path} ({exc})") from exc


def _graph_view(graph: dict[str, object], view_name: str = "knowledge") -> dict[str, object]:
    views = graph.get("views", {})
    if isinstance(views, dict):
        view = views.get(view_name, {})
        if isinstance(view, dict):
            nodes = view.get("nodes", [])
            edges = view.get("edges", [])
            insights = view.get("insights", {})
            if isinstance(nodes, list) and isinstance(edges, list) and isinstance(insights, dict):
                return {"nodes": nodes, "edges": edges, "insights": insights, "name": view_name}
    return {
        "nodes": graph.get("nodes", []) if isinstance(graph.get("nodes"), list) else [],
        "edges": graph.get("edges", []) if isinstance(graph.get("edges"), list) else [],
        "insights": graph.get("insights", {}) if isinstance(graph.get("insights"), dict) else {},
        "name": "legacy",
    }


def _page_nodes(nodes: list[dict[str, object]]) -> list[dict[str, object]]:
    return [node for node in nodes if str(node.get("type") or "page") not in {"raw", "file", "claim"}]


def _entity_nodes(nodes: list[dict[str, object]]) -> list[dict[str, object]]:
    return [node for node in nodes if str(node.get("type") or "page") == "entity"]


def _entity_alias_stats(entity_nodes: list[dict[str, object]]) -> tuple[int, int]:
    alias_count = 0
    aliased_entity_count = 0
    for node in entity_nodes:
        aliases = node.get("aliases", [])
        if not isinstance(aliases, list):
            continue
        clean_aliases = [str(item).strip() for item in aliases if str(item).strip()]
        alias_count += len(clean_aliases)
        if clean_aliases:
            aliased_entity_count += 1
    return alias_count, aliased_entity_count


def _summary_length(node: dict[str, object]) -> int:
    return len(str(node.get("summary", "") or "").strip())


def _connected_components(node_ids: set[str], edges: list[dict[str, str]]) -> list[list[str]]:
    adjacency: dict[str, set[str]] = {node_id: set() for node_id in node_ids}
    for edge in edges:
        source = str(edge.get("source") or "")
        target = str(edge.get("target") or "")
        if source not in adjacency or target not in adjacency:
            continue
        adjacency[source].add(target)
        adjacency[target].add(source)

    components: list[list[str]] = []
    seen: set[str] = set()
    for node_id in sorted(node_ids):
        if node_id in seen:
            continue
        stack = [node_id]
        component: list[str] = []
        while stack:
            current = stack.pop()
            if current in seen:
                continue
            seen.add(current)
            component.append(current)
            stack.extend(sorted(adjacency[current] - seen))
        components.append(sorted(component))
    return sorted(components, key=lambda item: (-len(item), item[0] if item else ""))


def _hub_stub_candidates(
    page_nodes: list[dict[str, object]],
    metrics: dict[str, dict[str, object]],
) -> list[dict[str, object]]:
    if not page_nodes:
        return []
    degrees = [int(metrics[str(node["id"])]["degree"]) for node in page_nodes]
    average_degree = sum(degrees) / len(degrees)
    threshold = max(3, int(round(average_degree + 1)))
    items: list[dict[str, object]] = []
    for node in page_nodes:
        node_id = str(node["id"])
        if str(node.get("type") or "page") == "entity":
            continue
        degree = int(metrics[node_id]["degree"])
        summary_length = _summary_length(node)
        if degree < threshold or summary_length >= 80:
            continue
        items.append({
            "id": node_id,
            "title": str(node.get("label") or node_id),
            "type": str(node.get("type") or "page"),
            "degree": degree,
            "summaryLength": summary_length,
            "reason": f"Degree is {degree}, but the summary is only {summary_length} characters long.",
        })
    return sorted(items, key=lambda item: (-int(item["degree"]), int(item["summaryLength"]), str(item["title"]).lower()))[:6]


def _fragile_bridge_candidates(
    page_nodes: list[dict[str, object]],
    metrics: dict[str, dict[str, object]],
) -> list[dict[str, object]]:
    items: list[dict[str, object]] = []
    for node in page_nodes:
        node_id = str(node["id"])
        info = metrics[node_id]
        degree = int(info["degree"])
        neighbor_types = {str(item) for item in info["neighbor_types"]}
        if degree > 0 and degree <= 2 and len(neighbor_types) >= 2:
            items.append({
                "id": node_id,
                "title": str(node.get("label") or node_id),
                "type": str(node.get("type") or "page"),
                "degree": degree,
                "neighborTypes": sorted(neighbor_types),
                "reason": f"Only {degree} relations connect {len(neighbor_types)} page types, so this bridge is fragile.",
            })
    return sorted(items, key=lambda item: (int(item["degree"]), -len(item["neighborTypes"]), str(item["title"]).lower()))[:6]


def _page_health_candidates(
    page_nodes: list[dict[str, object]],
    metrics: dict[str, dict[str, object]],
) -> list[dict[str, object]]:
    items: list[dict[str, object]] = []
    for node in page_nodes:
        node_id = str(node["id"])
        degree = int(metrics[node_id]["degree"])
        if degree == 0:
            items.append({
                "id": node_id,
                "title": str(node.get("label") or node_id),
                "type": str(node.get("type") or "page"),
                "severity": "isolated",
                "degree": degree,
                "reason": "No page-level relationships yet.",
            })
        elif degree == 1:
            items.append({
                "id": node_id,
                "title": str(node.get("label") or node_id),
                "type": str(node.get("type") or "page"),
                "severity": "weak",
                "degree": degree,
                "reason": "Only one page-level relationship so far. Add more links.",
            })
    return sorted(
        items,
        key=lambda item: (
            0 if str(item["severity"]) == "isolated" else 1,
            str(item["title"]).lower(),
        ),
    )[:8]


def _isolated_cluster_candidates(
    page_nodes: list[dict[str, object]],
    edges: list[dict[str, str]],
    node_by_id: dict[str, dict[str, object]],
) -> list[dict[str, object]]:
    page_node_ids = {str(node["id"]) for node in page_nodes}
    components = _connected_components(page_node_ids, edges)
    if len(components) <= 1:
        return []
    items: list[dict[str, object]] = []
    for component in components[1:]:
        if len(component) < 2:
            continue
        labels = [str(node_by_id[node_id].get("label") or node_id) for node_id in component if node_id in node_by_id]
        items.append({
            "size": len(component),
            "nodeIds": component,
            "titles": labels[:4],
            "reason": f"This cluster is disconnected from the main graph and contains {len(component)} pages.",
        })
    return sorted(items, key=lambda item: (-int(item["size"]), ",".join(item["titles"]).lower()))[:4]


def _top_actions(report: dict[str, object]) -> list[str]:
    stats = report["stats"]
    assert isinstance(stats, dict)
    actions: list[str] = []
    if int(stats.get("isolatedPageCount", 0) or 0):
        actions.append("Fix isolated pages first by adding `links_to` edges or source references.")
    if int(stats.get("hubStubCount", 0) or 0):
        actions.append("Strengthen high-degree thin pages with better summaries, context, and sources.")
    if int(stats.get("fragileBridgeCount", 0) or 0):
        actions.append("Reinforce fragile bridge pages so cross-topic links do not rely on single points.")
    if int(stats.get("isolatedClusterCount", 0) or 0):
        actions.append("Reconnect isolated clusters back to the main graph.")
    if int(stats.get("suggestedLinkCount", 0) or 0):
        actions.append("Review suggested links and convert strong candidates into explicit page links.")
    if int(stats.get("ambiguousAliasGroupCount", 0) or 0):
        actions.append("Review ambiguous alias groups so multiple entity pages do not collapse into the same identity key unexpectedly.")
    return actions[:4] or ["The graph structure looks stable. Continue expanding high-value pages."]


def _console_summary(report: dict[str, object]) -> str:
    stats = report["stats"]
    assert isinstance(stats, dict)
    return (
        "pages={pages}, relations={relations}, entities={entities}, aliasedEntities={aliased_entities}, aliases={aliases}, ambiguousAliasGroups={ambiguous_groups}, ambiguousEntities={ambiguous_entities}, "
        "isolatedPages={isolated}, weakPages={weak}, hubStubs={hub_stubs}, fragileBridges={fragile}, isolatedClusters={clusters}, suggestedLinks={suggested}"
    ).format(
        pages=int(stats.get("nodeCount", 0) or 0),
        relations=int(stats.get("edgeCount", 0) or 0),
        entities=int(stats.get("entityCount", 0) or 0),
        aliased_entities=int(stats.get("aliasedEntityCount", 0) or 0),
        aliases=int(stats.get("aliasCount", 0) or 0),
        ambiguous_groups=int(stats.get("ambiguousAliasGroupCount", 0) or 0),
        ambiguous_entities=int(stats.get("ambiguousEntityCount", 0) or 0),
        isolated=int(stats.get("isolatedPageCount", 0) or 0),
        weak=int(stats.get("weakPageCount", 0) or 0),
        hub_stubs=int(stats.get("hubStubCount", 0) or 0),
        fragile=int(stats.get("fragileBridgeCount", 0) or 0),
        clusters=int(stats.get("isolatedClusterCount", 0) or 0),
        suggested=int(stats.get("suggestedLinkCount", 0) or 0),
    )


def _console_actions(report: dict[str, object]) -> list[str]:
    stats = report["stats"]
    assert isinstance(stats, dict)
    actions: list[str] = []
    if int(stats.get("isolatedPageCount", 0) or 0):
        actions.append("Fix isolated pages first by adding links or source references.")
    if int(stats.get("hubStubCount", 0) or 0):
        actions.append("Strengthen high-degree thin pages with better summaries and context.")
    if int(stats.get("fragileBridgeCount", 0) or 0):
        actions.append("Reinforce fragile bridge pages so cross-topic links do not rely on single points.")
    if int(stats.get("isolatedClusterCount", 0) or 0):
        actions.append("Reconnect isolated clusters back to the main graph.")
    if int(stats.get("suggestedLinkCount", 0) or 0):
        actions.append("Review suggested links and convert strong candidates into explicit page links.")
    if int(stats.get("ambiguousAliasGroupCount", 0) or 0):
        actions.append("Review ambiguous entity merge candidates before changing canonical entity pages.")
    return actions[:4] or ["Graph structure looks stable. Continue expanding high-value pages."]


def build_report(graph: dict[str, object]) -> dict[str, object]:
    active_view = _graph_view(graph, "knowledge")
    nodes = active_view.get("nodes", [])
    edges = active_view.get("edges", [])
    insights = active_view.get("insights", {})
    if not isinstance(nodes, list) or not isinstance(edges, list):
        raise SystemExit("Invalid graph payload: nodes/edges are missing.")
    if not isinstance(insights, dict):
        insights = {}

    page_nodes = _page_nodes(nodes)
    entity_nodes = _entity_nodes(nodes)
    page_node_ids = {str(node["id"]) for node in page_nodes}
    filtered_edges = [
        edge for edge in edges
        if str(edge.get("source") or "") in page_node_ids and str(edge.get("target") or "") in page_node_ids
    ]
    metrics = node_metrics(page_nodes, filtered_edges)
    node_by_id = {str(node["id"]): node for node in page_nodes}

    isolated_pages = _page_health_candidates(page_nodes, metrics)
    hub_stubs = _hub_stub_candidates(page_nodes, metrics)
    fragile_bridges = _fragile_bridge_candidates(page_nodes, metrics)
    isolated_clusters = _isolated_cluster_candidates(page_nodes, filtered_edges, node_by_id)
    suggested_links = [
        item for item in insights.get("suggestedLinks", [])
        if isinstance(item, dict)
    ]
    isolated_entities = sorted(
        [
            {
                "id": str(node["id"]),
                "title": str(node.get("label") or node["id"]),
                "type": "entity",
                "reason": "This entity node does not connect to any other knowledge nodes yet.",
            }
            for node in entity_nodes
            if not any(
                str(edge.get("source") or "") == str(node["id"]) or str(edge.get("target") or "") == str(node["id"])
                for edge in edges
            )
        ],
        key=lambda item: str(item["title"]).lower(),
    )[:8]
    alias_count, aliased_entity_count = _entity_alias_stats(entity_nodes)
    ambiguous_merge_candidates, ambiguous_entity_count = ambiguous_entity_merge_candidates(entity_nodes)

    stats = {
        "view": str(active_view.get("name") or "knowledge"),
        "nodeCount": len(page_nodes),
        "edgeCount": len(filtered_edges),
        "entityCount": len(entity_nodes),
        "aliasCount": alias_count,
        "aliasedEntityCount": aliased_entity_count,
        "ambiguousAliasGroupCount": len(ambiguous_merge_candidates),
        "ambiguousEntityCount": ambiguous_entity_count,
        "isolatedEntityCount": len(isolated_entities),
        "isolatedPageCount": sum(1 for item in isolated_pages if str(item.get("severity", "")) == "isolated"),
        "weakPageCount": sum(1 for item in isolated_pages if str(item.get("severity", "")) == "weak"),
        "bridgePageCount": len([item for item in insights.get("bridgeNodes", []) if isinstance(item, dict)]),
        "suggestedLinkCount": len(suggested_links),
        "hubStubCount": len(hub_stubs),
        "fragileBridgeCount": len(fragile_bridges),
        "isolatedClusterCount": len(isolated_clusters),
        "componentCount": len(_connected_components(page_node_ids, filtered_edges)) if page_node_ids else 0,
        "averageDegree": round((len(filtered_edges) * 2 / len(page_nodes)) if page_nodes else 0, 2),
    }

    top_node = next((item for item in insights.get("topNodes", []) if isinstance(item, dict)), None)
    summary_parts = []
    if top_node:
        summary_parts.append(f"The current key page is {top_node.get('title', 'n/a')}.")
    if stats["isolatedPageCount"]:
        summary_parts.append(f"There are {stats['isolatedPageCount']} isolated pages that need links.")
    elif stats["weakPageCount"]:
        summary_parts.append(f"There are {stats['weakPageCount']} weakly connected pages that need more context.")
    else:
        summary_parts.append("The main pages already have a basic connection structure.")
    if stats["hubStubCount"]:
        summary_parts.append(f"There are {stats['hubStubCount']} high-degree thin pages worth strengthening first.")
    if stats["isolatedClusterCount"]:
        summary_parts.append(f"There are {stats['isolatedClusterCount']} clusters disconnected from the main graph.")
    if stats["suggestedLinkCount"]:
        summary_parts.append(f"There are {stats['suggestedLinkCount']} suggested links ready for review.")
    if stats["entityCount"]:
        summary_parts.append(f"The graph currently identifies {stats['entityCount']} entity nodes.")
    if stats["aliasCount"]:
        summary_parts.append(f"Among them, {stats['aliasedEntityCount']} entities carry aliases for a total of {stats['aliasCount']} alias entries.")
    if stats["ambiguousAliasGroupCount"]:
        summary_parts.append(
            f"There are also {stats['ambiguousAliasGroupCount']} ambiguous alias groups spanning {stats['ambiguousEntityCount']} entity pages. Review them manually."
        )

    report = {
        "generated_at": today_str(),
        "schemaVersion": str(graph.get("schema_version") or "1"),
        "view": str(active_view.get("name") or "knowledge"),
        "summary": " ".join(summary_parts),
        "stats": stats,
        "topActions": _top_actions({"stats": stats}),
        "topNodes": insights.get("topNodes", []),
        "bridgeNodes": insights.get("bridgeNodes", []),
        "isolatedPages": isolated_pages,
        "isolatedEntities": isolated_entities,
        "ambiguousEntityMergeCandidates": ambiguous_merge_candidates,
        "hubStubs": hub_stubs,
        "fragileBridges": fragile_bridges,
        "isolatedClusters": isolated_clusters,
        "suggestedLinks": suggested_links,
    }
    return report


def render_report_markdown(report: dict[str, object]) -> str:
    stats = report["stats"]
    assert isinstance(stats, dict)
    lines = [
        "# ThinkWiki Graph Report",
        "",
        f"- Generated: {report['generated_at']}",
        f"- Summary: {report['summary']}",
        "",
        "## Health Summary",
        "",
        f"- Pages: {stats['nodeCount']}",
        f"- Relations: {stats['edgeCount']}",
        f"- Entities: {stats['entityCount']}",
        f"- Aliased Entities: {stats['aliasedEntityCount']}",
        f"- Aliases: {stats['aliasCount']}",
        f"- Ambiguous Alias Groups: {stats['ambiguousAliasGroupCount']}",
        f"- Ambiguous Entities: {stats['ambiguousEntityCount']}",
        f"- Isolated Entities: {stats['isolatedEntityCount']}",
        f"- Average Degree: {stats['averageDegree']}",
        f"- Isolated Pages: {stats['isolatedPageCount']}",
        f"- Weak Pages: {stats['weakPageCount']}",
        f"- Bridge Pages: {stats['bridgePageCount']}",
        f"- Suggested Links: {stats['suggestedLinkCount']}",
        f"- Hub Stubs: {stats['hubStubCount']}",
        f"- Fragile Bridges: {stats['fragileBridgeCount']}",
        f"- Isolated Clusters: {stats['isolatedClusterCount']}",
        "",
        "## Top Actions",
        "",
    ]
    lines.extend(f"- {item}" for item in report["topActions"])
    lines.extend(["", "## Entities That Need Links", ""])
    if report["isolatedEntities"]:
        lines.extend(
            f"- {item['title']} | {item['reason']}"
            for item in report["isolatedEntities"]
        )
    else:
        lines.append("- No isolated entities")
    lines.extend(["", "## Ambiguous Entity Merge Candidates", ""])
    if report["ambiguousEntityMergeCandidates"]:
        lines.extend(
            f"- key={item['identityKey']} | {', '.join(item['titles'])} | {item['reason']}"
            for item in report["ambiguousEntityMergeCandidates"]
        )
    else:
        lines.append("- No ambiguous merge candidates")
    lines.extend(["", "## Hub Stubs", ""])
    if report["hubStubs"]:
        lines.extend(
            f"- {item['title']} ({item['type']}) | degree={item['degree']} | {item['reason']}"
            for item in report["hubStubs"]
        )
    else:
        lines.append("- No hub stubs")
    lines.extend(["", "## Fragile Bridges", ""])
    if report["fragileBridges"]:
        lines.extend(
            f"- {item['title']} ({item['type']}) | degree={item['degree']} | {item['reason']}"
            for item in report["fragileBridges"]
        )
    else:
        lines.append("- No fragile bridges")
    lines.extend(["", "## Isolated Clusters", ""])
    if report["isolatedClusters"]:
        lines.extend(
            f"- size={item['size']} | {', '.join(item['titles'])} | {item['reason']}"
            for item in report["isolatedClusters"]
        )
    else:
        lines.append("- No isolated clusters")
    lines.extend(["", "## Suggested Links", ""])
    if report["suggestedLinks"]:
        lines.extend(
            f"- {item['source']} <-> {item['target']} | score={item['score']}"
            for item in report["suggestedLinks"]
        )
    else:
        lines.append("- No suggested links")
    return "\n".join(lines)


def _render_html_list(items: list[str]) -> str:
    if not items:
        return "<div class='empty'>Nothing here yet.</div>"
    return "<ul class='bullet-list'>{}</ul>".format(
        "".join(f"<li>{escape(item)}</li>" for item in items)
    )


def _render_html_metric_cards(stats: dict[str, object]) -> str:
    cards = []
    for label, key in [
        ("Pages", "nodeCount"),
        ("Relations", "edgeCount"),
        ("Entities", "entityCount"),
        ("Aliased Entities", "aliasedEntityCount"),
        ("Aliases", "aliasCount"),
        ("Ambiguous Alias Groups", "ambiguousAliasGroupCount"),
        ("Ambiguous Entities", "ambiguousEntityCount"),
        ("Isolated Entities", "isolatedEntityCount"),
        ("Average Degree", "averageDegree"),
        ("Isolated Pages", "isolatedPageCount"),
        ("Weak Pages", "weakPageCount"),
        ("Bridge Pages", "bridgePageCount"),
        ("Suggested Links", "suggestedLinkCount"),
        ("Hub Stubs", "hubStubCount"),
        ("Fragile Bridges", "fragileBridgeCount"),
        ("Isolated Clusters", "isolatedClusterCount"),
    ]:
        cards.append(
            "<div class='stat'><strong>{}</strong><span>{}</span></div>".format(
                escape(str(stats.get(key, 0) or 0)),
                escape(label),
            )
        )
    return "\n".join(cards)


def _render_html_record_cards(items: list[dict[str, object]], empty_text: str, formatter) -> str:
    if not items:
        return "<div class='empty'>{}</div>".format(escape(empty_text))
    rows = []
    for item in items:
        title, meta, reason = formatter(item)
        rows.append(
            "<div class='record-card'>"
            "<strong>{}</strong>"
            "<div class='record-meta'>{}</div>"
            "<p>{}</p>"
            "</div>".format(
                escape(title),
                escape(meta),
                escape(reason),
            )
        )
    return "\n".join(rows)


def render_report_html(report: dict[str, object]) -> str:
    stats = report["stats"]
    assert isinstance(stats, dict)
    top_actions = report.get("topActions", [])
    hub_stubs = report.get("hubStubs", [])
    fragile_bridges = report.get("fragileBridges", [])
    isolated_clusters = report.get("isolatedClusters", [])
    suggested_links = report.get("suggestedLinks", [])
    isolated_pages = report.get("isolatedPages", [])
    isolated_entities = report.get("isolatedEntities", [])
    ambiguous_merge_candidates = report.get("ambiguousEntityMergeCandidates", [])
    top_nodes = report.get("topNodes", [])
    bridge_nodes = report.get("bridgeNodes", [])

    isolated_cards = _render_html_record_cards(
        isolated_pages if isinstance(isolated_pages, list) else [],
        "No isolated or weak pages.",
        lambda item: (
            str(item.get("title") or item.get("id") or "Untitled"),
            "{} | degree={}".format(str(item.get("severity") or "page"), int(item.get("degree", 0) or 0)),
            str(item.get("reason") or ""),
        ),
    )
    hub_cards = _render_html_record_cards(
        hub_stubs if isinstance(hub_stubs, list) else [],
        "No hub stubs.",
        lambda item: (
            str(item.get("title") or item.get("id") or "Untitled"),
            "{} | degree={}".format(str(item.get("type") or "page"), int(item.get("degree", 0) or 0)),
            str(item.get("reason") or ""),
        ),
    )
    bridge_cards = _render_html_record_cards(
        fragile_bridges if isinstance(fragile_bridges, list) else [],
        "No fragile bridges.",
        lambda item: (
            str(item.get("title") or item.get("id") or "Untitled"),
            "{} | degree={}".format(str(item.get("type") or "page"), int(item.get("degree", 0) or 0)),
            str(item.get("reason") or ""),
        ),
    )
    cluster_cards = _render_html_record_cards(
        isolated_clusters if isinstance(isolated_clusters, list) else [],
        "No isolated clusters.",
        lambda item: (
            ", ".join(str(title) for title in item.get("titles", [])[:3]) or "Untitled cluster",
            "cluster | size={}".format(int(item.get("size", 0) or 0)),
            str(item.get("reason") or ""),
        ),
    )
    suggestion_cards = _render_html_record_cards(
        suggested_links if isinstance(suggested_links, list) else [],
        "No suggested links.",
        lambda item: (
            "{} <-> {}".format(str(item.get("source") or "n/a"), str(item.get("target") or "n/a")),
            "suggested link | score={}".format(item.get("score", "n/a")),
            str(item.get("reason") or "High-confidence structural suggestion."),
        ),
    )
    isolated_entity_cards = _render_html_record_cards(
        isolated_entities if isinstance(isolated_entities, list) else [],
        "No isolated entities.",
        lambda item: (
            str(item.get("title") or item.get("id") or "Untitled"),
            str(item.get("type") or "entity"),
            str(item.get("reason") or ""),
        ),
    )
    ambiguous_merge_cards = _render_html_record_cards(
        ambiguous_merge_candidates if isinstance(ambiguous_merge_candidates, list) else [],
        "No ambiguous merge candidates.",
        lambda item: (
            ", ".join(str(title) for title in item.get("titles", [])[:3]) or "Untitled",
            "identity key={}".format(str(item.get("identityKey") or "n/a")),
            str(item.get("reason") or ""),
        ),
    )
    top_node_cards = _render_html_record_cards(
        top_nodes if isinstance(top_nodes, list) else [],
        "No key pages yet.",
        lambda item: (
            str(item.get("title") or item.get("id") or "Untitled"),
            "{} | score={}".format(str(item.get("type") or "page"), int(item.get("score", 0) or 0)),
            str(item.get("reason") or ""),
        ),
    )
    bridge_node_cards = _render_html_record_cards(
        bridge_nodes if isinstance(bridge_nodes, list) else [],
        "No bridge pages yet.",
        lambda item: (
            str(item.get("title") or item.get("id") or "Untitled"),
            "{} | score={}".format(str(item.get("type") or "page"), int(item.get("score", 0) or 0)),
            str(item.get("reason") or ""),
        ),
    )

    return """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>ThinkWiki Graph Report</title>
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
      width: min(1180px, 100%);
      margin: 0 auto;
      background: rgba(9, 13, 28, 0.86);
      border: 1px solid var(--border);
      border-radius: 24px;
      padding: 28px;
    }}
    h1, h2, p {{ margin-top: 0; }}
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
      grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
      gap: 12px;
      margin: 24px 0;
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
    .stat span {{
      color: var(--muted);
    }}
    .layout {{
      display: grid;
      gap: 14px;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      margin-top: 18px;
    }}
    .panel {{
      border: 1px solid var(--border);
      background: rgba(255,255,255,0.02);
      border-radius: 18px;
      padding: 18px;
    }}
    .panel p {{
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
      margin-bottom: 0;
    }}
    .empty {{
      border: 1px dashed var(--border);
      border-radius: 16px;
      padding: 14px;
      color: var(--muted);
    }}
    a {{
      color: var(--accent);
    }}
    @media (max-width: 860px) {{
      .layout {{
        grid-template-columns: 1fr;
      }}
    }}
  </style>
</head>
<body>
  <main class="shell">
    <h1>ThinkWiki Graph Report</h1>
    <p class="lead">{summary}</p>
    <div class="meta">
      <span class="badge">Generated {generated_at}</span>
      <span class="badge">Pages {page_count}</span>
      <span class="badge">Relations {edge_count}</span>
      <span class="badge">Entities {entity_count}</span>
      <span class="badge">Aliases {alias_count}</span>
      <span class="badge"><a href="index.html">Open Graph</a></span>
      <span class="badge"><a href="../index.html">Open Workspace Home</a></span>
    </div>

    <section>
      <h2>Health Summary</h2>
      <div class="stats">
        {metric_cards}
      </div>
    </section>

    <div class="layout">
      <section class="panel">
        <h2>Top Actions</h2>
        <p>Start with the graph issues that most affect navigation and maintainability.</p>
        {top_actions}
      </section>
      <section class="panel">
        <h2>Key Pages</h2>
        <p>Read or strengthen these pages first because they matter most to the current graph structure.</p>
        <div class="records">{top_nodes}</div>
      </section>
      <section class="panel">
        <h2>Bridge Pages</h2>
        <p>These pages connect different node types or topical regions.</p>
        <div class="records">{bridge_nodes}</div>
      </section>
      <section class="panel">
        <h2>Pages That Need Links</h2>
        <p>This section shows isolated pages and weakly connected pages that should gain links first.</p>
        <div class="records">{isolated_pages}</div>
      </section>
      <section class="panel">
        <h2>Entities That Need Links</h2>
        <p>These entities have been identified but still lack enough knowledge-graph connections.</p>
        <div class="records">{isolated_entities}</div>
      </section>
      <section class="panel">
        <h2>Ambiguous Entity Merge Candidates</h2>
        <p>These identity keys match multiple entity pages and should be reviewed before any canonical merge.</p>
        <div class="records">{ambiguous_merge_candidates}</div>
      </section>
      <section class="panel">
        <h2>Hub Stubs</h2>
        <p>These pages have many relations but thin content, so improving summaries and context usually pays off first.</p>
        <div class="records">{hub_stubs}</div>
      </section>
      <section class="panel">
        <h2>Fragile Bridges</h2>
        <p>These structures rely on very few pages to keep cross-topic links alive, which makes them fragile.</p>
        <div class="records">{fragile_bridges}</div>
      </section>
      <section class="panel">
        <h2>Isolated Clusters</h2>
        <p>These pages already form small clusters but are not connected back to the main graph yet.</p>
        <div class="records">{isolated_clusters}</div>
      </section>
      <section class="panel">
        <h2>Suggested Links</h2>
        <p>These are high-confidence candidate relations that could become explicit links after review.</p>
        <div class="records">{suggested_links}</div>
      </section>
    </div>
  </main>
</body>
</html>
""".format(
        summary=escape(str(report.get("summary") or "")),
        generated_at=escape(str(report.get("generated_at") or "")),
        page_count=escape(str(stats.get("nodeCount", 0) or 0)),
        edge_count=escape(str(stats.get("edgeCount", 0) or 0)),
        entity_count=escape(str(stats.get("entityCount", 0) or 0)),
        alias_count=escape(str(stats.get("aliasCount", 0) or 0)),
        metric_cards=_render_html_metric_cards(stats),
        top_actions=_render_html_list([str(item) for item in top_actions] if isinstance(top_actions, list) else []),
        top_nodes=top_node_cards,
        bridge_nodes=bridge_node_cards,
        isolated_pages=isolated_cards,
        isolated_entities=isolated_entity_cards,
        ambiguous_merge_candidates=ambiguous_merge_cards,
        hub_stubs=hub_cards,
        fragile_bridges=bridge_cards,
        isolated_clusters=cluster_cards,
        suggested_links=suggestion_cards,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a deterministic graph health report from the current ThinkWiki graph data.")
    parser.add_argument("--root", default=".", help="Wiki root path")
    args = parser.parse_args()

    root = find_repo_root(Path(args.root))
    graph = _load_graph(root)
    report = build_report(graph)

    report_dir = root / "output" / "graph"
    report_json_path = report_dir / "report.json"
    report_md_path = report_dir / "report.md"
    report_html_path = report_dir / "report.html"
    write_text(report_json_path, json.dumps(report, ensure_ascii=False, indent=2))
    write_text(report_md_path, render_report_markdown(report))
    write_text(report_html_path, render_report_html(report))
    output_home = write_output_home(root)

    append_log(root, f"[{today_str()}] graph-report | {report['stats']['nodeCount']} pages", [
        "- report html: output/graph/report.html",
        "- report: output/graph/report.md",
        "- data: output/graph/report.json",
        "- hub: output/index.html",
    ])
    print("# ThinkWiki Graph Report")
    print("")
    print(f"- Root: {root}")
    print(f"- Summary: {_console_summary(report)}")
    print(f"- Isolated Pages: {report['stats']['isolatedPageCount']}")
    print(f"- Hub Stubs: {report['stats']['hubStubCount']}")
    print(f"- Fragile Bridges: {report['stats']['fragileBridgeCount']}")
    print(f"- Suggested Links: {report['stats']['suggestedLinkCount']}")
    print("")
    print("Top Actions:")
    for item in _console_actions(report):
        print(f"- {item}")
    print("")
    print("Graph report: output/graph/report.html")
    print(f"Graph report URI: {file_uri(report_html_path)}")
    print("Graph report markdown: output/graph/report.md")
    print("Graph report data: output/graph/report.json")
    print("Output hub: output/index.html")
    print(f"Output hub URI: {file_uri(output_home)}")
    print_output_serve_hint(root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
