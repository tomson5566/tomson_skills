from __future__ import annotations

"""
ThinkWiki Module: workspace_status

Purpose:
- Compute reusable workspace snapshot data for status and health reporting.

Usage:
- Imported by status-oriented scripts; not intended for direct end-user execution.
- Run `python scripts/<script> --help` for direct CLI details when the file exposes its own arguments.
"""


import json
from datetime import datetime
from pathlib import Path

from utils import REQUIRED_FIELDS, ambiguous_entity_merge_candidates, collect_inbox_items, collect_wiki_pages, parse_frontmatter, read_text

REQUIRED_WORKSPACE_PATHS = [
    ".wiki-schema.md",
    "index.md",
    "log.md",
    "overview.md",
    "purpose.md",
    "raw",
    "raw/inbox",
    "normalized",
    "normalized/inbox",
    "wiki",
    "output",
    "output/inbox",
    "output/viewer",
    "output/graph",
]


def _load_json(path: Path) -> tuple[dict[str, object], str | None]:
    if not path.exists():
        return {}, "missing"
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except (json.JSONDecodeError, OSError) as exc:
        return {}, str(exc)


def _format_timestamp(timestamp: float | None) -> str:
    if timestamp is None or timestamp <= 0:
        return ""
    return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M")


def _mtime(path: Path) -> float | None:
    try:
        return path.stat().st_mtime if path.exists() else None
    except OSError:
        return None


def _max_mtime(paths: list[Path]) -> float | None:
    values = [value for value in (_mtime(path) for path in paths) if value is not None]
    return max(values) if values else None


def _workspace_title(root: Path) -> str:
    for line in read_text(root / "index.md").splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            title = stripped[2:].strip()
            if title in {"Knowledge Base Index", "Wiki Index"}:
                return root.name
            return title
    return root.name


def _page_snapshot(root: Path) -> dict[str, object]:
    pages = collect_wiki_pages(root)
    counts: dict[str, int] = {}
    invalid_pages: list[dict[str, object]] = []
    for page in pages:
        meta, _body = parse_frontmatter(read_text(page))
        page_type = str(meta.get("type", "") or page.parent.name[:-1] or "page")
        counts[page_type] = counts.get(page_type, 0) + 1
        missing_fields: list[str] = []
        for field in REQUIRED_FIELDS:
            if field not in meta:
                missing_fields.append(field)
                continue
            value = meta.get(field)
            if value is None:
                missing_fields.append(field)
            elif isinstance(value, list) and not value:
                missing_fields.append(field)
            elif isinstance(value, str) and not value.strip():
                missing_fields.append(field)
        if missing_fields:
            invalid_pages.append({
                "path": page.relative_to(root).as_posix(),
                "missing": missing_fields,
            })
    return {
        "total": len(pages),
        "counts": counts,
        "latest_mtime": _max_mtime(pages),
        "invalid_pages": invalid_pages,
    }


def _inbox_snapshot(root: Path) -> dict[str, object]:
    inbox_dir = root / "normalized" / "inbox"
    markdown_paths = sorted(inbox_dir.glob("*.md")) if inbox_dir.exists() else []
    metadata_paths = sorted(inbox_dir.glob("*.json")) if inbox_dir.exists() else []
    quality_counts = {"ready": 0, "review": 0, "weak": 0}
    for item in collect_inbox_items(root):
        quality = str(item.get("quality_status", "") or "")
        if quality in quality_counts:
            quality_counts[quality] += 1
    metadata_errors: list[str] = []
    for metadata_path in metadata_paths:
        payload, error = _load_json(metadata_path)
        companion_note = metadata_path.with_suffix(".md")
        if error:
            metadata_errors.append(f"[invalid-inbox-metadata] {metadata_path.relative_to(root).as_posix()} ({error})")
            continue
        if not companion_note.exists():
            metadata_errors.append(f"[orphan-inbox-metadata] {metadata_path.relative_to(root).as_posix()} has no matching markdown item")
        kind = str(payload.get("kind", "") or "")
        if kind == "web":
            missing = [
                field
                for field in ("title", "url", "adapter")
                if not str(payload.get(field, "") or "").strip()
            ]
            if missing:
                metadata_errors.append(
                    "[incomplete-web-metadata] {} is missing {}".format(
                        metadata_path.relative_to(root).as_posix(),
                        ", ".join(missing),
                    )
                )
    for markdown_path in markdown_paths:
        text = read_text(markdown_path).strip()
        if not text:
            metadata_errors.append(f"[empty-inbox-item] {markdown_path.relative_to(root).as_posix()} has no content")
    return {
        "total": len(markdown_paths),
        "quality_counts": quality_counts,
        "latest_mtime": _max_mtime(markdown_paths + metadata_paths),
        "metadata_errors": metadata_errors,
    }


