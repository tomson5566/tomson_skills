#!/usr/bin/env python3
from __future__ import annotations

"""
ThinkWiki Script: build_graph

Purpose:
- Build the ThinkWiki graph outputs, including document, knowledge, and suggested graph views.

Usage:
- Prefer `python scripts/thinkwiki graph ...`.
- Run `python scripts/<script> --help` for direct CLI details when the file exposes its own arguments.
"""


import argparse
import json
import re
from pathlib import Path

from utils import (
    append_log,
    collect_wiki_pages,
    entity_label_keys,
    extract_summary,
    file_uri,
    find_repo_root,
    is_external_link,
    markdown_links,
    parse_frontmatter,
    print_output_serve_hint,
    read_text,
    today_str,
    write_text,
    write_output_home,
)

TYPE_ORDER = {
    "raw": 0,
    "file": 0,
    "source": 1,
    "topic": 2,
    "concept": 2,
    "entity": 2,
    "decision": 3,
    "synthesis": 3,
    "query": 3,
    "claim": 4,
    "page": 2,
}

TYPE_LANE_OFFSET = {
    "raw": 0,
    "file": 0,
    "source": 0,
    "topic": -28,
    "concept": 28,
    "entity": 0,
    "decision": -28,
    "synthesis": 28,
    "query": 28,
    "claim": 0,
    "page": 0,
}

TYPE_COLORS = {
    "raw": "#94a3b8",
    "file": "#94a3b8",
    "source": "#60a5fa",
    "topic": "#34d399",
    "concept": "#a78bfa",
    "entity": "#f472b6",
    "decision": "#fb923c",
    "synthesis": "#22d3ee",
    "query": "#cbd5e1",
    "claim": "#facc15",
    "page": "#60a5fa",
}

EDGE_STYLES = {
    "references": {
        "stroke": "rgba(138,180,255,0.38)",
        "highlight": "rgba(138,180,255,0.98)",
        "dash": "",
    },
    "links_to": {
        "stroke": "rgba(255,255,255,0.28)",
        "highlight": "rgba(255,255,255,0.82)",
        "dash": "",
    },
    "includes": {
        "stroke": "rgba(52,211,153,0.42)",
        "highlight": "rgba(52,211,153,0.96)",
        "dash": "6 4",
    },
    "cites": {
        "stroke": "rgba(251,146,60,0.4)",
        "highlight": "rgba(251,146,60,0.96)",
        "dash": "2 6",
    },
    "about": {
        "stroke": "rgba(96,165,250,0.42)",
        "highlight": "rgba(96,165,250,0.96)",
        "dash": "8 6",
    },
    "belongs_to": {
        "stroke": "rgba(52,211,153,0.42)",
        "highlight": "rgba(52,211,153,0.96)",
        "dash": "",
    },
    "related_to": {
        "stroke": "rgba(255,255,255,0.28)",
        "highlight": "rgba(255,255,255,0.9)",
        "dash": "",
    },
    "depends_on": {
        "stroke": "rgba(167,139,250,0.42)",
        "highlight": "rgba(167,139,250,0.96)",
        "dash": "4 4",
    },
    "asserts": {
        "stroke": "rgba(250,204,21,0.42)",
        "highlight": "rgba(250,204,21,0.98)",
        "dash": "",
    },
    "supports": {
        "stroke": "rgba(34,211,238,0.42)",
        "highlight": "rgba(34,211,238,0.96)",
        "dash": "",
    },
    "contradicts": {
        "stroke": "rgba(244,114,182,0.42)",
        "highlight": "rgba(244,114,182,0.96)",
        "dash": "10 5",
    },
    "suggests_related_to": {
        "stroke": "rgba(138,180,255,0.38)",
        "highlight": "rgba(138,180,255,0.96)",
        "dash": "10 6",
    },
}

TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{2,}")
COMMON_TOKENS = {
    "about",
    "after",
    "also",
    "and",
    "are",
    "between",
    "from",
    "have",
    "into",
    "that",
    "their",
    "there",
    "these",
    "this",
    "through",
    "using",
    "with",
    "wiki",
}


def normalize_sources(meta: dict[str, object]) -> list[str]:
    raw = meta.get("sources", [])
    if isinstance(raw, list):
        return [str(item).strip() for item in raw if str(item).strip()]
    if raw:
        return [str(raw).strip()]
    return []


def ordered_unique(items: list[str]) -> list[str]:
    results: list[str] = []
    seen: set[str] = set()
    for item in items:
        value = str(item).strip()
        if not value or value in seen:
            continue
        seen.add(value)
        results.append(value)
    return results


def placeholder_node(node_id: str, label: str, node_type: str) -> dict[str, object]:
    return {
        "id": node_id,
        "label": label,
        "type": node_type,
        "summary": "",
        "confidence": "",
        "status": "",
        "updated": "",
        "path": node_id,
        "sources": [],
    }


def node_payload_for_page(root: Path, page: Path, meta: dict[str, object], body: str, page_type: str) -> dict[str, object]:
    node_id = page.relative_to(root).as_posix()
    return {
        "id": node_id,
        "label": str(meta.get("title") or page.stem),
        "type": page_type,
        "summary": extract_summary(meta, body),
        "confidence": str(meta.get("confidence") or "").strip(),
        "status": str(meta.get("status") or "").strip(),
        "updated": str(meta.get("updated") or meta.get("created") or "").strip(),
        "path": node_id,
        "sources": normalize_sources(meta),
        "nodeType": "page",
        "pageType": page_type,
        "topics": normalize_str_list(meta.get("topics", [])),
        "entities": normalize_str_list(meta.get("entities", [])),
        "concepts": normalize_str_list(meta.get("concepts", [])),
        "aliases": normalize_str_list(meta.get("aliases", [])),
        "maturity": str(meta.get("maturity") or "").strip(),
        "canonicalEntity": str(meta.get("canonical_entity") or "").strip(),
    }


def normalize_str_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if value:
        return [str(value).strip()]
    return []


def synthetic_entity_id(label: str) -> str:
    slug = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]+", "-", label.casefold()).strip("-")
    return f"entity:{slug or 'entity'}"


def synthetic_entity_node(label: str) -> dict[str, object]:
    node_id = synthetic_entity_id(label)
    return {
        "id": node_id,
        "label": label,
        "type": "entity",
        "summary": "",
        "confidence": "inferred",
        "status": "active",
        "updated": "",
        "path": node_id,
        "sources": [],
        "nodeType": "entity",
        "pageType": "entity",
        "topics": [],
        "entities": [],
        "concepts": [],
        "aliases": [],
        "maturity": "emerging",
    }


def build_page_lookups(records: list[dict[str, object]]) -> tuple[dict[str, str], dict[str, dict[str, object]]]:
    lookup: dict[str, str] = {}
    node_map: dict[str, dict[str, object]] = {}
    page_ids = {str(record["id"]) for record in records}
    for record in records:
        page_id = str(record["id"])
        title = str(record["title"])
        meta = record.get("meta", {})
        status = str(meta.get("status") or "").strip().casefold() if isinstance(meta, dict) else ""
        canonical_entity = str(meta.get("canonical_entity") or "").strip() if isinstance(meta, dict) else ""
        aliases = normalize_str_list(meta.get("aliases", [])) if isinstance(meta, dict) else []
        target_page_id = canonical_entity if (
            str(record["page_type"]) == "entity"
            and status == "merged"
            and canonical_entity in page_ids
        ) else page_id
        node_map[page_id] = {
            "id": page_id,
            "title": title,
            "type": str(record["page_type"]),
        }
        alias_keys: list[str] = []
        for alias in aliases:
            alias_keys.extend(entity_label_keys(alias))
        title_keys = entity_label_keys(title) if str(record["page_type"]) == "entity" else [title.strip().casefold()]
        for key in ordered_unique([
            page_id.casefold(),
            Path(page_id).as_posix().casefold(),
            Path(page_id).stem.casefold(),
            *title_keys,
            *alias_keys,
        ]):
            lookup[key] = target_page_id
    return lookup, node_map


def is_merged_entity_record(record: dict[str, object]) -> bool:
    if str(record.get("page_type") or "") != "entity":
        return False
    meta = record.get("meta", {})
    if not isinstance(meta, dict):
        return False
    return (
        str(meta.get("status") or "").strip().casefold() == "merged"
        and str(meta.get("canonical_entity") or "").strip() != ""
    )


def resolve_page_target(
    root: Path,
    current_page: Path,
    value: object,
    lookup: dict[str, str],
) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    wikilink = re.fullmatch(r"\[\[([^\]]+)\]\]", raw)
    if wikilink:
        raw = wikilink.group(1).strip()
    if raw.endswith(".md"):
        if raw.startswith("wiki/"):
            return lookup.get(raw.casefold(), "")
        target = (current_page.parent / raw).resolve()
        try:
            relative = target.relative_to(root.resolve()).as_posix()
        except ValueError:
            relative = raw
        return lookup.get(relative.casefold(), "")
    return lookup.get(raw.casefold(), "")


def graph_relation_items(meta: dict[str, object]) -> list[dict[str, str]]:
    graph_meta = meta.get("graph", {})
    if not isinstance(graph_meta, dict):
        return []
    raw_items = graph_meta.get("explicit_relations", [])
    if not isinstance(raw_items, list):
        return []
    items: list[dict[str, str]] = []
    for row in raw_items:
        if not isinstance(row, dict):
            continue
        relation_type = str(row.get("type") or "").strip()
        target = str(row.get("target") or "").strip()
        if relation_type and target:
            items.append({"type": relation_type, "target": target})
    return items


def extract_claims(meta: dict[str, object], body: str) -> list[dict[str, object]]:
    claims: list[dict[str, object]] = []
    raw_claims = meta.get("claims", [])
    if isinstance(raw_claims, list):
        for row in raw_claims:
            if isinstance(row, dict):
                text = str(row.get("text") or "").strip()
                if not text:
                    continue
                claims.append({
                    "text": text,
                    "confidence": str(row.get("confidence") or "").strip(),
                    "supports": normalize_str_list(row.get("supports", [])),
                    "contradicts": normalize_str_list(row.get("contradicts", [])),
                })
            else:
                text = str(row).strip()
                if text:
                    claims.append({"text": text, "confidence": "", "supports": [], "contradicts": []})

    current_heading = ""
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("## "):
            current_heading = stripped[3:].strip().casefold()
            continue
        if current_heading != "claims" or not stripped.startswith("- "):
            continue
        bullet = stripped[2:].strip()
        match = re.match(r"\[(?P<confidence>[^\]]+)\]\s*(?P<text>.+)", bullet)
        if match:
            claims.append({
                "text": match.group("text").strip(),
                "confidence": match.group("confidence").strip(),
                "supports": [],
                "contradicts": [],
            })
        elif bullet:
            claims.append({"text": bullet, "confidence": "", "supports": [], "contradicts": []})

    deduped: list[dict[str, object]] = []
    seen: set[str] = set()
    for item in claims:
        text = str(item.get("text") or "").strip()
        key = text.casefold()
        if not text or key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def extract_connection_relations(body: str) -> list[dict[str, str]]:
    relations: list[dict[str, str]] = []
    current_heading = ""
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("## "):
            current_heading = stripped[3:].strip().casefold()
            continue
        if current_heading not in {"connections", "knowledge connections"} or not stripped.startswith("- "):
            continue
        bullet = stripped[2:].strip()
        match = re.match(r"(?P<relation>[a-z_]+)\s*:\s*(?P<target>\[\[[^\]]+\]\]|[^-]+)", bullet)
        if not match:
            continue
        relations.append({
            "type": match.group("relation").strip(),
            "target": match.group("target").strip(),
        })
    return relations


def frontmatter_block_lines(text: str, key: str) -> list[str]:
    if not text.startswith("---\n"):
        return []
    parts = text.split("\n---\n", 1)
    if len(parts) != 2:
        return []
    lines = parts[0].splitlines()[1:]
    collecting = False
    block: list[str] = []
    for raw in lines:
        if not collecting and raw.strip() == f"{key}:":
            collecting = True
            continue
        if not collecting:
            continue
        if raw and not raw.startswith(" "):
            break
        block.append(raw)
    return block


def parse_frontmatter_claims_block(text: str) -> list[dict[str, object]]:
    lines = frontmatter_block_lines(text, "claims")
    if not lines:
        return []
    claims: list[dict[str, object]] = []
    current: dict[str, object] | None = None
    current_list_key: str | None = None
    for raw in lines:
        line = raw.rstrip()
        stripped = line.strip()
        if not stripped:
            continue
        if raw.startswith("  - "):
            if current:
                claims.append(current)
            current = {"supports": [], "contradicts": []}
            current_list_key = None
            head = stripped[2:]
            if ": " in head:
                key, value = head.split(": ", 1)
                current[key.strip()] = value.strip()
            continue
        if current is None:
            continue
        if stripped.endswith(":"):
            list_key = stripped[:-1].strip()
            if list_key in {"supports", "contradicts"}:
                current.setdefault(list_key, [])
                current_list_key = list_key
            continue
        if raw.startswith("      - ") and current_list_key:
            current.setdefault(current_list_key, []).append(stripped[2:].strip())
            continue
        if ": " in stripped:
            key, value = stripped.split(": ", 1)
            current[key.strip()] = value.strip()
            current_list_key = None
    if current:
        claims.append(current)
    return claims


def parse_frontmatter_graph_relations_block(text: str) -> list[dict[str, str]]:
    lines = frontmatter_block_lines(text, "graph")
    if not lines:
        return []
    relations: list[dict[str, str]] = []
    in_explicit_relations = False
    current: dict[str, str] | None = None
    for raw in lines:
        line = raw.rstrip()
        stripped = line.strip()
        if not stripped:
            continue
        if stripped == "explicit_relations:":
            in_explicit_relations = True
            continue
        if not in_explicit_relations:
            continue
        if stripped.startswith("- "):
            if current and current.get("type") and current.get("target"):
                relations.append(current)
            current = {}
            head = stripped[2:]
            if ": " in head:
                key, value = head.split(": ", 1)
                current[key.strip()] = value.strip()
            continue
        if current is None:
            continue
        if ": " in stripped:
            key, value = stripped.split(": ", 1)
            current[key.strip()] = value.strip()
    if current and current.get("type") and current.get("target"):
        relations.append(current)
    return relations


def add_node(nodes: dict[str, dict[str, object]], payload: dict[str, object]) -> None:
    node_id = str(payload["id"])
    existing = nodes.get(node_id)
    if existing is None:
        nodes[node_id] = payload
        return

    existing_type = str(existing.get("type") or "")
    new_type = str(payload.get("type") or "")
    if existing_type in {"raw", "file", "page"} and new_type not in {"", existing_type, "raw"}:
        existing["type"] = new_type

    existing_label = str(existing.get("label") or "")
    new_label = str(payload.get("label") or "")
    if new_label and (existing_label == Path(node_id).stem or existing_type == "raw"):
        existing["label"] = new_label

    for key in ("summary", "confidence", "status", "updated", "path", "nodeType", "pageType", "maturity"):
        old_value = str(existing.get(key) or "").strip()
        new_value = str(payload.get(key) or "").strip()
        if new_value and not old_value:
            existing[key] = new_value

    merged_sources = ordered_unique([
        *[str(item) for item in existing.get("sources", [])],
        *[str(item) for item in payload.get("sources", [])],
    ])
    existing["sources"] = merged_sources
    for key in ("topics", "entities", "concepts", "aliases"):
        existing[key] = ordered_unique([
            *[str(item) for item in existing.get(key, [])],
            *[str(item) for item in payload.get(key, [])],
        ])


def add_edge(
    edges: list[dict[str, str]],
    seen_edges: set[tuple[str, str, str]],
    source: str,
    target: str,
    edge_type: str,
) -> None:
    edge_key = (source, target, edge_type)
    if edge_key not in seen_edges:
        seen_edges.add(edge_key)
        edges.append({
            "source": source,
            "target": target,
            "type": edge_type,
            "relation": edge_type,
        })


def node_type_for_path(node_id: str) -> str:
    if node_id.startswith("raw/"):
        return "raw"
    if node_id.startswith("wiki/"):
        parent_name = Path(node_id).parent.name
        if parent_name.endswith("s"):
            return parent_name[:-1]
        return "page"
    return "file"


def text_tokens(*parts: object) -> set[str]:
    tokens: set[str] = set()
    for part in parts:
        for token in TOKEN_RE.findall(str(part or "").lower()):
            if token in COMMON_TOKENS:
                continue
            tokens.add(token)
    return tokens


def node_metrics(
    nodes: list[dict[str, object]],
    edges: list[dict[str, str]],
) -> dict[str, dict[str, object]]:
    metrics: dict[str, dict[str, object]] = {
        str(node["id"]): {
            "degree": 0,
            "inbound": 0,
            "outbound": 0,
            "neighbor_ids": set(),
            "neighbor_types": set(),
            "edge_types": set(),
        }
        for node in nodes
    }

    node_type_map = {str(node["id"]): str(node.get("type") or "page") for node in nodes}
    for edge in edges:
        source = str(edge.get("source") or "")
        target = str(edge.get("target") or "")
        edge_type = str(edge.get("type") or "links_to")
        if source not in metrics or target not in metrics:
            continue
        metrics[source]["degree"] += 1
        metrics[source]["outbound"] += 1
        metrics[source]["neighbor_ids"].add(target)
        metrics[source]["neighbor_types"].add(node_type_map.get(target, "page"))
        metrics[source]["edge_types"].add(edge_type)

        metrics[target]["degree"] += 1
        metrics[target]["inbound"] += 1
        metrics[target]["neighbor_ids"].add(source)
        metrics[target]["neighbor_types"].add(node_type_map.get(source, "page"))
        metrics[target]["edge_types"].add(edge_type)

    return metrics


def compute_link_suggestions(
    nodes: list[dict[str, object]],
    metrics: dict[str, dict[str, object]],
    edges: list[dict[str, str]],
    limit: int = 8,
    excluded_types: set[str] | None = None,
) -> list[dict[str, object]]:
    excluded = excluded_types or {"raw", "file"}
    undirected_edges = {
        tuple(sorted((str(edge.get("source") or ""), str(edge.get("target") or ""))))
        for edge in edges
    }
    candidates = [
        node for node in nodes if str(node.get("type") or "page") not in excluded
    ]
    candidate_data = {
        str(node["id"]): {
            "label": str(node.get("label") or node["id"]),
            "tokens": text_tokens(node.get("label"), node.get("summary"), node.get("path")),
            "sources": {str(item).strip() for item in node.get("sources", []) if str(item).strip()},
        }
        for node in candidates
    }

    suggestions: list[dict[str, object]] = []
    for index, left in enumerate(candidates):
        left_id = str(left["id"])
        for right in candidates[index + 1 :]:
            right_id = str(right["id"])
            if tuple(sorted((left_id, right_id))) in undirected_edges:
                continue

            left_data = candidate_data[left_id]
            right_data = candidate_data[right_id]
            shared_tokens = sorted(left_data["tokens"] & right_data["tokens"])
            shared_sources = sorted(left_data["sources"] & right_data["sources"])
            shared_neighbors = sorted(
                set(metrics[left_id]["neighbor_ids"]) & set(metrics[right_id]["neighbor_ids"])
            )

            score = 0
            reasons: list[str] = []
            if shared_sources:
                score += 5 + min(2, len(shared_sources))
                reasons.append("shared sources")
            if shared_tokens:
                score += min(4, len(shared_tokens)) * 2
                reasons.append("shared keywords")
            if shared_neighbors:
                score += 2
                reasons.append("shared graph neighbors")
            if str(left.get("type") or "") == str(right.get("type") or ""):
                score += 1

            if score < 5:
                continue

            suggestions.append({
                "source": left_id,
                "sourceLabel": left_data["label"],
                "target": right_id,
                "targetLabel": right_data["label"],
                "score": score,
                "reasons": reasons,
                "sharedTokens": shared_tokens[:4],
                "sharedSources": shared_sources[:3],
            })

    return sorted(
        suggestions,
        key=lambda item: (
            -int(item["score"]),
            str(item["sourceLabel"]).lower(),
            str(item["targetLabel"]).lower(),
        ),
    )[:limit]