def _output_snapshot(root: Path) -> dict[str, object]:
    output_dir = root / "output"
    viewer_html = output_dir / "viewer" / "index.html"
    viewer_json = output_dir / "viewer" / "viewer.json"
    graph_html = output_dir / "graph" / "index.html"
    graph_json = output_dir / "graph" / "graph.json"
    graph_report_json = output_dir / "graph" / "report.json"
    graph_report_md = output_dir / "graph" / "report.md"
    graph_report_html = output_dir / "graph" / "report.html"
    inbox_html = output_dir / "inbox" / "index.html"
    hub_html = output_dir / "index.html"

    viewer_payload, viewer_error = _load_json(viewer_json)
    graph_payload, graph_error = _load_json(graph_json)
    graph_report_payload, graph_report_error = _load_json(graph_report_json)
    insights = graph_payload.get("insights", {}) if isinstance(graph_payload.get("insights"), dict) else {}
    graph_views = graph_payload.get("views", {}) if isinstance(graph_payload.get("views"), dict) else {}
    knowledge_view = graph_views.get("knowledge", {}) if isinstance(graph_views.get("knowledge"), dict) else {}
    knowledge_nodes = knowledge_view.get("nodes", []) if isinstance(knowledge_view.get("nodes"), list) else []
    knowledge_edges = knowledge_view.get("edges", []) if isinstance(knowledge_view.get("edges"), list) else []
    suggested_view = graph_views.get("suggested", {}) if isinstance(graph_views.get("suggested"), dict) else {}
    suggested_edges = suggested_view.get("edges", []) if isinstance(suggested_view.get("edges"), list) else []
    report_stats = graph_report_payload.get("stats", {}) if isinstance(graph_report_payload.get("stats"), dict) else {}
    entity_nodes = [
        node for node in knowledge_nodes
        if isinstance(node, dict) and str(node.get("type", "") or "") == "entity"
    ]
    ambiguous_merge_candidates, ambiguous_entity_count = ambiguous_entity_merge_candidates(entity_nodes)

    return {
        "hub": {
            "exists": hub_html.exists(),
            "mtime": _mtime(hub_html),
        },
        "viewer": {
            "html_exists": viewer_html.exists(),
            "json_exists": viewer_json.exists(),
            "mtime": _mtime(viewer_html),
            "generated_at": str(viewer_payload.get("generatedAt", "") or ""),
            "page_count": int(viewer_payload.get("pageCount", 0) or 0),
            "error": viewer_error,
        },
        "graph": {
            "html_exists": graph_html.exists(),
            "json_exists": graph_json.exists(),
            "mtime": _mtime(graph_html),
            "generated_at": str(graph_payload.get("generated_at", "") or ""),
            "schema_version": str(graph_payload.get("schema_version", "") or ""),
            "default_view": str(graph_payload.get("default_view", "") or ""),
            "node_count": len(graph_payload.get("nodes", [])) if isinstance(graph_payload.get("nodes"), list) else 0,
            "edge_count": len(graph_payload.get("edges", [])) if isinstance(graph_payload.get("edges"), list) else 0,
            "suggested_links": len(insights.get("suggestedLinks", [])) if isinstance(insights.get("suggestedLinks"), list) else 0,
            "knowledge_node_count": len(knowledge_nodes),
            "knowledge_edge_count": len(knowledge_edges),
            "claim_count": sum(1 for node in knowledge_nodes if str(node.get("type", "") or "") == "claim"),
            "entity_count": len(entity_nodes),
            "aliased_entity_count": sum(
                1
                for node in entity_nodes
                if isinstance(node.get("aliases"), list) and any(str(item).strip() for item in node.get("aliases", []))
            ),
            "alias_count": sum(
                len([str(item).strip() for item in node.get("aliases", []) if str(item).strip()])
                for node in entity_nodes
                if isinstance(node.get("aliases"), list)
            ),
            "ambiguous_alias_group_count": len(ambiguous_merge_candidates),
            "ambiguous_entity_count": ambiguous_entity_count,
            "suggested_edge_count": len(suggested_edges),
            "report_exists": graph_report_json.exists(),
            "report_markdown_exists": graph_report_md.exists(),
            "report_html_exists": graph_report_html.exists(),
            "report_mtime": _mtime(graph_report_html) or _mtime(graph_report_json) or _mtime(graph_report_md),
            "report_generated_at": str(graph_report_payload.get("generated_at", "") or ""),
            "report_summary": str(graph_report_payload.get("summary", "") or ""),
            "report_top_actions": len(graph_report_payload.get("topActions", [])) if isinstance(graph_report_payload.get("topActions"), list) else 0,
            "report_isolated_pages": int(report_stats.get("isolatedPageCount", 0) or 0),
            "report_weak_pages": int(report_stats.get("weakPageCount", 0) or 0),
            "report_hub_stubs": int(report_stats.get("hubStubCount", 0) or 0),
            "report_fragile_bridges": int(report_stats.get("fragileBridgeCount", 0) or 0),
            "report_isolated_clusters": int(report_stats.get("isolatedClusterCount", 0) or 0),
            "report_entities": int(report_stats.get("entityCount", 0) or 0),
            "report_aliased_entities": int(report_stats.get("aliasedEntityCount", 0) or 0),
            "report_aliases": int(report_stats.get("aliasCount", 0) or 0),
            "report_ambiguous_alias_groups": int(report_stats.get("ambiguousAliasGroupCount", 0) or 0),
            "report_ambiguous_entities": int(report_stats.get("ambiguousEntityCount", 0) or 0),
            "report_isolated_entities": int(report_stats.get("isolatedEntityCount", 0) or 0),
            "error": graph_error,
            "report_error": graph_report_error,
        },
        "inbox": {
            "html_exists": inbox_html.exists(),
            "mtime": _mtime(inbox_html),
        },
    }