def graph_summary_text(insights: dict[str, object]) -> str:
    stats = insights["stats"]
    isolated_count = int(stats["isolatedCount"])
    weak_count = int(stats["weakCount"])
    suggestion_count = len(insights["suggestedLinks"])
    bridge_count = len(insights["bridgeNodes"])
    top_node = next(iter(insights["topNodes"]), None)
    if top_node:
        lead = f"The current key page is {top_node['title']}."
    else:
        lead = "The graph is still taking shape."

    if isolated_count:
        health = f"There are {isolated_count} isolated pages that need links first."
    elif weak_count:
        health = f"There are {weak_count} weakly connected pages that need more context."
    else:
        health = "The main pages already have a basic connection structure."

    if suggestion_count:
        next_step = f"You can review {suggestion_count} suggested links next."
    elif bridge_count:
        next_step = f"You can expand the structure from {bridge_count} bridge pages next."
    else:
        next_step = "Next, improve summaries, sources, or cross-page links."
    return " ".join([lead, health, next_step])


def compute_graph_insights(
    nodes: list[dict[str, object]],
    edges: list[dict[str, str]],
    excluded_types: set[str] | None = None,
) -> dict[str, object]:
    excluded = excluded_types or {"raw", "file"}
    candidate_nodes = [node for node in nodes if str(node.get("type") or "page") not in excluded]
    candidate_ids = {str(node["id"]) for node in candidate_nodes}
    candidate_edges = [
        edge for edge in edges
        if str(edge.get("source") or "") in candidate_ids and str(edge.get("target") or "") in candidate_ids
    ]
    metrics = node_metrics(candidate_nodes, candidate_edges)
    node_items: list[dict[str, object]] = []
    isolated_nodes: list[dict[str, object]] = []
    bridge_nodes: list[dict[str, object]] = []

    for node in candidate_nodes:
        node_id = str(node["id"])
        info = metrics[node_id]
        degree = int(info["degree"])
        inbound = int(info["inbound"])
        outbound = int(info["outbound"])
        neighbor_types = sorted(str(item) for item in info["neighbor_types"])
        edge_types = sorted(str(item) for item in info["edge_types"])
        top_score = degree * 3 + inbound * 2 + len(neighbor_types) * 2 + len(edge_types)
        bridge_score = len(neighbor_types) * 3 + len(edge_types) * 2 + max(0, degree - 1)

        node_item = {
            "id": node_id,
            "title": str(node.get("label") or node_id),
            "type": str(node.get("type") or "page"),
            "degree": degree,
            "inbound": inbound,
            "outbound": outbound,
            "neighborTypes": neighbor_types,
            "edgeTypes": edge_types,
            "topScore": top_score,
            "bridgeScore": bridge_score,
        }
        node_items.append(node_item)

        if degree == 0:
            isolated_nodes.append({
                "id": node_id,
                "title": node_item["title"],
                "type": node_item["type"],
                "severity": "isolated",
                "reason": "No relationships with other pages yet",
            })
        elif degree == 1:
            isolated_nodes.append({
                "id": node_id,
                "title": node_item["title"],
                "type": node_item["type"],
                "severity": "weak",
                "reason": "Only one relationship so far. Add more links.",
            })

        if degree >= 2 and len(neighbor_types) >= 2:
            bridge_nodes.append({
                "id": node_id,
                "title": node_item["title"],
                "type": node_item["type"],
                "score": bridge_score,
                "reason": f"Connects {len(neighbor_types)} page types and works well as a bridge.",
            })

    top_nodes = sorted(
        node_items,
        key=lambda item: (
            -int(item["topScore"]),
            -int(item["degree"]),
            str(item["title"]).lower(),
        ),
    )[:6]
    bridge_nodes = sorted(
        bridge_nodes,
        key=lambda item: (-int(item["score"]), str(item["title"]).lower()),
    )[:5]
    isolated_nodes = sorted(
        isolated_nodes,
        key=lambda item: (
            0 if str(item["severity"]) == "isolated" else 1,
            str(item["title"]).lower(),
        ),
    )[:8]
    suggested_links = compute_link_suggestions(candidate_nodes, metrics, candidate_edges, excluded_types=excluded)

    insights = {
        "stats": {
            "nodeCount": len(candidate_nodes),
            "edgeCount": len(candidate_edges),
            "isolatedCount": sum(1 for item in isolated_nodes if item["severity"] == "isolated"),
            "weakCount": sum(1 for item in isolated_nodes if item["severity"] == "weak"),
            "averageDegree": round((len(candidate_edges) * 2 / len(candidate_nodes)) if candidate_nodes else 0, 2),
        },
        "topNodes": [
            {
                "id": item["id"],
                "title": item["title"],
                "type": item["type"],
                "score": item["topScore"],
                "reason": f"Degree {item['degree']}, inbound {item['inbound']}, spanning {len(item['neighborTypes'])} neighbor types.",
            }
            for item in top_nodes
        ],
        "bridgeNodes": bridge_nodes,
        "isolatedNodes": isolated_nodes,
        "suggestedLinks": suggested_links,
    }
    insights["summary"] = graph_summary_text(insights)
    return insights


def compute_layout(nodes: list[dict[str, object]], edges: list[dict[str, str]]) -> tuple[dict[str, dict[str, int]], int, int]:
    columns: dict[int, list[dict[str, object]]] = {}
    degrees: dict[str, int] = {str(node["id"]): 0 for node in nodes}
    for edge in edges:
        source = str(edge.get("source") or "")
        target = str(edge.get("target") or "")
        if source in degrees:
            degrees[source] += 1
        if target in degrees:
            degrees[target] += 1

    for node in nodes:
        column = TYPE_ORDER.get(str(node.get("type") or "page"), 2)
        columns.setdefault(column, []).append(node)

    positions: dict[str, dict[str, int]] = {}
    left_padding = 90
    top_padding = 84
    column_width = 220
    row_gap = 92
    max_rows = 1

    for column_index, items in sorted(columns.items()):
        sorted_items = sorted(
            items,
            key=lambda item: (
                -degrees.get(str(item["id"]), 0),
                TYPE_LANE_OFFSET.get(str(item.get("type") or "page"), 0),
                str(item.get("label") or "").lower(),
            ),
        )
        max_rows = max(max_rows, len(sorted_items))
        start_y = top_padding + max(0, (max_rows - len(sorted_items)) * row_gap // 2)
        for row_index, item in enumerate(sorted_items):
            node_type = str(item.get("type") or "page")
            positions[str(item["id"])] = {
                "x": left_padding + column_index * column_width + TYPE_LANE_OFFSET.get(node_type, 0),
                "y": start_y + row_index * row_gap,
            }

    width = max(960, left_padding * 2 + max(1, max(columns.keys(), default=0) + 1) * column_width + 40)
    height = max(760, top_padding * 2 + max_rows * row_gap)
    return positions, width, height


def _graph_view(graph: dict[str, object], view_name: str | None = None) -> dict[str, object]:
    requested_view = view_name or str(graph.get("default_view") or "knowledge")
    views = graph.get("views", {})
    if isinstance(views, dict):
        view = views.get(requested_view, {})
        if isinstance(view, dict):
            nodes = view.get("nodes", [])
            edges = view.get("edges", [])
            insights = view.get("insights", {})
            if isinstance(nodes, list) and isinstance(edges, list) and isinstance(insights, dict):
                return {
                    "name": requested_view,
                    "nodes": nodes,
                    "edges": edges,
                    "insights": insights,
                }
    return {
        "name": "legacy",
        "nodes": list(graph.get("nodes", [])),
        "edges": list(graph.get("edges", [])),
        "insights": graph.get("insights", {}) if isinstance(graph.get("insights"), dict) else {},
    }


def _render_view_payload(
    nodes: list[dict[str, object]],
    edges: list[dict[str, str]],
    insights: dict[str, object] | None,
) -> dict[str, object]:
    active_insights = insights if isinstance(insights, dict) else compute_graph_insights(nodes, edges)
    positions, width, height = compute_layout(nodes, edges)

    rendered_nodes: list[dict[str, object]] = []
    for node in nodes:
        node_id = str(node["id"])
        pos = positions.get(node_id, {"x": 0, "y": 0})
        node_type = str(node.get("type") or "page")
        rendered_nodes.append({
            "id": node_id,
            "label": str(node.get("label") or node_id),
            "type": node_type,
            "summary": str(node.get("summary") or ""),
            "confidence": str(node.get("confidence") or ""),
            "status": str(node.get("status") or ""),
            "updated": str(node.get("updated") or ""),
            "path": str(node.get("path") or node_id),
            "sources": [str(item) for item in node.get("sources", [])],
            "nodeType": str(node.get("nodeType") or "page"),
            "pageType": str(node.get("pageType") or node_type),
            "aliases": [str(item) for item in node.get("aliases", [])],
            "maturity": str(node.get("maturity") or ""),
            "x": pos["x"],
            "y": pos["y"],
            "color": TYPE_COLORS.get(node_type, "#60a5fa"),
        })

    return {
        "nodeCount": len(rendered_nodes),
        "edgeCount": len(edges),
        "canvasWidth": width,
        "canvasHeight": height,
        "nodes": rendered_nodes,
        "edges": edges,
        "insights": active_insights,
    }


def html_payload(root: Path, graph: dict[str, object]) -> dict[str, object]:
    active_view = _graph_view(graph)
    nodes = list(active_view.get("nodes", []))
    edges = list(active_view.get("edges", []))
    insights = active_view.get("insights")
    if not isinstance(insights, dict):
        insights = compute_graph_insights(nodes, edges)
    views = graph.get("views", {})
    rendered_views: dict[str, dict[str, object]] = {}
    if isinstance(views, dict):
        for view_name, view in views.items():
            if not isinstance(view, dict):
                continue
            view_nodes = view.get("nodes", [])
            view_edges = view.get("edges", [])
            view_insights = view.get("insights", {})
            if not isinstance(view_nodes, list) or not isinstance(view_edges, list):
                continue
            rendered_views[str(view_name)] = _render_view_payload(view_nodes, view_edges, view_insights if isinstance(view_insights, dict) else None)
    active_payload = rendered_views.get(str(active_view.get("name") or ""), _render_view_payload(nodes, edges, insights))

    return {
        "generatedAt": graph.get("generated_at") or today_str(),
        "rootName": root.name,
        "viewName": active_view.get("name") or graph.get("default_view") or "knowledge",
        "defaultView": str(graph.get("default_view") or "knowledge"),
        "schemaVersion": str(graph.get("schema_version") or "1"),
        "availableViews": sorted(rendered_views.keys()),
        "views": rendered_views,
        "nodeCount": int(active_payload["nodeCount"]),
        "edgeCount": int(active_payload["edgeCount"]),
        "canvasWidth": int(active_payload["canvasWidth"]),
        "canvasHeight": int(active_payload["canvasHeight"]),
        "nodes": list(active_payload["nodes"]),
        "edges": list(active_payload["edges"]),
        "insights": dict(active_payload["insights"]),
        "edgeStyles": EDGE_STYLES,
    }


def safe_json_for_script(payload: dict[str, object]) -> str:
    return (
        json.dumps(payload, ensure_ascii=False)
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )


def render_graph_html(payload: dict[str, object]) -> str:
    data_json = safe_json_for_script(payload)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>ThinkWiki Graph</title>
  <style>
    :root {{
      --bg: #0b1020;
      --panel: #121935;
      --panel-soft: #182142;
      --text: #edf2ff;
      --muted: #a8b3cf;
      --border: rgba(255, 255, 255, 0.1);
      --accent: #8ab4ff;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: linear-gradient(180deg, #0b1020 0%, #10172f 100%);
      color: var(--text);
    }}
    .layout {{
      display: grid;
      grid-template-columns: 300px 1fr 340px;
      min-height: 100vh;
    }}
    .panel {{
      padding: 20px;
      overflow: auto;
      background: rgba(9, 13, 28, 0.82);
    }}
    .panel.left {{
      border-right: 1px solid var(--border);
    }}
    .panel.right {{
      border-left: 1px solid var(--border);
    }}
    .stage {{
      overflow: auto;
      padding: 16px;
    }}
    .card {{
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 16px;
      padding: 16px;
      margin-bottom: 14px;
    }}
    .title {{
      font-size: 1.15rem;
      margin: 0 0 10px;
    }}
    .lead, .muted {{
      color: var(--muted);
      line-height: 1.6;
    }}
    .stats {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 10px;
    }}
    .stat {{
      background: var(--panel-soft);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 10px;
    }}
    .stat strong {{
      display: block;
      font-size: 1.15rem;
    }}
    input, select, button {{
      width: 100%;
      border-radius: 12px;
      border: 1px solid var(--border);
      background: var(--panel);
      color: var(--text);
      padding: 10px 12px;
      margin-bottom: 10px;
    }}
    button {{
      cursor: pointer;
    }}
    .legend-item {{
      display: flex;
      gap: 8px;
      align-items: center;
      margin-bottom: 8px;
      color: var(--muted);
      font-size: 0.92rem;
    }}
    .dot {{
      width: 10px;
      height: 10px;
      border-radius: 999px;
      display: inline-block;
    }}
    .edge-swatch {{
      width: 22px;
      height: 0;
      border-top-width: 2px;
      border-top-style: solid;
      display: inline-block;
      opacity: 0.9;
    }}
    .toggle-list {{
      display: grid;
      gap: 10px;
    }}
    .focus-row {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 10px;
      margin-bottom: 10px;
    }}
    .focus-chip {{
      border-radius: 999px;
      border: 1px solid var(--border);
      background: rgba(255,255,255,0.03);
      color: var(--muted);
      padding: 9px 12px;
      font-size: 0.92rem;
      text-align: center;
    }}
    .focus-chip.active {{
      border-color: rgba(138,180,255,0.55);
      color: var(--text);
      background: rgba(138,180,255,0.12);
    }}
    .mode-row {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 10px;
      margin-bottom: 10px;
    }}
    .toggle-item {{
      display: flex;
      align-items: center;
      gap: 10px;
      color: var(--muted);
      font-size: 0.92rem;
    }}
    .toggle-item input {{
      width: auto;
      margin: 0;
      accent-color: #8ab4ff;
    }}
    .chip {{
      display: inline-block;
      margin: 0 8px 8px 0;
      padding: 4px 10px;
      border-radius: 999px;
      border: 1px solid var(--border);
      color: var(--muted);
      font-size: 0.85rem;
    }}
    .detail-row {{
      margin-bottom: 12px;
    }}
    .detail-row strong {{
      display: block;
      margin-bottom: 4px;
    }}
    .detail-stats {{
      display: grid;
      gap: 10px;
      margin: 12px 0;
    }}
    .detail-stat-row {{
      display: flex;
      justify-content: space-between;
      gap: 12px;
      color: var(--muted);
      font-size: 0.94rem;
      padding: 8px 10px;
      border-radius: 12px;
      background: rgba(255,255,255,0.03);
      border: 1px solid rgba(255,255,255,0.06);
    }}
    .empty {{
      color: var(--muted);
      padding: 16px;
      border: 1px dashed var(--border);
      border-radius: 12px;
    }}
    .sources {{
      max-height: 220px;
      overflow: auto;
      white-space: pre-wrap;
      word-break: break-word;
    }}
    .action {{
      display: inline-block;
      margin-top: 10px;
      color: var(--accent);
      text-decoration: none;
    }}
    .section-title {{
      margin: 18px 0 10px;
      font-size: 0.95rem;
    }}
    .insight-summary {{
      margin: 0;
      color: var(--muted);
      line-height: 1.6;
    }}
    .insight-list {{
      display: grid;
      gap: 10px;
    }}
    .insight-item {{
      width: 100%;
      text-align: left;
      background: rgba(255,255,255,0.03);
      border: 1px solid rgba(255,255,255,0.08);
      border-radius: 14px;
      padding: 12px;
      margin: 0;
    }}
    .insight-item.active {{
      border-color: rgba(138,180,255,0.52);
      background: rgba(138,180,255,0.12);
    }}
    .insight-item strong {{
      display: block;
      margin-bottom: 4px;
      font-size: 0.95rem;
    }}
    .insight-meta {{
      color: var(--muted);
      font-size: 0.88rem;
      line-height: 1.5;
    }}
    .insight-score {{
      display: inline-block;
      margin-top: 8px;
      padding: 2px 8px;
      border-radius: 999px;
      background: rgba(255,255,255,0.05);
      color: var(--muted);
      font-size: 0.82rem;
    }}
    .insight-reasons {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-top: 8px;
    }}
    .insight-reason {{
      display: inline-block;
      padding: 3px 8px;
      border-radius: 999px;
      background: rgba(255,255,255,0.05);
      border: 1px solid rgba(255,255,255,0.08);
      color: var(--muted);
      font-size: 0.8rem;
    }}
    svg {{
      display: block;
      background:
        radial-gradient(circle at center, rgba(255, 255, 255, 0.04) 1px, transparent 1px);
      background-size: 24px 24px;
      border-radius: 16px;
    }}
    @media (max-width: 1100px) {{
      .layout {{
        grid-template-columns: 1fr;
      }}
      .panel.left, .panel.right {{
        border: 0;
        border-bottom: 1px solid var(--border);
      }}
    }}
  </style>