def collect_workspace_snapshot(root: Path) -> dict[str, object]:
    pages = _page_snapshot(root)
    inbox = _inbox_snapshot(root)
    outputs = _output_snapshot(root)
    return {
        "root": str(root),
        "title": _workspace_title(root),
        "pages": pages,
        "inbox": inbox,
        "outputs": outputs,
    }


def collect_health_issues(root: Path, snapshot: dict[str, object]) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    for relative in REQUIRED_WORKSPACE_PATHS:
        if not (root / relative).exists():
            errors.append(f"[missing-workspace-asset] {relative}")

    pages = snapshot["pages"]
    assert isinstance(pages, dict)
    for record in pages.get("invalid_pages", []):
        if not isinstance(record, dict):
            continue
        path = str(record.get("path", "") or "")
        missing = record.get("missing", [])
        if path and isinstance(missing, list):
            errors.append(f"[invalid-page-frontmatter] {path} is missing {', '.join(str(item) for item in missing)}")

    inbox = snapshot["inbox"]
    assert isinstance(inbox, dict)
    for item in inbox.get("metadata_errors", []):
        warnings.append(str(item))

    outputs = snapshot["outputs"]
    assert isinstance(outputs, dict)
    viewer = outputs["viewer"]
    graph = outputs["graph"]
    inbox_output = outputs["inbox"]
    hub = outputs["hub"]
    assert isinstance(viewer, dict)
    assert isinstance(graph, dict)
    assert isinstance(inbox_output, dict)
    assert isinstance(hub, dict)

    if viewer.get("html_exists") and not viewer.get("json_exists"):
        errors.append("[viewer-metadata-missing] output/viewer/index.html exists but output/viewer/viewer.json is missing")
    if graph.get("html_exists") and not graph.get("json_exists"):
        errors.append("[graph-data-missing] output/graph/index.html exists but output/graph/graph.json is missing")
    if graph.get("json_exists") and not graph.get("report_exists"):
        warnings.append("[graph-report-missing] output/graph/graph.json exists but output/graph/report.json is missing")
    if graph.get("json_exists") and str(graph.get("schema_version", "") or "") == "2" and not int(graph.get("knowledge_node_count", 0) or 0):
        warnings.append("[knowledge-graph-empty] graph.json v2 exists but knowledge view has no nodes")
    if graph.get("report_exists") and not graph.get("report_html_exists"):
        warnings.append("[graph-report-html-missing] output/graph/report.json exists but output/graph/report.html is missing")
    if graph.get("report_exists") and str(graph.get("report_error", "") or "").strip():
        warnings.append("[invalid-graph-report] output/graph/report.json could not be read")

    latest_wiki_mtime = pages.get("latest_mtime")
    viewer_mtime = viewer.get("mtime")
    graph_mtime = graph.get("mtime")
    graph_report_mtime = graph.get("report_mtime")
    if isinstance(latest_wiki_mtime, (int, float)) and latest_wiki_mtime > 0:
        if isinstance(viewer_mtime, (int, float)) and viewer_mtime < latest_wiki_mtime:
            warnings.append("[stale-viewer-output] output/viewer/index.html is older than the latest wiki page")
        if isinstance(graph_mtime, (int, float)) and graph_mtime < latest_wiki_mtime:
            warnings.append("[stale-graph-output] output/graph/index.html is older than the latest wiki page")
        if isinstance(graph_report_mtime, (int, float)) and graph_report_mtime < latest_wiki_mtime:
            warnings.append("[stale-graph-report] output/graph/report.json is older than the latest wiki page")
        if pages.get("total", 0) and not viewer.get("html_exists"):
            warnings.append("[viewer-not-built] wiki pages exist but output/viewer/index.html has not been generated yet")
        if pages.get("total", 0) and not graph.get("html_exists"):
            warnings.append("[graph-not-built] wiki pages exist but output/graph/index.html has not been generated yet")
        if pages.get("total", 0) and graph.get("json_exists") and not graph.get("report_exists"):
            warnings.append("[graph-report-not-built] graph data exists but the graph governance report has not been generated yet")

    if (
        isinstance(graph_mtime, (int, float))
        and graph.get("json_exists")
        and isinstance(graph_report_mtime, (int, float))
        and graph_report_mtime < graph_mtime
    ):
        warnings.append("[stale-graph-report] output/graph/report.json is older than output/graph/index.html")

    latest_inbox_mtime = inbox.get("latest_mtime")
    inbox_mtime = inbox_output.get("mtime")
    if inbox.get("total", 0) and not inbox_output.get("html_exists"):
        warnings.append("[inbox-review-missing] inbox items exist but output/inbox/index.html has not been generated yet")
    if (
        isinstance(latest_inbox_mtime, (int, float))
        and latest_inbox_mtime > 0
        and isinstance(inbox_mtime, (int, float))
        and inbox_mtime < latest_inbox_mtime
    ):
        warnings.append("[stale-inbox-review] output/inbox/index.html is older than the latest inbox item")

    if hub.get("exists"):
        hub_mtime = hub.get("mtime")
        freshest_output = max(
            value
            for value in [viewer_mtime, graph_mtime, inbox_mtime]
            if isinstance(value, (int, float))
        ) if any(isinstance(value, (int, float)) for value in [viewer_mtime, graph_mtime, inbox_mtime]) else None
        if isinstance(hub_mtime, (int, float)) and isinstance(freshest_output, (int, float)) and hub_mtime < freshest_output:
            warnings.append("[stale-output-home] output/index.html is older than one of the generated output pages")

    if viewer.get("json_exists") and int(viewer.get("page_count", 0) or 0) != int(pages.get("total", 0) or 0):
        warnings.append("[viewer-page-count-mismatch] output/viewer/viewer.json pageCount does not match current wiki page count")

    return errors, warnings