</head>
<body>
  <div class="layout">
    <aside class="panel left">
      <div class="card">
        <h1 class="title">ThinkWiki Graph</h1>
        <p class="lead">Offline graph explorer for ThinkWiki. The default view is the content knowledge graph, where you can search, filter, and inspect page structure plus semantic content relations.</p>
      </div>
      <div class="card">
        <div class="stats">
          <div class="stat"><strong id="nodeCountValue">{payload["nodeCount"]}</strong><span class="muted">Nodes</span></div>
          <div class="stat"><strong id="edgeCountValue">{payload["edgeCount"]}</strong><span class="muted">Edges</span></div>
        </div>
        <p class="muted">Wiki: {payload["rootName"]}</p>
        <p class="muted">Schema: <span id="schemaVersionValue">{payload["schemaVersion"]}</span></p>
        <p class="muted">View: <span id="viewNameValue">{payload["viewName"]}</span></p>
        <p class="muted">Generated: {payload["generatedAt"]}</p>
      </div>
      <div class="card">
        <h2 class="title">Graph Modes</h2>
        <div class="mode-row">
          <button type="button" class="focus-chip active" data-view-mode="knowledge">knowledge</button>
          <button type="button" class="focus-chip" data-view-mode="document">document</button>
          <button type="button" class="focus-chip" data-view-mode="suggested">suggested</button>
        </div>
        <p class="muted">Knowledge shows semantic content relations, Document shows file and page relations, and Suggested shows candidate content edges.</p>
      </div>
      <div class="card">
        <h2 class="title">Quick Focus</h2>
        <div class="focus-row">
          <button type="button" class="focus-chip active" data-focus-type="">All</button>
          <button type="button" class="focus-chip" data-focus-type="concept">concepts</button>
          <button type="button" class="focus-chip" data-focus-type="decision">decisions</button>
          <button type="button" class="focus-chip" data-focus-type="source">sources</button>
          <button type="button" class="focus-chip" data-focus-type="claim">claims</button>
        </div>
      </div>
      <div class="card">
        <input id="search" type="search" placeholder="Search title, path, summary">
        <select id="scopeFilter">
          <option value="all">Whole Graph</option>
          <option value="1">1-hop neighborhood</option>
          <option value="2">2-hop neighborhood</option>
        </select>
        <select id="typeFilter">
          <option value="">All Types</option>
          <option value="source">source</option>
          <option value="topic">topic</option>
          <option value="concept">concept</option>
          <option value="entity">entity</option>
          <option value="decision">decision</option>
          <option value="synthesis">synthesis</option>
          <option value="query">query</option>
          <option value="claim">claim</option>
          <option value="raw">raw</option>
          <option value="file">file</option>
        </select>
        <select id="statusFilter">
          <option value="">All Statuses</option>
          <option value="active">active</option>
          <option value="stale">stale</option>
          <option value="archived">archived</option>
          <option value="superseded">superseded</option>
        </select>
        <select id="confidenceFilter">
          <option value="">All Confidence Levels</option>
          <option value="verified">verified</option>
          <option value="extracted">extracted</option>
          <option value="mixed">mixed</option>
          <option value="inferred">inferred</option>
        </select>
        <button id="resetBtn">Reset View</button>
      </div>
      <div class="card">
        <h2 class="title">Legend</h2>
        <div class="legend-item"><span class="dot" style="background:#60a5fa"></span>source</div>
        <div class="legend-item"><span class="dot" style="background:#34d399"></span>topic</div>
        <div class="legend-item"><span class="dot" style="background:#a78bfa"></span>concept</div>
        <div class="legend-item"><span class="dot" style="background:#f472b6"></span>entity</div>
        <div class="legend-item"><span class="dot" style="background:#fb923c"></span>decision</div>
        <div class="legend-item"><span class="dot" style="background:#22d3ee"></span>synthesis</div>
        <div class="legend-item"><span class="dot" style="background:#cbd5e1"></span>query</div>
        <div class="legend-item"><span class="dot" style="background:#facc15"></span>claim</div>
        <div class="legend-item"><span class="dot" style="background:#94a3b8"></span>raw / file</div>
      </div>
      <div class="card">
        <h2 class="title">Edge Legend</h2>
        <div class="legend-item"><span class="edge-swatch" style="border-top-color:rgba(138,180,255,0.85)"></span>references</div>
        <div class="legend-item"><span class="edge-swatch" style="border-top-color:rgba(255,255,255,0.65)"></span>links_to</div>
        <div class="legend-item"><span class="edge-swatch" style="border-top-color:rgba(52,211,153,0.9); border-top-style:dashed;"></span>includes</div>
        <div class="legend-item"><span class="edge-swatch" style="border-top-color:rgba(251,146,60,0.9); border-top-style:dashed;"></span>cites</div>
        <div class="legend-item"><span class="edge-swatch" style="border-top-color:rgba(96,165,250,0.9); border-top-style:dashed;"></span>about</div>
        <div class="legend-item"><span class="edge-swatch" style="border-top-color:rgba(52,211,153,0.9)"></span>belongs_to</div>
        <div class="legend-item"><span class="edge-swatch" style="border-top-color:rgba(255,255,255,0.8)"></span>related_to</div>
        <div class="legend-item"><span class="edge-swatch" style="border-top-color:rgba(167,139,250,0.9); border-top-style:dashed;"></span>depends_on</div>
        <div class="legend-item"><span class="edge-swatch" style="border-top-color:rgba(250,204,21,0.95)"></span>asserts</div>
        <div class="legend-item"><span class="edge-swatch" style="border-top-color:rgba(34,211,238,0.95)"></span>supports</div>
        <div class="legend-item"><span class="edge-swatch" style="border-top-color:rgba(244,114,182,0.95); border-top-style:dashed;"></span>contradicts</div>
        <div class="legend-item"><span class="edge-swatch" style="border-top-color:rgba(138,180,255,0.95); border-top-style:dashed;"></span>suggests_related_to</div>
      </div>
      <div class="card">
        <h2 class="title">Edge Filters</h2>
        <div class="toggle-list">
          <label class="toggle-item"><input type="checkbox" id="edgeType-references" checked>references</label>
          <label class="toggle-item"><input type="checkbox" id="edgeType-links_to" checked>links_to</label>
          <label class="toggle-item"><input type="checkbox" id="edgeType-includes" checked>includes</label>
          <label class="toggle-item"><input type="checkbox" id="edgeType-cites" checked>cites</label>
          <label class="toggle-item"><input type="checkbox" id="edgeType-about" checked>about</label>
          <label class="toggle-item"><input type="checkbox" id="edgeType-belongs_to" checked>belongs_to</label>
          <label class="toggle-item"><input type="checkbox" id="edgeType-related_to" checked>related_to</label>
          <label class="toggle-item"><input type="checkbox" id="edgeType-depends_on" checked>depends_on</label>
          <label class="toggle-item"><input type="checkbox" id="edgeType-asserts" checked>asserts</label>
          <label class="toggle-item"><input type="checkbox" id="edgeType-supports" checked>supports</label>
          <label class="toggle-item"><input type="checkbox" id="edgeType-contradicts" checked>contradicts</label>
          <label class="toggle-item"><input type="checkbox" id="edgeType-suggests_related_to" checked>suggests_related_to</label>
        </div>
      </div>
    </aside>
    <main class="stage" id="graphStage">
      <svg id="graph" viewBox="0 0 {payload["canvasWidth"]} {payload["canvasHeight"]}" width="{payload["canvasWidth"]}" height="{payload["canvasHeight"]}"></svg>
    </main>
    <aside class="panel right">
      <div class="card">
        <h2 class="title">Graph Insights</h2>
        <div id="insightsPanel" class="empty">Loading graph insights...</div>
      </div>
      <div class="card">
        <h2 class="title">Node Details</h2>
        <div id="detailPanel" class="empty">Click a node to inspect its summary, sources, status, and page path.</div>
      </div>
    </aside>
  </div>
  <script>
    const payload = {data_json};
    const searchEl = document.getElementById("search");
    const typeFilterEl = document.getElementById("typeFilter");
    const statusFilterEl = document.getElementById("statusFilter");
    const confidenceFilterEl = document.getElementById("confidenceFilter");
    const scopeFilterEl = document.getElementById("scopeFilter");
    const resetBtn = document.getElementById("resetBtn");
    const modeButtons = Array.from(document.querySelectorAll("[data-view-mode]"));
    const nodeCountValueEl = document.getElementById("nodeCountValue");
    const edgeCountValueEl = document.getElementById("edgeCountValue");
    const viewNameValueEl = document.getElementById("viewNameValue");
    const insightsPanel = document.getElementById("insightsPanel");
    const detailPanel = document.getElementById("detailPanel");
    const svg = document.getElementById("graph");
    const graphStage = document.getElementById("graphStage");
    const allViews = payload.views || {{}};
    const edgeStyles = payload.edgeStyles || {{}};
    const edgeTypeInputs = Array.from(document.querySelectorAll('input[id^="edgeType-"]'));
    const focusButtons = Array.from(document.querySelectorAll("[data-focus-type]"));

    let activeNodeId = "";
    let activeSuggestionKey = "";
    let activeViewName = payload.defaultView || payload.viewName || "knowledge";
    let view = payload;
    let insights = payload.insights || {{}};
    let nodeMap = new Map();
    let neighbors = new Map();

    function fallbackInsights() {{
      return {{
        stats: {{}},
        topNodes: [],
        bridgeNodes: [],
        isolatedNodes: [],
        suggestedLinks: [],
        summary: "",
      }};
    }}

    function refreshViewState() {{
      view = allViews[activeViewName] || payload;
      insights = view.insights || fallbackInsights();
      nodeMap = new Map((view.nodes || []).map((node) => [node.id, node]));
      neighbors = new Map();
      (view.nodes || []).forEach((node) => neighbors.set(node.id, new Set()));
      (view.edges || []).forEach((edge) => {{
        if (neighbors.has(edge.source)) neighbors.get(edge.source).add(edge.target);
        if (neighbors.has(edge.target)) neighbors.get(edge.target).add(edge.source);
      }});
      svg.setAttribute("viewBox", `0 0 ${{view.canvasWidth || payload.canvasWidth}} ${{view.canvasHeight || payload.canvasHeight}}`);
      svg.setAttribute("width", String(view.canvasWidth || payload.canvasWidth));
      svg.setAttribute("height", String(view.canvasHeight || payload.canvasHeight));
      if (nodeCountValueEl) nodeCountValueEl.textContent = String(view.nodeCount || 0);
      if (edgeCountValueEl) edgeCountValueEl.textContent = String(view.edgeCount || 0);
      if (viewNameValueEl) viewNameValueEl.textContent = String(activeViewName);
      if (activeNodeId && !nodeMap.has(activeNodeId)) activeNodeId = "";
      syncModeButtons();
      syncEdgeTypeInputs();
    }}

    function syncModeButtons() {{
      modeButtons.forEach((button) => {{
        const viewMode = button.getAttribute("data-view-mode") || "";
        button.classList.toggle("active", viewMode === activeViewName);
      }});
    }}

    function syncEdgeTypeInputs() {{
      const visibleEdgeTypes = new Set((view.edges || []).map((edge) => edge.type || "links_to"));
      edgeTypeInputs.forEach((input) => {{
        const edgeType = input.id.replace("edgeType-", "");
        input.disabled = !visibleEdgeTypes.has(edgeType);
        if (input.disabled) input.checked = false;
        else if (!input.checked && visibleEdgeTypes.size <= 4) input.checked = true;
      }});
    }}

    function readHashNodeId() {{
      const raw = String(window.location.hash || "").replace(/^#/, "");
      const params = new URLSearchParams(raw);
      return params.get("node") || "";
    }}

    function updateHash(nodeId) {{
      const params = new URLSearchParams();
      if (nodeId) params.set("node", nodeId);
      const nextHash = params.toString();
      if ((window.location.hash || "").replace(/^#/, "") !== nextHash) {{
        window.location.hash = nextHash;
      }}
    }}

    function escapeHtml(value) {{
      return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#39;");
    }}

    function suggestionKey(sourceId, targetId) {{
      return [String(sourceId || ""), String(targetId || "")].sort().join("::");
    }}

    function activeSuggestionNodeIds() {{
      return new Set(
        String(activeSuggestionKey || "")
          .split("::")
          .filter(Boolean)
      );
    }}

    function enabledEdgeTypes() {{
      const enabled = new Set(
        edgeTypeInputs
          .filter((input) => input.checked)
          .map((input) => input.id.replace("edgeType-", ""))
      );
      return enabled.size ? enabled : new Set(Object.keys(edgeStyles));
    }}

    function syncFocusButtons() {{
      const activeType = typeFilterEl.value || "";
      focusButtons.forEach((button) => {{
        const buttonType = button.getAttribute("data-focus-type") || "";
        button.classList.toggle("active", buttonType === activeType);
      }});
    }}

    function visibleNodeIds() {{
      const query = searchEl.value.trim().toLowerCase();
      const typeNeedle = typeFilterEl.value.trim().toLowerCase();
      const statusNeedle = statusFilterEl.value.trim().toLowerCase();
      const confidenceNeedle = confidenceFilterEl.value.trim().toLowerCase();
      const enabledTypes = enabledEdgeTypes();
      const filteredIds = new Set();

      (view.nodes || []).forEach((node) => {{
        const haystack = [
          node.label,
          node.path,
          node.summary,
          node.type,
          ...(node.sources || []),
        ].join(" ").toLowerCase();

        if (typeNeedle && String(node.type || "").toLowerCase() !== typeNeedle) return;
        if (statusNeedle && String(node.status || "").toLowerCase() !== statusNeedle) return;
        if (confidenceNeedle && String(node.confidence || "").toLowerCase() !== confidenceNeedle) return;
        if (query && !haystack.includes(query)) return;

        filteredIds.add(node.id);
      }});

      const scope = scopeFilterEl.value || "all";
      if (!activeNodeId || !filteredIds.has(activeNodeId) || scope === "all") {{
        return filteredIds;
      }}

      const maxDepth = scope === "2" ? 2 : 1;
      const scopedIds = new Set([activeNodeId]);
      let frontier = new Set([activeNodeId]);

      for (let depth = 0; depth < maxDepth; depth += 1) {{
        const nextFrontier = new Set();
        frontier.forEach((nodeId) => {{
          (view.edges || []).forEach((edge) => {{
            if (!enabledTypes.has(edge.type || "")) return;
            let neighborId = "";
            if (edge.source === nodeId) neighborId = edge.target;
            else if (edge.target === nodeId) neighborId = edge.source;
            else return;
            if (!filteredIds.has(neighborId) || scopedIds.has(neighborId)) return;
            scopedIds.add(neighborId);
            nextFrontier.add(neighborId);
          }});
        }});
        frontier = nextFrontier;
        if (!frontier.size) break;
      }}

      return scopedIds;
    }}

    function createSvgEl(name, attrs = {{}}) {{
      const el = document.createElementNS("http://www.w3.org/2000/svg", name);
      Object.entries(attrs).forEach(([key, value]) => el.setAttribute(key, String(value)));
      return el;
    }}

    function centerNodeInStage(nodeId) {{
      if (!nodeId || !graphStage || !nodeMap.has(nodeId)) return;
      const node = nodeMap.get(nodeId);
      const targetLeft = Math.max(0, node.x - graphStage.clientWidth / 2);
      const targetTop = Math.max(0, node.y - graphStage.clientHeight / 2);
      graphStage.scrollTo({{ left: targetLeft, top: targetTop, behavior: "smooth" }});
    }}

    function edgeStatsForNode(nodeId) {{
      const stats = {{}};
      (view.edges || []).forEach((edge) => {{
        if (edge.source !== nodeId && edge.target !== nodeId) return;
        stats.total = (stats.total || 0) + 1;
        const edgeType = edge.type || "links_to";
        stats[edgeType] = (stats[edgeType] || 0) + 1;
      }});
      return stats;
    }}

    function renderInsightNodeList(title, items, options = {{}}) {{
      const emptyText = options.emptyText || "Nothing to show right now.";
      if (!items || !items.length) {{
        return `
          <h3 class="section-title">${{escapeHtml(title)}}</h3>
          <div class="empty">${{escapeHtml(emptyText)}}</div>
        `;
      }}
      const activeSuggestionNodes = activeSuggestionNodeIds();
      const body = items.map((item) => {{
        const isActive = activeNodeId === item.id || activeSuggestionNodes.has(item.id);
        const score = item.score ? `<span class="insight-score">score ${{escapeHtml(item.score)}}</span>` : "";
        return `
          <button
            type="button"
            class="insight-item${{isActive ? " active" : ""}}"
            data-insight-node="${{escapeHtml(item.id)}}"
          >
            <strong>${{escapeHtml(item.title)}}</strong>
            <div class="insight-meta">${{escapeHtml(item.reason || "")}}</div>
            ${{score}}
          </button>
        `;
      }}).join("");
      return `<h3 class="section-title">${{escapeHtml(title)}}</h3><div class="insight-list">${{body}}</div>`;
    }}

    function renderSuggestionList(items) {{
      if (!items || !items.length) {{
        return `
          <h3 class="section-title">Suggested Links</h3>
          <div class="empty">No high-confidence suggested links right now.</div>
        `;
      }}
      const body = items.map((item) => {{
        const itemKey = suggestionKey(item.source, item.target);
        const isActive = activeSuggestionKey === itemKey;
        const reasons = (item.reasons || []).map((reason) =>
          `<span class="insight-reason">${{escapeHtml(reason)}}</span>`
        ).join("");
        return `
          <button
            type="button"
            class="insight-item${{isActive ? " active" : ""}}"
            data-suggestion-source="${{escapeHtml(item.source)}}"
            data-suggestion-target="${{escapeHtml(item.target)}}"
          >
            <strong>${{escapeHtml(item.sourceLabel)}} → ${{escapeHtml(item.targetLabel)}}</strong>
            <div class="insight-meta">Suggested links that could become explicit context edges.</div>
            <span class="insight-score">score ${{escapeHtml(item.score)}}</span>
            <div class="insight-reasons">${{reasons}}</div>
          </button>
        `;
      }}).join("");
      return `<h3 class="section-title">Suggested Links</h3><div class="insight-list">${{body}}</div>`;
    }}

    function renderInsights() {{
      const stats = insights.stats || {{}};
      const overviewStats = `
        <div class="stats">
          <div class="stat"><strong>${{escapeHtml(stats.nodeCount || 0)}}</strong><span class="muted">Nodes</span></div>
          <div class="stat"><strong>${{escapeHtml(stats.edgeCount || 0)}}</strong><span class="muted">Edges</span></div>
          <div class="stat"><strong>${{escapeHtml(stats.isolatedCount || 0)}}</strong><span class="muted">Isolated</span></div>
          <div class="stat"><strong>${{escapeHtml(stats.averageDegree || 0)}}</strong><span class="muted">Avg Degree</span></div>
        </div>
      `;
      const selectionNote = activeSuggestionKey
        ? `<p class="insight-summary">A suggested link is highlighted, and the graph shows the recommended connection as a dashed edge.</p>`
        : activeNodeId
          ? `<p class="insight-summary">A node is selected, and the insight lists highlight related pages.</p>`
          : "";

      insightsPanel.className = "";
      insightsPanel.innerHTML = `
        ${{overviewStats}}
        <p class="insight-summary">${{escapeHtml(insights.summary || "The graph is ready. Start exploring from the key pages.")}}</p>
        ${{selectionNote}}
        ${{renderInsightNodeList("Key Pages", insights.topNodes || [], {{ emptyText: "There are not enough nodes yet to identify key pages." }})}}
        ${{renderInsightNodeList("Bridge Pages", insights.bridgeNodes || [], {{ emptyText: "No clear bridge pages yet." }})}}
        ${{renderInsightNodeList("Pages That Need Links", insights.isolatedNodes || [], {{ emptyText: "There are no isolated or weakly connected pages right now." }})}}
        ${{renderSuggestionList(insights.suggestedLinks || [])}}
      `;
    }}

    function renderDetail(node) {{
      if (!node) {{
        detailPanel.className = "empty";
        detailPanel.textContent = "Click a node to inspect its summary, sources, status, and page path.";
        return;
      }}

      detailPanel.className = "";
      const viewerHref = "../viewer/index.html#page=" + encodeURIComponent(node.path || node.id);
      const homeHref = "../index.html";
      const sources = (node.sources && node.sources.length)
        ? node.sources.map((item) => escapeHtml(item)).join("<br>")
        : "n/a";
      const aliases = (node.aliases && node.aliases.length)
        ? node.aliases.map((item) => escapeHtml(item)).join(", ")
        : "n/a";
      const edgeStats = edgeStatsForNode(node.id);
      const edgeStatsHtml = `
        <div class="detail-stats">
          ${{
            Object.entries(edgeStats)
              .sort((left, right) => String(left[0]).localeCompare(String(right[0])))
              .map(([name, count]) => `<div class="detail-stat-row"><span>${{escapeHtml(name)}}</span><strong>${{escapeHtml(count)}}</strong></div>`)
              .join("")
          }}
        </div>
      `;

      detailPanel.innerHTML = `
        <h3 style="margin-top:0;">${{escapeHtml(node.label)}}</h3>
        <div>
          <span class="chip">${{escapeHtml(node.type || "page")}}</span>
          <span class="chip">${{escapeHtml(node.nodeType || "page")}}</span>
          <span class="chip">${{escapeHtml(node.confidence || "n/a")}}</span>
          <span class="chip">${{escapeHtml(node.status || "n/a")}}</span>
          <span class="chip">${{escapeHtml(node.maturity || "n/a")}}</span>
        </div>
        <div class="detail-row"><strong>Path</strong>${{escapeHtml(node.path || node.id)}}</div>
        <div class="detail-row"><strong>Updated</strong>${{escapeHtml(node.updated || "n/a")}}</div>
        <div class="detail-row"><strong>Summary</strong>${{escapeHtml(node.summary || "(no summary)")}}</div>
        <div class="detail-row"><strong>Aliases</strong>${{aliases}}</div>
        <div class="detail-row"><strong>Relation Stats</strong>${{edgeStatsHtml}}</div>
        <div class="detail-row"><strong>Sources</strong><div class="sources">${{sources}}</div></div>
        <a class="action" href="${{viewerHref}}" target="_blank" rel="noopener">Open Local Viewer</a>
        <a class="action" href="${{homeHref}}" target="_blank" rel="noopener">Open Workspace Home</a>
      `;
    }}

    function selectNode(nodeId, options = {{}}) {{
      activeNodeId = nodeMap.has(nodeId) ? nodeId : "";
      activeSuggestionKey = options.keepSuggestion ? activeSuggestionKey : "";
      if (options.updateHash !== false) {{
        updateHash(activeNodeId);
      }}
      renderInsights();
      renderDetail(activeNodeId ? nodeMap.get(activeNodeId) : null);
      renderGraph();
      centerNodeInStage(activeNodeId);
    }}

    function selectSuggestedLink(sourceId, targetId) {{
      activeSuggestionKey = suggestionKey(sourceId, targetId);
      activeNodeId = nodeMap.has(sourceId) ? sourceId : "";
      updateHash(activeNodeId);
      renderInsights();
      renderDetail(activeNodeId ? nodeMap.get(activeNodeId) : null);
      renderGraph();
      centerNodeInStage(activeNodeId);
    }}

    function renderGraph() {{
      svg.innerHTML = "";
      const visibleIds = visibleNodeIds();
      const enabledTypes = enabledEdgeTypes();
      const suggestedNodes = activeSuggestionNodeIds();

      (view.edges || []).forEach((edge) => {{
        if (!enabledTypes.has(edge.type || "")) return;
        if (!visibleIds.has(edge.source) || !visibleIds.has(edge.target)) return;
        const sourceNode = nodeMap.get(edge.source);
        const targetNode = nodeMap.get(edge.target);
        if (!sourceNode || !targetNode) return;

        const related = activeNodeId && (edge.source === activeNodeId || edge.target === activeNodeId);
        const edgeStyle = edgeStyles[edge.type] || edgeStyles.links_to || {{
          stroke: "rgba(255,255,255,0.28)",
          highlight: "rgba(255,255,255,0.82)",
          dash: "",
        }};
        const line = createSvgEl("line", {{
          x1: sourceNode.x,
          y1: sourceNode.y,
          x2: targetNode.x,
          y2: targetNode.y,
          stroke: related ? edgeStyle.highlight : edgeStyle.stroke,
          "stroke-width": related ? 2.4 : 1.35,
          opacity: activeNodeId ? (related ? 1 : 0.42) : 0.92,
        }});
        if (edgeStyle.dash) {{
          line.setAttribute("stroke-dasharray", edgeStyle.dash);
        }}
        line.setAttribute("data-edge-type", edge.type || "");
        svg.appendChild(line);
      }});

      if (suggestedNodes.size === 2) {{
        const [sourceId, targetId] = Array.from(suggestedNodes.values());
        if (visibleIds.has(sourceId) && visibleIds.has(targetId)) {{
          const sourceNode = nodeMap.get(sourceId);
          const targetNode = nodeMap.get(targetId);
          if (sourceNode && targetNode) {{
            const suggestionLine = createSvgEl("line", {{
              x1: sourceNode.x,
              y1: sourceNode.y,
              x2: targetNode.x,
              y2: targetNode.y,
              stroke: "rgba(138,180,255,0.96)",
              "stroke-width": 2.6,
              opacity: 0.96,
            }});
            suggestionLine.setAttribute("stroke-dasharray", "10 6");
            suggestionLine.setAttribute("data-suggested-link", activeSuggestionKey);
            svg.appendChild(suggestionLine);
          }}
        }}
      }}

      (view.nodes || []).forEach((node) => {{
        if (!visibleIds.has(node.id)) return;
        const isNeighbor = activeNodeId && (neighbors.get(activeNodeId) || new Set()).has(node.id);
        const isActive = activeNodeId === node.id;
        const isSuggested = suggestedNodes.has(node.id);
        const faded = activeNodeId && !isActive && !isNeighbor && !isSuggested;

        const group = createSvgEl("g", {{
          transform: `translate(${{node.x}}, ${{node.y}})`,
          style: "cursor:pointer;",
        }});
        const circle = createSvgEl("circle", {{
          r: isActive ? 16 : isSuggested ? 14 : 12,
          fill: node.color || "#60a5fa",
          stroke: isActive ? "#ffffff" : isSuggested ? "#8ab4ff" : "rgba(255,255,255,0.25)",
          "stroke-width": isActive ? 2.4 : isSuggested ? 2 : 1.2,
          opacity: faded ? 0.62 : 1,
        }});
        const label = createSvgEl("text", {{
          x: 18,
          y: 5,
          fill: "#edf2ff",
          "font-size": 12,
          opacity: faded ? 0.7 : 0.94,
        }});
        label.textContent = node.label;

        group.appendChild(circle);
        group.appendChild(label);
        group.addEventListener("click", () => {{
          selectNode(node.id);
        }});
        svg.appendChild(group);
      }});
    }}

    function resetView() {{
      activeNodeId = "";
      activeSuggestionKey = "";
      updateHash("");
      renderInsights();
      renderDetail(null);
      renderGraph();
    }}

    insightsPanel.addEventListener("click", (event) => {{
      const target = event.target.closest("button");
      if (!target) return;
      const nodeId = target.getAttribute("data-insight-node") || "";
      if (nodeId) {{
        selectNode(nodeId, {{ updateHash: true, keepSuggestion: false }});
        return;
      }}
      const sourceId = target.getAttribute("data-suggestion-source") || "";
      const targetId = target.getAttribute("data-suggestion-target") || "";
      if (sourceId && targetId) {{
        selectSuggestedLink(sourceId, targetId);
      }}
    }});

    searchEl.addEventListener("input", () => {{
      renderInsights();
      renderGraph();
    }});
    scopeFilterEl.addEventListener("change", () => {{
      renderInsights();
      renderGraph();
    }});
    typeFilterEl.addEventListener("change", () => {{
      syncFocusButtons();
      renderInsights();
      renderGraph();
    }});
    statusFilterEl.addEventListener("change", () => {{
      renderInsights();
      renderGraph();
    }});
    confidenceFilterEl.addEventListener("change", () => {{
      renderInsights();
      renderGraph();
    }});
    edgeTypeInputs.forEach((input) => input.addEventListener("change", () => {{
      renderInsights();
      renderGraph();
    }}));
    focusButtons.forEach((button) => button.addEventListener("click", () => {{
      typeFilterEl.value = button.getAttribute("data-focus-type") || "";
      syncFocusButtons();
      renderInsights();
      renderGraph();
    }}));
    modeButtons.forEach((button) => button.addEventListener("click", () => {{
      const nextView = button.getAttribute("data-view-mode") || "knowledge";
      if (!allViews[nextView]) return;
      activeViewName = nextView;
      activeSuggestionKey = "";
      refreshViewState();
      renderInsights();
      renderDetail(activeNodeId ? nodeMap.get(activeNodeId) : null);
      renderGraph();
    }}));
    resetBtn.addEventListener("click", resetView);
    window.addEventListener("hashchange", () => {{
      const nextNodeId = readHashNodeId();
      selectNode(nextNodeId, {{ updateHash: false }});
    }});

    const initialNodeId = readHashNodeId();
    refreshViewState();
    activeNodeId = nodeMap.has(initialNodeId) ? initialNodeId : "";
    syncFocusButtons();
    renderInsights();
    renderDetail(activeNodeId ? nodeMap.get(activeNodeId) : null);
    renderGraph();
    centerNodeInStage(activeNodeId);
  </script>
</body>
</html>
"""


def build_document_view(
    root: Path,
    records: list[dict[str, object]],
) -> tuple[list[dict[str, object]], list[dict[str, str]], dict[str, object]]:
    page_ids = {Path(record["page"]).resolve(): str(record["id"]) for record in records}
    nodes: dict[str, dict[str, object]] = {}
    edges: list[dict[str, str]] = []
    seen_edges: set[tuple[str, str, str]] = set()

    for record in records:
        page = Path(record["page"])
        meta = record["meta"]
        assert isinstance(meta, dict)
        body = str(record["body"])
        page_id = str(record["id"])
        page_type = str(record["page_type"])
        add_node(nodes, node_payload_for_page(root, page, meta, body, page_type))

        for source in normalize_sources(meta):
            source_path = (root / source).resolve()
            source_id = source_path.relative_to(root).as_posix() if source_path.is_relative_to(root) else source
            source_type = node_type_for_path(source_id)
            add_node(nodes, placeholder_node(source_id, Path(source_id).stem, source_type))
            edge_type = "cites" if source_type == "raw" else "includes" if page_type == "topic" else "references"
            add_edge(edges, seen_edges, page_id, source_id, edge_type)

        for link in markdown_links(body):
            if is_external_link(link):
                continue
            target = (page.parent / link).resolve()
            target_id = page_ids.get(target)
            if target_id:
                add_edge(edges, seen_edges, page_id, target_id, "links_to")

    graph_nodes = sorted(nodes.values(), key=lambda node: str(node["id"]))
    graph_edges = sorted(edges, key=lambda edge: (edge["source"], edge["type"], edge["target"]))
    insights = compute_graph_insights(graph_nodes, graph_edges, excluded_types={"raw", "file"})
    return graph_nodes, graph_edges, insights


def build_knowledge_view(
    root: Path,
    records: list[dict[str, object]],
    lookup: dict[str, str],
) -> tuple[list[dict[str, object]], list[dict[str, str]], dict[str, object]]:
    nodes: dict[str, dict[str, object]] = {}
    edges: list[dict[str, str]] = []
    seen_edges: set[tuple[str, str, str]] = set()

    for record in records:
        page = Path(record["page"])
        meta = record["meta"]
        assert isinstance(meta, dict)
        body = str(record["body"])
        raw_text = str(record["raw_text"])
        page_id = str(record["id"])
        page_type = str(record["page_type"])
        page_node = node_payload_for_page(root, page, meta, body, page_type)
        add_node(nodes, page_node)

        for source in normalize_sources(meta):
            target_id = resolve_page_target(root, page, source, lookup)
            if target_id:
                add_edge(edges, seen_edges, page_id, target_id, "about")

        for link in markdown_links(body):
            if is_external_link(link):
                continue
            target_id = resolve_page_target(root, page, link, lookup)
            if target_id:
                add_edge(edges, seen_edges, page_id, target_id, "related_to")

        for entity_label in normalize_str_list(meta.get("entities", [])):
            target_id = resolve_page_target(root, page, entity_label, lookup)
            if target_id:
                add_edge(edges, seen_edges, page_id, target_id, "about")
                continue
            entity_node = synthetic_entity_node(entity_label)
            add_node(nodes, entity_node)
            add_edge(edges, seen_edges, page_id, str(entity_node["id"]), "about")

        relation_specs = [
            *({"type": "belongs_to", "target": item} for item in normalize_str_list(meta.get("topics", []))),
            *({"type": "about", "target": item} for item in normalize_str_list(meta.get("concepts", []))),
            *graph_relation_items(meta),
            *parse_frontmatter_graph_relations_block(raw_text),
            *extract_connection_relations(body),
        ]
        for item in relation_specs:
            relation_type = str(item["type"])
            target_id = resolve_page_target(root, page, item["target"], lookup)
            if target_id:
                add_edge(edges, seen_edges, page_id, target_id, relation_type)

        structured_claims = [*parse_frontmatter_claims_block(raw_text), *extract_claims(meta, body)]
        deduped_claims: list[dict[str, object]] = []
        seen_claims: set[str] = set()
        for claim in structured_claims:
            claim_text = str(claim.get("text") or "").strip()
            key = claim_text.casefold()
            if not claim_text or key in seen_claims:
                continue
            seen_claims.add(key)
            deduped_claims.append(claim)

        for index, claim in enumerate(deduped_claims, start=1):
            claim_text = str(claim.get("text") or "").strip()
            if not claim_text:
                continue
            claim_id = f"claim:{page_id}#{index}"
            claim_node = {
                "id": claim_id,
                "label": claim_text,
                "type": "claim",
                "nodeType": "claim",
                "pageType": "claim",
                "summary": claim_text,
                "confidence": str(claim.get("confidence") or page_node.get("confidence") or "").strip(),
                "status": str(page_node.get("status") or "").strip(),
                "updated": str(page_node.get("updated") or "").strip(),
                "path": page_id,
                "sources": [str(item) for item in page_node.get("sources", [])],
                "topics": [str(item) for item in page_node.get("topics", [])],
                "entities": [],
                "concepts": [],
                "aliases": [],
                "maturity": "draft",
            }
            add_node(nodes, claim_node)
            add_edge(edges, seen_edges, page_id, claim_id, "asserts")
            for target in normalize_str_list(claim.get("supports", [])):
                target_id = resolve_page_target(root, page, target, lookup)
                if target_id:
                    add_edge(edges, seen_edges, claim_id, target_id, "supports")
            for target in normalize_str_list(claim.get("contradicts", [])):
                target_id = resolve_page_target(root, page, target, lookup)
                if target_id:
                    add_edge(edges, seen_edges, claim_id, target_id, "contradicts")

    graph_nodes = sorted(nodes.values(), key=lambda node: str(node["id"]))
    graph_edges = sorted(edges, key=lambda edge: (edge["source"], edge["type"], edge["target"]))
    insights = compute_graph_insights(graph_nodes, graph_edges, excluded_types={"raw", "file", "claim"})
    return graph_nodes, graph_edges, insights


def build_suggested_view(
    knowledge_nodes: list[dict[str, object]],
    knowledge_edges: list[dict[str, str]],
    knowledge_insights: dict[str, object],
) -> tuple[list[dict[str, object]], list[dict[str, str]], dict[str, object]]:
    page_nodes = [
        node for node in knowledge_nodes
        if str(node.get("type") or "page") not in {"raw", "file", "claim"}
    ]
    page_node_ids = {str(node["id"]) for node in page_nodes}
    page_edges = [
        edge for edge in knowledge_edges
        if str(edge.get("source") or "") in page_node_ids and str(edge.get("target") or "") in page_node_ids
    ]
    metrics = node_metrics(page_nodes, page_edges)
    suggestions = compute_link_suggestions(
        page_nodes,
        metrics,
        page_edges,
        excluded_types={"raw", "file", "claim"},
    )
    suggested_edges: list[dict[str, str]] = []
    seen_edges: set[tuple[str, str, str]] = set()
    for item in suggestions:
        edge_key = (str(item["source"]), str(item["target"]), "suggests_related_to")
        if edge_key in seen_edges:
            continue
        seen_edges.add(edge_key)
        suggested_edges.append({
            "source": str(item["source"]),
            "target": str(item["target"]),
            "type": "suggests_related_to",
            "relation": "suggests_related_to",
            "score": str(item["score"]),
        })
    insights = dict(knowledge_insights)
    insights["suggestedLinks"] = suggestions
    insights["summary"] = (
        f"There are {len(suggestions)} high-confidence candidate content relations that could become explicit graph links."
        if suggestions
        else "There are no new high-confidence candidate content relations right now."
    )
    return page_nodes, suggested_edges, insights


def markdown_lines_for_graph(nodes: list[dict[str, object]], edges: list[dict[str, str]], insights: dict[str, object]) -> list[str]:
    lines = [
        "# Knowledge Graph",
        "",
        f"- Nodes: {len(nodes)}",
        f"- Edges: {len(edges)}",
        f"- Summary: {insights['summary']}",
        "",
        "## Key Pages",
    ]
    lines.extend(
        f"- {item['title']} ({item['type']}) | score={item['score']} | {item['reason']}"
        for item in insights["topNodes"]
    )
    lines.extend(["", "## Suggested Links"])
    if insights["suggestedLinks"]:
        lines.extend(
            f"- {item['source']} <-> {item['target']} | score={item['score']} | {', '.join(item['reasons'])}"
            for item in insights["suggestedLinks"]
        )
    else:
        lines.append("- No suggested links")
    lines.extend(["", "## Nodes"])
    lines.extend(f"- {node['type']}: {node['label']} ({node['id']})" for node in nodes)
    lines.extend(["", "## Edges"])
    lines.extend(f"- {edge['source']} --{edge['type']}--> {edge['target']}" for edge in edges)
    return lines


def main() -> int:
    parser = argparse.ArgumentParser(description="Build graph data from wiki pages.")
    parser.add_argument("--root", default=".", help="Wiki root path")
    args = parser.parse_args()

    root = find_repo_root(Path(args.root))
    pages = collect_wiki_pages(root)
    records: list[dict[str, object]] = []
    for page in pages:
        raw_text = read_text(page)
        meta, body = parse_frontmatter(raw_text)
        page_id = page.relative_to(root).as_posix()
        page_type = str(meta.get("type") or page.parent.name[:-1])
        records.append({
            "page": page,
            "id": page_id,
            "title": str(meta.get("title") or page.stem),
            "page_type": page_type,
            "meta": meta,
            "body": body,
            "raw_text": raw_text,
        })

    active_records = [record for record in records if not is_merged_entity_record(record)]
    lookup, _node_map = build_page_lookups(records)
    document_nodes, document_edges, document_insights = build_document_view(root, active_records)
    knowledge_nodes, knowledge_edges, knowledge_insights = build_knowledge_view(root, active_records, lookup)
    suggested_nodes, suggested_edges, suggested_insights = build_suggested_view(
        knowledge_nodes,
        knowledge_edges,
        knowledge_insights,
    )
    legacy_nodes = [
        node for node in knowledge_nodes
        if str(node.get("type") or "page") != "claim"
    ]
    legacy_node_ids = {str(node["id"]) for node in legacy_nodes}
    legacy_edges = [
        edge for edge in knowledge_edges
        if str(edge.get("source") or "") in legacy_node_ids and str(edge.get("target") or "") in legacy_node_ids
    ]
    legacy_insights = compute_graph_insights(legacy_nodes, legacy_edges, excluded_types={"raw", "file", "claim"})
    graph = {
        "generated_at": today_str(),
        "schema_version": "2",
        "default_view": "knowledge",
        "catalog": {
            "pageCount": len(legacy_nodes),
            "claimCount": len([node for node in knowledge_nodes if str(node.get("type") or "") == "claim"]),
            "nodeCount": len(knowledge_nodes),
            "edgeCount": len(knowledge_edges),
        },
        "nodes": legacy_nodes,
        "edges": legacy_edges,
        "insights": legacy_insights,
        "views": {
            "document": {
                "nodes": document_nodes,
                "edges": document_edges,
                "insights": document_insights,
            },
            "knowledge": {
                "nodes": knowledge_nodes,
                "edges": knowledge_edges,
                "insights": knowledge_insights,
            },
            "suggested": {
                "nodes": suggested_nodes,
                "edges": suggested_edges,
                "insights": suggested_insights,
            },
        },
    }
    graph_dir = root / "output" / "graph"
    graph_json_path = graph_dir / "graph.json"
    graph_md_path = graph_dir / "graph.md"
    graph_html_path = graph_dir / "index.html"
    write_text(graph_json_path, json.dumps(graph, ensure_ascii=False, indent=2))

    write_text(graph_md_path, "\n".join(markdown_lines_for_graph(legacy_nodes, legacy_edges, legacy_insights)))
    write_text(graph_html_path, render_graph_html(html_payload(root, graph)))
    output_home = write_output_home(root)

    append_log(root, f"[{today_str()}] graph | {len(knowledge_nodes)} nodes, {len(knowledge_edges)} edges", [
        "- data: output/graph/graph.json",
        "- summary: output/graph/graph.md",
        "- viewer: output/graph/index.html",
        "- hub: output/index.html",
    ])
    print(f"Built graph with {len(knowledge_nodes)} nodes and {len(knowledge_edges)} edges")
    print("Graph data: output/graph/graph.json")
    print("Graph summary: output/graph/graph.md")
    print("Graph viewer: output/graph/index.html")
    print(f"Graph viewer URI: {file_uri(graph_html_path)}")
    print("Output hub: output/index.html")
    print(f"Output hub URI: {file_uri(output_home)}")
    print_output_serve_hint(root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