def format_status_lines(snapshot: dict[str, object]) -> list[str]:
    pages = snapshot["pages"]
    inbox = snapshot["inbox"]
    outputs = snapshot["outputs"]
    assert isinstance(pages, dict)
    assert isinstance(inbox, dict)
    assert isinstance(outputs, dict)
    viewer = outputs["viewer"]
    graph = outputs["graph"]
    inbox_output = outputs["inbox"]
    hub = outputs["hub"]
    assert isinstance(viewer, dict)
    assert isinstance(graph, dict)
    assert isinstance(inbox_output, dict)
    assert isinstance(hub, dict)

    page_counts = pages.get("counts", {})
    assert isinstance(page_counts, dict)
    page_breakdown = ", ".join(
        "{}={}".format(page_type, count)
        for page_type, count in sorted((str(key), int(value)) for key, value in page_counts.items())
    ) or "none"
    quality_counts = inbox.get("quality_counts", {})
    assert isinstance(quality_counts, dict)

    lines = [
        "# ThinkWiki Status",
        "",
        f"- Root: {snapshot['root']}",
        f"- Title: {snapshot['title']}",
        f"- Pages: {pages.get('total', 0)} ({page_breakdown})",
        "- Inbox: total={total}, ready={ready}, review={review}, weak={weak}".format(
            total=int(inbox.get("total", 0) or 0),
            ready=int(quality_counts.get("ready", 0) or 0),
            review=int(quality_counts.get("review", 0) or 0),
            weak=int(quality_counts.get("weak", 0) or 0),
        ),
        "- Output Home: {state}{updated}".format(
            state="ready" if hub.get("exists") else "missing",
            updated=f" (updated {_format_timestamp(hub.get('mtime'))})" if hub.get("exists") else "",
        ),
        "- Viewer: {state}{detail}".format(
            state="ready" if viewer.get("html_exists") else "missing",
            detail=(
                " (generated {generated}, pageCount={count})".format(
                    generated=str(viewer.get("generated_at", "") or _format_timestamp(viewer.get("mtime")) or "n/a"),
                    count=int(viewer.get("page_count", 0) or 0),
                )
                if viewer.get("html_exists")
                else ""
            ),
        ),
        "- Graph: {state}{detail}".format(
            state="ready" if graph.get("html_exists") else "missing",
            detail=(
                " (generated {generated}, schema=v{schema}, defaultView={default_view}, nodes={nodes}, edges={edges}, knowledgeNodes={knowledge_nodes}, claims={claims}, entities={entities}, aliasedEntities={aliased_entities}, aliases={aliases}, ambiguousAliasGroups={ambiguous_groups}, ambiguousEntities={ambiguous_entities}, suggestedLinks={suggested})".format(
                    generated=str(graph.get("generated_at", "") or _format_timestamp(graph.get("mtime")) or "n/a"),
                    schema=str(graph.get("schema_version", "") or "1"),
                    default_view=str(graph.get("default_view", "") or "legacy"),
                    nodes=int(graph.get("node_count", 0) or 0),
                    edges=int(graph.get("edge_count", 0) or 0),
                    knowledge_nodes=int(graph.get("knowledge_node_count", 0) or 0),
                    claims=int(graph.get("claim_count", 0) or 0),
                    entities=int(graph.get("entity_count", 0) or 0),
                    aliased_entities=int(graph.get("aliased_entity_count", 0) or 0),
                    aliases=int(graph.get("alias_count", 0) or 0),
                    ambiguous_groups=int(graph.get("ambiguous_alias_group_count", 0) or 0),
                    ambiguous_entities=int(graph.get("ambiguous_entity_count", 0) or 0),
                    suggested=int(graph.get("suggested_links", 0) or 0),
                )
                if graph.get("html_exists")
                else ""
            ),
        ),
        "- Graph Report: {state}{detail}".format(
            state="ready" if graph.get("report_html_exists") else "missing",
            detail=(
                " (generated {generated}, isolatedPages={isolated}, isolatedEntities={isolated_entities}, aliasedEntities={aliased_entities}, aliases={aliases}, ambiguousAliasGroups={ambiguous_groups}, ambiguousEntities={ambiguous_entities}, hubStubs={hub_stubs}, fragileBridges={fragile}, clusters={clusters})".format(
                    generated=str(graph.get("report_generated_at", "") or _format_timestamp(graph.get("report_mtime")) or "n/a"),
                    isolated=int(graph.get("report_isolated_pages", 0) or 0),
                    isolated_entities=int(graph.get("report_isolated_entities", 0) or 0),
                    aliased_entities=int(graph.get("report_aliased_entities", 0) or 0),
                    aliases=int(graph.get("report_aliases", 0) or 0),
                    ambiguous_groups=int(graph.get("report_ambiguous_alias_groups", 0) or 0),
                    ambiguous_entities=int(graph.get("report_ambiguous_entities", 0) or 0),
                    hub_stubs=int(graph.get("report_hub_stubs", 0) or 0),
                    fragile=int(graph.get("report_fragile_bridges", 0) or 0),
                    clusters=int(graph.get("report_isolated_clusters", 0) or 0),
                )
                if graph.get("report_exists")
                else ""
            ),
        ),
        "- Inbox Review: {state}{detail}".format(
            state="ready" if inbox_output.get("html_exists") else "missing",
            detail=f" (updated {_format_timestamp(inbox_output.get('mtime'))})" if inbox_output.get("html_exists") else "",
        ),
    ]
    return lines
