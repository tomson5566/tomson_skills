from __future__ import annotations

import base64
import contextlib
import http.server
import json
import os
import subprocess
import sys
import tempfile
import textwrap
import threading
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


def runtime_python() -> str:
    candidates = [
        REPO_ROOT / ".venv" / "bin" / "python3",
        REPO_ROOT / ".venv" / "bin" / "python",
        REPO_ROOT / ".venv" / "Scripts" / "python.exe",
        REPO_ROOT / ".venv" / "Scripts" / "python",
    ]
    if os.name == "nt":
        candidates = candidates[2:] + candidates[:2]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return sys.executable


def run_script(script_name: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [runtime_python(), str(REPO_ROOT / "scripts" / script_name), *args],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )


def run_thinkwiki(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [runtime_python(), str(REPO_ROOT / "scripts" / "thinkwiki"), *args],
        cwd=REPO_ROOT,
        check=check,
        capture_output=True,
        text=True,
    )


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content).strip() + "\n", encoding="utf-8")


@contextlib.contextmanager
def serve_directory(root: Path):
    class QuietHandler(http.server.SimpleHTTPRequestHandler):
        def log_message(self, format: str, *args: object) -> None:
            return

    previous = Path.cwd()
    server = None
    thread = None
    try:
        os.chdir(root)
        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), QuietHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        host, port = server.server_address
        yield f"http://{host}:{port}"
    finally:
        if server is not None:
            server.shutdown()
            server.server_close()
        if thread is not None:
            thread.join(timeout=2)
        os.chdir(previous)


@contextlib.contextmanager
def serve_handler(handler_class: type[http.server.BaseHTTPRequestHandler]):
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler_class)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address
        yield f"http://{host}:{port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


class ThinkWikiRegressionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._previous_allow_private = os.environ.get("THINKWIKI_ALLOW_PRIVATE_URL_FETCH")
        os.environ["THINKWIKI_ALLOW_PRIVATE_URL_FETCH"] = "1"

    @classmethod
    def tearDownClass(cls) -> None:
        if cls._previous_allow_private is None:
            os.environ.pop("THINKWIKI_ALLOW_PRIVATE_URL_FETCH", None)
        else:
            os.environ["THINKWIKI_ALLOW_PRIVATE_URL_FETCH"] = cls._previous_allow_private

    def test_batch_clip_dry_run_lists_supported_directory_sources(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir) / "wiki"
            import_dir = Path(tmp_dir) / "imports"
            run_script("init_wiki.py", "--root", str(root), "--title", "Batch Clip Wiki")
            write_text(import_dir / "alpha.md", "# Alpha\n\nAlpha note.")
            write_text(import_dir / "nested" / "beta.txt", "Beta note.")
            write_text(import_dir / "ignore.png", "not supported")

            result = run_thinkwiki("batch-clip", "--root", str(root), "--source-dir", str(import_dir), "--dry-run")

            self.assertIn("ThinkWiki Batch Clip", result.stdout)
            self.assertIn("Input: source-dir", result.stdout)
            self.assertIn("Matched Items: 2", result.stdout)
            self.assertIn("alpha.md", result.stdout)
            self.assertIn("beta.txt", result.stdout)
            self.assertNotIn("ignore.png", result.stdout)
            self.assertIn("Dry run complete. No files were changed.", result.stdout)
            self.assertFalse(any((root / "normalized" / "inbox").glob("*.md")))

    def test_batch_clip_manifest_clips_mixed_items_and_refreshes_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir) / "wiki"
            import_dir = Path(tmp_dir) / "imports"
            site_root = Path(tmp_dir) / "site"
            manifest = Path(tmp_dir) / "clip-manifest.jsonl"
            run_script("init_wiki.py", "--root", str(root), "--title", "Batch Clip Wiki")
            write_text(import_dir / "alpha.md", "# Alpha\n\nAlpha note from manifest.")
            write_text(
                site_root / "article.html",
                """
                <html>
                  <head>
                    <meta property="og:site_name" content="Manifest Blog">
                    <meta name="author" content="Ada Lovelace">
                    <meta property="article:published_time" content="2026-06-21">
                  </head>
                  <body>
                    <main>
                      <h1>Manifest Article</h1>
                      <p>This article is long enough to be treated as a ready inbox capture during batch clip execution.</p>
                    </main>
                  </body>
                </html>
                """,
            )

            with serve_directory(site_root) as base_url:
                write_text(
                    manifest,
                    f"""
                    {{"source":"./imports/alpha.md","title":"Alpha Manifest"}}
                    {{"url":"{base_url}/article.html","title":"Manifest Article","mode":"wait","waitSeconds":1}}
                    {{"text":"# Quick Note\\n\\nSomething worth saving.","title":"Quick Note"}}
                    """,
                )
                result = run_thinkwiki("batch-clip", "--root", str(root), "--manifest", str(manifest))

            normalized_files = sorted((root / "normalized" / "inbox").glob("*.md"))
            metadata_files = sorted((root / "normalized" / "inbox").glob("*.json"))
            self.assertEqual(len(normalized_files), 3)
            self.assertEqual(len(metadata_files), 1)
            payload = json.loads(metadata_files[0].read_text(encoding="utf-8"))
            self.assertEqual(payload["title"], "Manifest Article")
            self.assertEqual(payload["siteName"], "Manifest Blog")
            self.assertEqual(payload["author"], "Ada Lovelace")
            self.assertEqual(payload["captureMode"], "wait")
            self.assertIn("Matched Items: 3", result.stdout)
            self.assertIn("Clipped: 3", result.stdout)
            self.assertIn("Manifest Article", result.stdout)
            self.assertIn("Quick Note", result.stdout)
            self.assertIn("Inbox review: output/inbox/index.html", result.stdout)
            self.assertIn("Output hub: output/index.html", result.stdout)
            self.assertIn("batch-ingest --root", result.stdout)
            self.assertTrue((root / "output" / "inbox" / "index.html").exists())
            self.assertTrue((root / "output" / "index.html").exists())
            log_text = (root / "log.md").read_text(encoding="utf-8")
            self.assertIn("batch-clip | manifest", log_text)
            self.assertIn("normalized/inbox/", log_text)

    def test_batch_ingest_dry_run_only_lists_ready_items(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir) / "wiki"
            run_script("init_wiki.py", "--root", str(root), "--title", "Batch Wiki")
            write_text(
                root / "normalized" / "inbox" / "2026-06-21-ready-item.md",
                """
                # Ready Item

                This ready inbox item has enough body text to be safely promoted into the wiki during batch ingest.
                """,
            )
            write_text(
                root / "normalized" / "inbox" / "2026-06-21-ready-item.json",
                json.dumps({
                    "kind": "web",
                    "adapter": "generic",
                    "title": "Ready Item",
                    "siteName": "Example Blog",
                    "author": "Ada Lovelace",
                    "publishDate": "2026-06-21",
                    "url": "https://example.com/ready",
                }, ensure_ascii=False, indent=2),
            )
            write_text(
                root / "normalized" / "inbox" / "2026-06-21-weak-item.md",
                """
                # Weak Item

                short
                """,
            )
            write_text(
                root / "normalized" / "inbox" / "2026-06-21-weak-item.json",
                json.dumps({
                    "kind": "web",
                    "adapter": "generic",
                    "title": "Weak Item",
                    "url": "",
                }, ensure_ascii=False, indent=2),
            )

            result = run_thinkwiki("batch-ingest", "--root", str(root), "--dry-run")

            self.assertIn("ThinkWiki Batch Ingest", result.stdout)
            self.assertIn("Quality Filter: ready", result.stdout)
            self.assertIn("Matched Items: 1", result.stdout)
            self.assertIn("Ready Item", result.stdout)
            self.assertNotIn("Weak Item", result.stdout)
            self.assertIn("Dry run complete. No files were changed.", result.stdout)
            self.assertTrue((root / "normalized" / "inbox" / "2026-06-21-ready-item.md").exists())
            self.assertFalse(any((root / "wiki" / "sources").glob("*.md")))

    def test_batch_ingest_respects_limit_and_clears_processed_inbox_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir) / "wiki"
            run_script("init_wiki.py", "--root", str(root), "--title", "Batch Wiki")

            old_md = root / "normalized" / "inbox" / "2026-06-21-old-ready.md"
            old_json = root / "normalized" / "inbox" / "2026-06-21-old-ready.json"
            old_raw = root / "raw" / "inbox" / "2026-06-21-old-ready.html"
            write_text(
                old_md,
                """
                # Old Ready

                This older ready inbox item should remain queued when batch ingest is limited to one item.
                """,
            )
            write_text(
                old_json,
                json.dumps({
                    "kind": "web",
                    "adapter": "generic",
                    "title": "Old Ready",
                    "siteName": "Example Blog",
                    "author": "Grace Hopper",
                    "publishDate": "2026-06-21",
                    "url": "https://example.com/old-ready",
                }, ensure_ascii=False, indent=2),
            )
            write_text(old_raw, "<html><body>old ready</body></html>")

            new_md = root / "normalized" / "inbox" / "2026-06-21-new-ready.md"
            new_json = root / "normalized" / "inbox" / "2026-06-21-new-ready.json"
            new_raw = root / "raw" / "inbox" / "2026-06-21-new-ready.html"
            new_media_dir = root / "normalized" / "assets" / "inbox" / "2026-06-21-new-ready"
            write_text(
                new_md,
                """
                # New Ready

                This newer ready inbox item has the richest metadata and should be the one batch ingest processes first.
                """,
            )
            write_text(
                new_json,
                json.dumps({
                    "kind": "web",
                    "adapter": "generic",
                    "title": "New Ready",
                    "siteName": "Example Blog",
                    "author": "Ada Lovelace",
                    "publishDate": "2026-06-21",
                    "url": "https://example.com/new-ready",
                    "mediaDir": "normalized/assets/inbox/2026-06-21-new-ready",
                }, ensure_ascii=False, indent=2),
            )
            write_text(new_raw, "<html><body>new ready</body></html>")
            write_text(new_media_dir / "pixel.png", "image")

            os.utime(old_md, (1000, 1000))
            os.utime(old_json, (1000, 1000))
            os.utime(old_raw, (1000, 1000))
            os.utime(new_md, (2000, 2000))
            os.utime(new_json, (2000, 2000))
            os.utime(new_raw, (2000, 2000))

            result = run_thinkwiki("batch-ingest", "--root", str(root), "--limit", "1")

            self.assertIn("Ingested: 1", result.stdout)
            self.assertIn("Cleared Inbox Artifacts: 4", result.stdout)
            self.assertIn("New Ready -> wiki/sources/new-ready.md", result.stdout)
            self.assertIn("Output hub: output/index.html", result.stdout)
            self.assertIn("Next: run `python scripts/thinkwiki viewer --root", result.stdout)
            self.assertTrue((root / "wiki" / "sources" / "new-ready.md").exists())
            self.assertFalse(new_md.exists())
            self.assertFalse(new_json.exists())
            self.assertFalse(new_raw.exists())
            self.assertFalse(new_media_dir.exists())
            self.assertTrue(old_md.exists())
            self.assertTrue(old_json.exists())
            self.assertTrue(old_raw.exists())
            self.assertTrue((root / "output" / "inbox" / "index.html").exists())
            self.assertTrue((root / "output" / "index.html").exists())
            log_text = (root / "log.md").read_text(encoding="utf-8")
            self.assertIn("batch-ingest | quality=ready", log_text)
            self.assertIn("wiki/sources/new-ready.md", log_text)

    def test_health_passes_on_fresh_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir) / "wiki"
            run_script("init_wiki.py", "--root", str(root), "--title", "Healthy Wiki")

            result = run_script("health.py", "--root", str(root))

            self.assertIn("ThinkWiki Health Report", result.stdout)
            self.assertIn("- Errors: 0", result.stdout)
            self.assertIn("- Warnings: 0", result.stdout)
            self.assertIn("All checks passed", result.stdout)

    def test_status_command_reports_workspace_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir) / "wiki"
            run_script("init_wiki.py", "--root", str(root), "--title", "Status Wiki")
            write_text(
                root / "wiki" / "concepts" / "ai-native-team.md",
                """
                ---
                title: AI Native Team
                type: concept
                created: 2026-06-21
                updated: 2026-06-21
                summary: A concept page used for status testing.
                sources:
                  - raw/articles/team-note.md
                tags:
                  - concept
                confidence: high
                status: active
                ---

                # AI Native Team

                A concept page used for status testing.
                """,
            )
            write_text(
                root / "normalized" / "inbox" / "2026-06-21-captured-article.md",
                """
                # Captured Article

                This article is complete enough to be treated as ready for ingest.
                """,
            )
            write_text(
                root / "normalized" / "inbox" / "2026-06-21-captured-article.json",
                json.dumps({
                    "kind": "web",
                    "adapter": "generic",
                    "title": "Captured Article",
                    "siteName": "Example Blog",
                    "author": "Ada Lovelace",
                    "publishDate": "2026-06-21",
                    "url": "https://example.com/article",
                }, ensure_ascii=False, indent=2),
            )

            run_script("build_inbox.py", "--root", str(root))
            run_script("build_viewer.py", "--root", str(root))
            run_script("build_graph.py", "--root", str(root))

            result = run_thinkwiki("status", "--root", str(root))

            self.assertIn("ThinkWiki Status", result.stdout)
            self.assertIn("Title: wiki", result.stdout)
            self.assertIn("Pages: 1 (concept=1)", result.stdout)
            self.assertIn("Inbox: total=1, ready=1, review=0, weak=0", result.stdout)
            self.assertIn("Output Home: ready", result.stdout)
            self.assertIn("Viewer: ready", result.stdout)
            self.assertIn("Graph: ready", result.stdout)
            self.assertIn("Inbox Review: ready", result.stdout)

    def test_health_warns_on_invalid_inbox_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir) / "wiki"
            run_script("init_wiki.py", "--root", str(root), "--title", "Warning Wiki")
            write_text(root / "normalized" / "inbox" / "2026-06-21-bad.json", "{not-json")

            result = run_script("health.py", "--root", str(root))

            self.assertIn("- Errors: 0", result.stdout)
            self.assertIn("- Warnings: 1", result.stdout)
            self.assertIn("[invalid-inbox-metadata]", result.stdout)

    def test_init_reports_next_output_commands(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir) / "wiki"
            result = run_script("init_wiki.py", "--root", str(root), "--title", "Test Wiki")

            self.assertIn("Initialized wiki at ", result.stdout)
            self.assertIn(str(root.resolve()), result.stdout)
            self.assertIn("Next: run `python scripts/thinkwiki viewer --root", result.stdout)
            self.assertIn("Next: run `python scripts/thinkwiki graph --root", result.stdout)

    def test_graph_keeps_wiki_source_node_types(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir) / "wiki"
            write_text(root / ".wiki-schema.md", "# marker")
            (root / "raw" / "articles").mkdir(parents=True, exist_ok=True)
            (root / "output" / "graph").mkdir(parents=True, exist_ok=True)
            (root / "wiki" / "sources").mkdir(parents=True, exist_ok=True)
            (root / "wiki" / "topics").mkdir(parents=True, exist_ok=True)
            (root / "raw" / "articles" / "platform.docx").write_text("raw", encoding="utf-8")
            write_text(
                root / "wiki" / "sources" / "platform-spec.md",
                """
                ---
                title: Platform Spec
                type: source
                created: 2026-06-15
                updated: 2026-06-15
                summary: Source summary.
                sources:
                  - raw/articles/platform.docx
                tags:
                  - source
                confidence: extracted
                status: active
                ---

                # Platform Spec

                ## Summary

                Source summary.
                """,
            )
            write_text(
                root / "wiki" / "topics" / "platform.md",
                """
                ---
                title: Platform
                type: topic
                created: 2026-06-15
                updated: 2026-06-15
                summary: Topic summary.
                sources:
                  - wiki/sources/platform-spec.md
                tags:
                  - topic
                confidence: mixed
                status: active
                ---

                # Platform

                ## Included Sources

                - [Platform Spec](../sources/platform-spec.md)
                """,
            )

            run_script("build_graph.py", "--root", str(root))
            graph = json.loads((root / "output" / "graph" / "graph.json").read_text(encoding="utf-8"))
            node_by_id = {node["id"]: node for node in graph["nodes"]}
            document_edges = graph["views"]["document"]["edges"]

            self.assertEqual(node_by_id["wiki/sources/platform-spec.md"]["type"], "source")
            self.assertEqual(node_by_id["wiki/sources/platform-spec.md"]["summary"], "Source summary.")
            self.assertEqual(node_by_id["wiki/sources/platform-spec.md"]["confidence"], "extracted")
            self.assertEqual(node_by_id["wiki/sources/platform-spec.md"]["status"], "active")
            self.assertEqual(node_by_id["wiki/sources/platform-spec.md"]["path"], "wiki/sources/platform-spec.md")
            self.assertTrue(
                any(
                    edge["source"] == "wiki/topics/platform.md"
                    and edge["target"] == "wiki/sources/platform-spec.md"
                    and edge["type"] == "includes"
                    for edge in document_edges
                )
            )

    def test_graph_build_writes_html_viewer(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir) / "wiki"
            write_text(root / ".wiki-schema.md", "# marker")
            (root / "wiki" / "sources").mkdir(parents=True, exist_ok=True)
            (root / "output" / "graph").mkdir(parents=True, exist_ok=True)
            write_text(
                root / "wiki" / "sources" / "alpha.md",
                """
                ---
                title: Alpha Source
                type: source
                created: 2026-06-19
                updated: 2026-06-19
                summary: Alpha summary.
                sources:
                  - raw/articles/alpha.md
                tags:
                  - source
                confidence: extracted
                status: active
                ---

                # Alpha Source

                ## Summary

                Alpha summary.
                """,
            )

            run_script("build_graph.py", "--root", str(root))

            html_path = root / "output" / "graph" / "index.html"
            self.assertTrue(html_path.exists())
            html_text = html_path.read_text(encoding="utf-8")
            self.assertIn("ThinkWiki Graph", html_text)
            self.assertIn("Alpha Source", html_text)
            self.assertIn("../viewer/index.html#page=", html_text)
            self.assertIn('id="graphStage"', html_text)
            self.assertIn("centerNodeInStage", html_text)
            self.assertIn("Legend", html_text)
            self.assertIn("edgeStyles", html_text)
            self.assertIn('id="scopeFilter"', html_text)
            self.assertIn("scopeFilterEl", html_text)
            self.assertIn("edgeType-references", html_text)
            self.assertIn("enabledEdgeTypes", html_text)
            self.assertIn("Quick Focus", html_text)
            self.assertIn("syncFocusButtons", html_text)
            self.assertIn('data-focus-type="concept"', html_text)
            self.assertIn("edgeStatsForNode", html_text)
            self.assertIn("Relation Stats", html_text)
            self.assertIn("Graph Insights", html_text)
            self.assertIn("Key Pages", html_text)
            self.assertIn("Bridge Pages", html_text)
            self.assertIn("Suggested Links", html_text)
            self.assertIn("suggestionKey", html_text)
            self.assertIn("renderInsights", html_text)
            self.assertIn("stroke-dasharray", html_text)
            self.assertIn('id="viewNameValue">knowledge</span>', html_text)
            self.assertIn("Schema: ", html_text)
            self.assertIn('data-focus-type="claim"', html_text)
            self.assertIn('data-view-mode="knowledge"', html_text)
            self.assertIn('data-view-mode="document"', html_text)
            self.assertIn('data-view-mode="suggested"', html_text)
            self.assertIn("refreshViewState", html_text)
            self.assertIn("syncModeButtons", html_text)
            self.assertTrue((root / "output" / "index.html").exists())
            self.assertIn("output/graph/index.html", (root / "log.md").read_text(encoding="utf-8"))

    def test_graph_insights_identify_key_pages_and_link_suggestions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir) / "wiki"
            write_text(root / ".wiki-schema.md", "# marker")
            (root / "wiki" / "sources").mkdir(parents=True, exist_ok=True)
            (root / "wiki" / "topics").mkdir(parents=True, exist_ok=True)
            (root / "wiki" / "concepts").mkdir(parents=True, exist_ok=True)
            (root / "wiki" / "queries").mkdir(parents=True, exist_ok=True)

            write_text(
                root / "wiki" / "sources" / "platform-spec.md",
                """
                ---
                title: Platform Spec
                type: source
                created: 2026-06-19
                updated: 2026-06-19
                summary: Platform foundation and terminology.
                sources:
                  - raw/articles/platform.pdf
                confidence: extracted
                status: active
                ---

                # Platform Spec
                """,
            )
            write_text(
                root / "wiki" / "topics" / "platform.md",
                """
                ---
                title: Platform
                type: topic
                created: 2026-06-19
                updated: 2026-06-19
                summary: Platform topic overview.
                sources:
                  - wiki/sources/platform-spec.md
                confidence: mixed
                status: active
                ---

                # Platform

                - [Platform Spec](../sources/platform-spec.md)
                """,
            )
            write_text(
                root / "wiki" / "concepts" / "platform-principles.md",
                """
                ---
                title: Platform Principles
                type: concept
                created: 2026-06-19
                updated: 2026-06-19
                summary: Platform principles for the current wiki.
                sources:
                  - wiki/sources/platform-spec.md
                confidence: inferred
                status: active
                ---

                # Platform Principles
                """,
            )
            write_text(
                root / "wiki" / "queries" / "orphan-question.md",
                """
                ---
                title: Orphan Question
                type: query
                created: 2026-06-19
                updated: 2026-06-19
                summary: A loose question that still needs links.
                confidence: mixed
                status: active
                ---

                # Orphan Question
                """,
            )

            run_script("build_graph.py", "--root", str(root))
            graph = json.loads((root / "output" / "graph" / "graph.json").read_text(encoding="utf-8"))
            insights = graph["insights"]

            self.assertIn("summary", insights)
            self.assertGreaterEqual(len(insights["topNodes"]), 1)
            self.assertEqual(insights["topNodes"][0]["id"], "wiki/sources/platform-spec.md")
            self.assertTrue(
                any(item["id"] == "wiki/queries/orphan-question.md" and item["severity"] == "isolated" for item in insights["isolatedNodes"])
            )
            self.assertTrue(
                any(
                    {item["source"], item["target"]} == {
                        "wiki/topics/platform.md",
                        "wiki/concepts/platform-principles.md",
                    }
                    for item in insights["suggestedLinks"]
                )
            )

    def test_graph_build_writes_v2_knowledge_view_with_claims_and_explicit_relations(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir) / "wiki"
            write_text(root / ".wiki-schema.md", "# marker")
            (root / "wiki" / "sources").mkdir(parents=True, exist_ok=True)
            (root / "wiki" / "topics").mkdir(parents=True, exist_ok=True)
            (root / "wiki" / "concepts").mkdir(parents=True, exist_ok=True)
            (root / "output" / "graph").mkdir(parents=True, exist_ok=True)
            write_text(
                root / "wiki" / "sources" / "platform-spec.md",
                """
                ---
                title: Platform Spec
                type: source
                created: 2026-06-22
                updated: 2026-06-22
                summary: Source backing for execution rules.
                sources:
                  - raw/articles/platform.pdf
                confidence: extracted
                status: active
                ---

                # Platform Spec
                """,
            )
            write_text(
                root / "wiki" / "topics" / "platform.md",
                """
                ---
                title: Platform
                type: topic
                created: 2026-06-22
                updated: 2026-06-22
                summary: Platform topic.
                sources:
                  - wiki/sources/platform-spec.md
                confidence: mixed
                status: active
                ---

                # Platform
                """,
            )
            write_text(
                root / "wiki" / "concepts" / "review-loop.md",
                """
                ---
                title: Review Loop
                type: concept
                created: 2026-06-22
                updated: 2026-06-22
                summary: Review loop concept.
                sources:
                  - wiki/sources/platform-spec.md
                confidence: inferred
                status: active
                ---

                # Review Loop
                """,
            )
            write_text(
                root / "wiki" / "concepts" / "execution-spec.md",
                """
                ---
                title: Execution Spec
                type: concept
                created: 2026-06-22
                updated: 2026-06-22
                summary: Execution structure for reliable delivery.
                sources:
                  - wiki/sources/platform-spec.md
                topics:
                  - Platform
                concepts:
                  - Review Loop
                graph:
                  explicit_relations:
                    - type: depends_on
                      target: wiki/concepts/review-loop.md
                claims:
                  - text: Execution quality depends on explicit review loops.
                    confidence: high
                    supports:
                      - wiki/sources/platform-spec.md
                confidence: inferred
                status: active
                ---

                # Execution Spec

                ## Connections
                - related_to: [[Review Loop]]
                """,
            )

            run_script("build_graph.py", "--root", str(root))
            graph = json.loads((root / "output" / "graph" / "graph.json").read_text(encoding="utf-8"))

            self.assertEqual(graph["schema_version"], "2")
            self.assertEqual(graph["default_view"], "knowledge")
            self.assertIn("views", graph)
            self.assertNotIn("claim", {node["type"] for node in graph["nodes"]})

            knowledge = graph["views"]["knowledge"]
            knowledge_node_ids = {node["id"] for node in knowledge["nodes"]}
            knowledge_edge_types = {edge["type"] for edge in knowledge["edges"]}

            self.assertIn("claim:wiki/concepts/execution-spec.md#1", knowledge_node_ids)
            self.assertIn("belongs_to", knowledge_edge_types)
            self.assertIn("about", knowledge_edge_types)
            self.assertIn("depends_on", knowledge_edge_types)
            self.assertIn("asserts", knowledge_edge_types)
            self.assertIn("supports", knowledge_edge_types)
            self.assertEqual(knowledge["insights"]["stats"]["nodeCount"], 4)

    def test_graph_report_integrates_with_status_health_and_home(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir) / "wiki"
            run_script("init_wiki.py", "--root", str(root), "--title", "Graph Report Wiki")

            write_text(
                root / "wiki" / "sources" / "platform-spec.md",
                """
                ---
                title: Platform Spec
                type: source
                created: 2026-06-21
                updated: 2026-06-21
                summary: Tiny.
                sources:
                  - raw/articles/platform.pdf
                entities:
                  - OpenClaw
                tags:
                  - source
                confidence: extracted
                status: active
                ---

                # Platform Spec
                """,
            )
            write_text(
                root / "wiki" / "entities" / "openclaw.md",
                """
                ---
                title: OpenClaw
                type: entity
                created: 2026-06-21
                updated: 2026-06-21
                summary: OpenClaw entity page.
                sources:
                  - wiki/sources/platform-spec.md
                aliases:
                  - OpenClaw Platform
                  - OpenClaw System
                topics:
                  - Platform
                tags:
                  - entity
                confidence: mixed
                status: active
                maturity: emerging
                ---

                # OpenClaw
                """,
            )
            write_text(
                root / "wiki" / "entities" / "openclaw-platform.md",
                """
                ---
                title: OpenClaw Platform
                type: entity
                created: 2026-06-21
                updated: 2026-06-21
                summary: Alternate entity page that should now be flagged as an ambiguous merge candidate.
                sources:
                  - wiki/sources/platform-spec.md
                aliases:
                  - OpenClaw Delivery Platform
                topics:
                  - Platform
                tags:
                  - entity
                confidence: mixed
                status: active
                maturity: emerging
                ---

                # OpenClaw Platform
                """,
            )
            write_text(
                root / "wiki" / "topics" / "platform.md",
                """
                ---
                title: Platform
                type: topic
                created: 2026-06-21
                updated: 2026-06-21
                summary: Platform topic overview with enough context to connect to the core source.
                sources:
                  - wiki/sources/platform-spec.md
                tags:
                  - topic
                confidence: mixed
                status: active
                ---

                # Platform
                """,
            )
            write_text(
                root / "wiki" / "concepts" / "platform-principles.md",
                """
                ---
                title: Platform Principles
                type: concept
                created: 2026-06-21
                updated: 2026-06-21
                summary: Platform principles explain how the platform should evolve and how teams should reuse the source material.
                sources:
                  - wiki/sources/platform-spec.md
                tags:
                  - concept
                confidence: inferred
                status: active
                ---

                # Platform Principles
                """,
            )
            write_text(
                root / "wiki" / "decisions" / "platform-decision.md",
                """
                ---
                title: Platform Decision
                type: decision
                created: 2026-06-21
                updated: 2026-06-21
                summary: This decision records why the team keeps building around the platform source page.
                sources:
                  - wiki/sources/platform-spec.md
                tags:
                  - decision
                confidence: high
                status: active
                ---

                # Platform Decision
                """,
            )
            write_text(
                root / "wiki" / "queries" / "bridge-question.md",
                """
                ---
                title: Bridge Question
                type: query
                created: 2026-06-21
                updated: 2026-06-21
                summary: This question connects the central source page with the platform principles page.
                sources:
                  - wiki/sources/platform-spec.md
                tags:
                  - query
                confidence: mixed
                status: active
                ---

                # Bridge Question

                - [Platform Principles](../concepts/platform-principles.md)
                """,
            )
            write_text(
                root / "wiki" / "sources" / "cluster-spec.md",
                """
                ---
                title: Cluster Spec
                type: source
                created: 2026-06-21
                updated: 2026-06-21
                summary: Cluster source summary.
                sources:
                  - raw/articles/cluster.pdf
                tags:
                  - source
                confidence: extracted
                status: active
                ---

                # Cluster Spec
                """,
            )
            write_text(
                root / "wiki" / "topics" / "cluster-topic.md",
                """
                ---
                title: Cluster Topic
                type: topic
                created: 2026-06-21
                updated: 2026-06-21
                summary: This topic is intentionally disconnected from the main platform graph.
                sources:
                  - wiki/sources/cluster-spec.md
                tags:
                  - topic
                confidence: mixed
                status: active
                ---

                # Cluster Topic
                """,
            )
            write_text(
                root / "wiki" / "queries" / "orphan-question.md",
                """
                ---
                title: Orphan Question
                type: query
                created: 2026-06-21
                updated: 2026-06-21
                summary: A page that still needs its first explicit relationship.
                sources:
                  - raw/articles/orphan.txt
                tags:
                  - query
                confidence: low
                status: draft
                ---

                # Orphan Question
                """,
            )

            run_script("build_viewer.py", "--root", str(root))
            run_script("build_graph.py", "--root", str(root))

            result = run_thinkwiki("graph-report", "--root", str(root))
            entity_review_result = run_thinkwiki("entity-merge-review", "--root", str(root))

            report_json_path = root / "output" / "graph" / "report.json"
            report_md_path = root / "output" / "graph" / "report.md"
            report_html_path = root / "output" / "graph" / "report.html"
            entity_review_json_path = root / "output" / "graph" / "entity-merge-review.json"
            entity_review_md_path = root / "output" / "graph" / "entity-merge-review.md"
            entity_review_html_path = root / "output" / "graph" / "entity-merge-review.html"
            self.assertTrue(report_json_path.exists())
            self.assertTrue(report_md_path.exists())
            self.assertTrue(report_html_path.exists())
            self.assertTrue(entity_review_json_path.exists())
            self.assertTrue(entity_review_md_path.exists())
            self.assertTrue(entity_review_html_path.exists())
            report = json.loads(report_json_path.read_text(encoding="utf-8"))
            stats = report["stats"]
            entity_review = json.loads(entity_review_json_path.read_text(encoding="utf-8"))

            self.assertIn("ThinkWiki Graph Report", result.stdout)
            self.assertIn("Graph report: output/graph/report.html", result.stdout)
            self.assertIn("ThinkWiki Entity Merge Review", entity_review_result.stdout)
            self.assertIn("Entity merge review: output/graph/entity-merge-review.html", entity_review_result.stdout)
            self.assertEqual(stats["isolatedPageCount"], 1)
            self.assertGreaterEqual(stats["hubStubCount"], 1)
            self.assertEqual(stats["isolatedClusterCount"], 1)
            self.assertGreaterEqual(stats["fragileBridgeCount"], 1)
            self.assertGreaterEqual(stats["entityCount"], 1)
            self.assertGreaterEqual(stats["aliasedEntityCount"], 1)
            self.assertGreaterEqual(stats["aliasCount"], 2)
            self.assertGreaterEqual(stats["ambiguousAliasGroupCount"], 1)
            self.assertGreaterEqual(stats["ambiguousEntityCount"], 2)
            self.assertTrue(report["ambiguousEntityMergeCandidates"])
            self.assertTrue(any(item["identityKey"] == "openclaw" for item in report["ambiguousEntityMergeCandidates"]))
            self.assertEqual(entity_review["stats"]["ambiguousAliasGroupCount"], stats["ambiguousAliasGroupCount"])
            self.assertTrue(any(item["identityKey"] == "openclaw" for item in entity_review["candidates"]))
            self.assertTrue(any("isolated pages" in item for item in report["topActions"]))

            status_result = run_thinkwiki("status", "--root", str(root))
            self.assertIn("Graph Report: ready", status_result.stdout)
            self.assertIn("isolatedPages=1", status_result.stdout)
            self.assertIn("isolatedEntities=", status_result.stdout)
            self.assertIn("aliasedEntities=", status_result.stdout)
            self.assertIn("aliases=", status_result.stdout)
            self.assertIn("ambiguousAliasGroups=", status_result.stdout)
            self.assertIn("ambiguousEntities=", status_result.stdout)
            self.assertIn("hubStubs=", status_result.stdout)
            self.assertIn("clusters=1", status_result.stdout)
            self.assertIn("schema=v2", status_result.stdout)
            self.assertIn("defaultView=knowledge", status_result.stdout)
            self.assertIn("claims=", status_result.stdout)
            self.assertIn("entities=", status_result.stdout)

            health_result = run_thinkwiki("health", "--root", str(root))
            self.assertIn("Knowledge Graph: schema=v2, defaultView=knowledge", health_result.stdout)
            self.assertIn("entities=", health_result.stdout)
            self.assertIn("aliasedEntities=", health_result.stdout)
            self.assertIn("aliases=", health_result.stdout)
            self.assertIn("ambiguousAliasGroups=", health_result.stdout)
            self.assertIn("ambiguousEntities=", health_result.stdout)
            self.assertIn("Graph Report: ready, isolatedPages=1, isolatedEntities=", health_result.stdout)
            self.assertIn("- Errors: 0", health_result.stdout)
            self.assertIn("- Warnings: 0", health_result.stdout)

            hub_html = (root / "output" / "index.html").read_text(encoding="utf-8")
            self.assertIn("Graph Governance Report", hub_html)
            self.assertIn("graph/report.html", hub_html)
            self.assertIn("graph/entity-merge-review.html", hub_html)
            self.assertIn("Hub Stubs", hub_html)
            self.assertIn("Isolated Clusters 1", hub_html)
            self.assertIn("Fix isolated pages first", hub_html)
            self.assertIn("Graph Schema v2", hub_html)
            self.assertIn("Default View knowledge", hub_html)
            self.assertIn("Claims", hub_html)
            self.assertIn("Entities", hub_html)
            self.assertIn("Aliased Entities", hub_html)
            self.assertIn("Aliases", hub_html)
            self.assertIn("Ambiguous Alias Groups", hub_html)
            self.assertIn("Ambiguous Entities", hub_html)
            self.assertIn("Ambiguous Alias Groups", hub_html)
            self.assertIn("Entity Merge Review", hub_html)
            self.assertIn("Review Entity Merge Candidates", hub_html)
            self.assertIn("Isolated Entities", hub_html)

            report_html = report_html_path.read_text(encoding="utf-8")
            self.assertIn("ThinkWiki Graph Report", report_html)
            self.assertIn("Entities", report_html)
            self.assertIn("Aliased Entities", report_html)
            self.assertIn("Aliases", report_html)
            self.assertIn("Ambiguous Alias Groups", report_html)
            self.assertIn("Ambiguous Entities", report_html)
            self.assertIn("Ambiguous Entity Merge Candidates", report_html)
            self.assertIn("Entities That Need Links", report_html)
            self.assertIn("Pages That Need Links", report_html)
            self.assertIn("Hub Stubs", report_html)
            self.assertIn("Open Workspace Home", report_html)

            entity_review_html = entity_review_html_path.read_text(encoding="utf-8")
            self.assertIn("ThinkWiki Entity Merge Review", entity_review_html)
            self.assertIn("Ambiguous Alias Groups", entity_review_html)
            self.assertIn("Candidates", entity_review_html)
            self.assertIn("Open Workspace Home", entity_review_html)

    def test_output_hub_shows_wiki_stats(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir) / "wiki"
            write_text(root / ".wiki-schema.md", "# marker")
            write_text(root / "index.md", "# Demo Knowledge Base")
            (root / "wiki" / "sources").mkdir(parents=True, exist_ok=True)
            (root / "wiki" / "topics").mkdir(parents=True, exist_ok=True)
            (root / "output" / "viewer").mkdir(parents=True, exist_ok=True)
            (root / "output" / "graph").mkdir(parents=True, exist_ok=True)
            write_text(
                root / "wiki" / "sources" / "alpha.md",
                """
                ---
                title: Alpha Source
                type: source
                created: 2026-06-19
                updated: 2026-06-19
                summary: Alpha summary.
                sources:
                  - raw/articles/alpha.md
                tags:
                  - source
                confidence: extracted
                status: active
                ---

                # Alpha Source

                ## Summary

                Alpha summary.
                """,
            )
            write_text(
                root / "wiki" / "topics" / "beta.md",
                """
                ---
                title: Beta Topic
                type: topic
                created: 2026-06-19
                updated: 2026-06-19
                summary: Beta summary.
                sources:
                  - wiki/sources/alpha.md
                tags:
                  - topic
                confidence: mixed
                status: active
                ---

                # Beta Topic

                ## Included Sources

                - [Alpha Source](../sources/alpha.md)
                """,
            )

            run_script("build_viewer.py", "--root", str(root))
            run_script("build_graph.py", "--root", str(root))

            hub_html = (root / "output" / "index.html").read_text(encoding="utf-8")
            self.assertIn("Demo Knowledge Base", hub_html)
            self.assertIn("Workspace Home", hub_html)
            self.assertIn(">2</strong><span>Pages</span>", hub_html)
            self.assertIn(">2</strong><span>Graph Nodes</span>", hub_html)
            self.assertIn(">2</strong><span>Graph Edges</span>", hub_html)
            self.assertIn(">0</strong><span>Claims</span>", hub_html)
            self.assertIn(">0</strong><span>Entities</span>", hub_html)
            self.assertIn("What Changed", hub_html)
            self.assertIn("Next Actions", hub_html)
            self.assertIn("Needs Attention", hub_html)
            self.assertIn("Graph Snapshot", hub_html)
            self.assertIn("Featured Pages", hub_html)
            self.assertIn("Outputs Overview", hub_html)
            self.assertIn("Start here", hub_html)
            self.assertIn("Alpha Source", hub_html)
            self.assertIn("Beta Topic", hub_html)
            self.assertIn("viewer/index.html#page=wiki/topics/beta.md", hub_html)
            self.assertIn("Current key page:", hub_html)
            self.assertIn("Graph Schema v2", hub_html)
            self.assertIn("Default View knowledge", hub_html)
            self.assertIn("Entities", hub_html)

    def test_directory_ingest_updates_topic_sources(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir) / "wiki"
            source_dir = Path(tmp_dir) / "docs"
            write_text(source_dir / "platform" / "a.md", "# A\n\nAlpha summary.")
            write_text(source_dir / "platform" / "b.md", "# B\n\nBeta summary.")

            run_script("init_wiki.py", "--root", str(root), "--title", "Test Wiki")
            run_script("ingest.py", "--root", str(root), "--source", str(source_dir))

            topic_text = (root / "wiki" / "topics" / "platform.md").read_text(encoding="utf-8")
            self.assertIn("wiki/sources/a.md", topic_text)
            self.assertIn("wiki/sources/b.md", topic_text)
            self.assertIn("[a](../sources/a.md)", topic_text)
            self.assertIn("[b](../sources/b.md)", topic_text)

    def test_ingest_writes_structured_knowledge_fields_and_graph_relations(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir) / "wiki"
            source = Path(tmp_dir) / "execution-spec.md"
            write_text(
                source,
                """
                # Execution Spec

                Reliable delivery in OpenClaw depends on explicit review loops and clear execution boundaries.

                ## Review Loop

                Teams using Claude Code in OpenClaw should keep a review loop before finalizing important changes.

                ## Key Guidance

                Keep scope visible and reviewable in ThinkWiki.
                """,
            )
            run_script("init_wiki.py", "--root", str(root), "--title", "Test Wiki")
            write_text(
                root / "wiki" / "concepts" / "review-loop.md",
                """
                ---
                title: Review Loop
                type: concept
                created: 2026-06-22
                updated: 2026-06-22
                summary: Review loop concept page.
                sources:
                  - raw/articles/review-loop.md
                tags:
                  - concept
                confidence: mixed
                status: active
                ---

                # Review Loop
                """,
            )

            run_script("ingest.py", "--root", str(root), "--source", str(source), "--topic", "Platform")
            source_page = root / "wiki" / "sources" / "execution-spec.md"
            openclaw_page = root / "wiki" / "entities" / "openclaw.md"
            claude_code_page = root / "wiki" / "entities" / "claude-code.md"
            source_text = source_page.read_text(encoding="utf-8")
            openclaw_text = openclaw_page.read_text(encoding="utf-8")

            self.assertIn("topics:\n  - Platform", source_text)
            self.assertIn("entities:", source_text)
            self.assertIn("  - OpenClaw", source_text)
            self.assertIn("  - Claude Code", source_text)
            self.assertIn("concepts:\n  - Review Loop", source_text)
            self.assertIn("claims:", source_text)
            self.assertIn("## Entities", source_text)
            self.assertIn("- [OpenClaw](../entities/openclaw.md)", source_text)
            self.assertIn("- [Claude Code](../entities/claude-code.md)", source_text)
            self.assertIn("## Knowledge Connections", source_text)
            self.assertIn("- belongs_to: [[Platform]]", source_text)
            self.assertIn("- related_to: [[Review Loop]]", source_text)
            self.assertIn("- about: [[OpenClaw]]", source_text)
            self.assertIn("## Claims", source_text)
            self.assertIn("[high]", source_text)
            self.assertTrue(openclaw_page.exists())
            self.assertTrue(claude_code_page.exists())
            self.assertIn("type: entity", openclaw_text)
            self.assertIn("sources:\n  - wiki/sources/execution-spec.md", openclaw_text)
            self.assertIn("topics:\n  - Platform", openclaw_text)

            run_script("build_graph.py", "--root", str(root))
            graph = json.loads((root / "output" / "graph" / "graph.json").read_text(encoding="utf-8"))
            knowledge = graph["views"]["knowledge"]
            knowledge_edges = knowledge["edges"]
            knowledge_nodes = knowledge["nodes"]

            self.assertTrue(
                any(
                    edge["source"] == "wiki/sources/execution-spec.md"
                    and edge["target"] == "wiki/topics/platform.md"
                    and edge["type"] == "belongs_to"
                    for edge in knowledge_edges
                )
            )
            self.assertTrue(
                any(
                    edge["source"] == "wiki/sources/execution-spec.md"
                    and edge["target"] == "wiki/concepts/review-loop.md"
                    and edge["type"] in {"about", "related_to"}
                    for edge in knowledge_edges
                )
            )
            openclaw_entity_ids = [
                node["id"]
                for node in knowledge_nodes
                if node.get("type") == "entity" and node.get("label") == "OpenClaw"
            ]
            self.assertTrue(openclaw_entity_ids)
            self.assertTrue(
                any(
                    edge["source"] == "wiki/sources/execution-spec.md"
                    and edge["target"] == "wiki/entities/openclaw.md"
                    and edge["type"] == "about"
                    for edge in knowledge_edges
                )
            )
            self.assertTrue(
                any(
                    str(node["id"]).startswith("claim:wiki/sources/execution-spec.md#")
                    for node in knowledge_nodes
                )
            )
            self.assertNotIn("entity:openclaw", {node["id"] for node in knowledge_nodes})

    def test_ingest_reuses_existing_entity_page_and_refreshes_graph_links(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir) / "wiki"
            source = Path(tmp_dir) / "openclaw-platform-note.md"
            write_text(
                source,
                """
                # OpenClaw Platform Note

                OpenClaw Platform keeps the execution loop visible for the team.
                """,
            )
            run_script("init_wiki.py", "--root", str(root), "--title", "Test Wiki")
            write_text(
                root / "wiki" / "entities" / "openclaw.md",
                """
                ---
                title: OpenClaw
                type: entity
                created: 2026-06-22
                updated: 2026-06-22
                summary: Existing entity page.
                sources:
                  - wiki/sources/legacy.md
                topics:
                  - Platform
                tags:
                  - entity
                confidence: mixed
                status: active
                maturity: emerging
                ---

                # OpenClaw
                """,
            )

            run_script("ingest.py", "--root", str(root), "--source", str(source), "--topic", "Platform")

            entity_text = (root / "wiki" / "entities" / "openclaw.md").read_text(encoding="utf-8")
            self.assertIn("summary: Existing entity page.", entity_text)
            self.assertIn("  - wiki/sources/legacy.md", entity_text)
            self.assertIn("  - wiki/sources/openclaw-platform-note.md", entity_text)
            self.assertIn("aliases:\n  - OpenClaw Platform", entity_text)
            self.assertEqual(len(list((root / "wiki" / "entities").glob("openclaw*.md"))), 1)
            self.assertFalse((root / "wiki" / "entities" / "openclaw-platform.md").exists())

            run_script("build_graph.py", "--root", str(root))
            graph = json.loads((root / "output" / "graph" / "graph.json").read_text(encoding="utf-8"))
            knowledge_edges = graph["views"]["knowledge"]["edges"]
            self.assertTrue(
                any(
                    edge["source"] == "wiki/sources/openclaw-platform-note.md"
                    and edge["target"] == "wiki/entities/openclaw.md"
                    and edge["type"] == "about"
                    for edge in knowledge_edges
                )
            )

    def test_entity_merge_apply_rewrites_entities_and_rebuilds_graph_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir) / "wiki"
            run_script("init_wiki.py", "--root", str(root), "--title", "Merge Apply Wiki")
            write_text(
                root / "wiki" / "sources" / "platform-spec.md",
                """
                ---
                title: Platform Spec
                type: source
                created: 2026-06-22
                updated: 2026-06-22
                summary: Platform source connected to an entity label that should be canonicalized.
                sources:
                  - raw/articles/platform.pdf
                entities:
                  - OpenClaw Platform
                tags:
                  - source
                confidence: extracted
                status: active
                ---

                # Platform Spec
                """,
            )
            write_text(
                root / "wiki" / "entities" / "openclaw.md",
                """
                ---
                title: OpenClaw
                type: entity
                created: 2026-06-22
                updated: 2026-06-22
                summary: Canonical OpenClaw entity.
                sources:
                  - wiki/sources/platform-spec.md
                aliases:
                  - OpenClaw System
                topics:
                  - Platform
                tags:
                  - entity
                confidence: mixed
                status: active
                maturity: emerging
                ---

                # OpenClaw
                """,
            )
            write_text(
                root / "wiki" / "entities" / "openclaw-platform.md",
                """
                ---
                title: OpenClaw Platform
                type: entity
                created: 2026-06-22
                updated: 2026-06-22
                summary: Alternate page that should be merged into OpenClaw.
                sources:
                  - wiki/sources/platform-spec.md
                aliases:
                  - OpenClaw Delivery Platform
                topics:
                  - Platform
                tags:
                  - entity
                confidence: mixed
                status: active
                maturity: emerging
                ---

                # OpenClaw Platform
                """,
            )

            run_script("build_viewer.py", "--root", str(root))
            run_script("build_graph.py", "--root", str(root))

            review_before = run_thinkwiki("entity-merge-review", "--root", str(root))
            self.assertIn("Ambiguous Alias Groups: 1", review_before.stdout)

            apply_result = run_thinkwiki(
                "entity-merge-apply",
                "--root",
                str(root),
                "--identity-key",
                "openclaw",
                "--canonical",
                "wiki/entities/openclaw.md",
            )

            self.assertIn("ThinkWiki Entity Merge Apply", apply_result.stdout)
            self.assertIn("Canonical: wiki/entities/openclaw.md", apply_result.stdout)
            self.assertIn("merged: wiki/entities/openclaw-platform.md -> wiki/entities/openclaw.md", apply_result.stdout)

            canonical_text = (root / "wiki" / "entities" / "openclaw.md").read_text(encoding="utf-8")
            merged_text = (root / "wiki" / "entities" / "openclaw-platform.md").read_text(encoding="utf-8")
            self.assertIn("aliases:", canonical_text)
            self.assertIn("  - OpenClaw Platform", canonical_text)
            self.assertIn("  - OpenClaw Delivery Platform", canonical_text)
            self.assertIn("status: merged", merged_text)
            self.assertIn("canonical_entity: wiki/entities/openclaw.md", merged_text)
            self.assertIn("This entity page has been merged into", merged_text)

            graph = json.loads((root / "output" / "graph" / "graph.json").read_text(encoding="utf-8"))
            knowledge_nodes = graph["views"]["knowledge"]["nodes"]
            knowledge_edges = graph["views"]["knowledge"]["edges"]
            entity_node_ids = {node["id"] for node in knowledge_nodes if node.get("type") == "entity"}
            self.assertIn("wiki/entities/openclaw.md", entity_node_ids)
            self.assertNotIn("wiki/entities/openclaw-platform.md", entity_node_ids)
            self.assertTrue(
                any(
                    edge["source"] == "wiki/sources/platform-spec.md"
                    and edge["target"] == "wiki/entities/openclaw.md"
                    and edge["type"] == "about"
                    for edge in knowledge_edges
                )
            )

            entity_review = json.loads((root / "output" / "graph" / "entity-merge-review.json").read_text(encoding="utf-8"))
            self.assertEqual(entity_review["stats"]["ambiguousAliasGroupCount"], 0)
            self.assertEqual(entity_review["stats"]["ambiguousEntityCount"], 0)

    def test_entity_merge_apply_dry_run_writes_plan_without_mutating_pages(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir) / "wiki"
            run_script("init_wiki.py", "--root", str(root), "--title", "Merge Plan Wiki")
            write_text(
                root / "wiki" / "sources" / "platform-spec.md",
                """
                ---
                title: Platform Spec
                type: source
                created: 2026-06-22
                updated: 2026-06-22
                summary: Platform source connected to an entity label that should only be previewed.
                sources:
                  - raw/articles/platform.pdf
                entities:
                  - OpenClaw Platform
                tags:
                  - source
                confidence: extracted
                status: active
                ---

                # Platform Spec
                """,
            )
            write_text(
                root / "wiki" / "entities" / "openclaw.md",
                """
                ---
                title: OpenClaw
                type: entity
                created: 2026-06-22
                updated: 2026-06-22
                summary: Canonical OpenClaw entity.
                sources:
                  - wiki/sources/platform-spec.md
                aliases:
                  - OpenClaw System
                topics:
                  - Platform
                tags:
                  - entity
                confidence: mixed
                status: active
                maturity: emerging
                ---

                # OpenClaw
                """,
            )
            write_text(
                root / "wiki" / "entities" / "openclaw-platform.md",
                """
                ---
                title: OpenClaw Platform
                type: entity
                created: 2026-06-22
                updated: 2026-06-22
                summary: Alternate page that should be previewed before merge.
                sources:
                  - wiki/sources/platform-spec.md
                aliases:
                  - OpenClaw Delivery Platform
                topics:
                  - Platform
                tags:
                  - entity
                confidence: mixed
                status: active
                maturity: emerging
                ---

                # OpenClaw Platform
                """,
            )

            run_script("build_viewer.py", "--root", str(root))
            run_script("build_graph.py", "--root", str(root))
            run_thinkwiki("entity-merge-review", "--root", str(root))

            canonical_before = (root / "wiki" / "entities" / "openclaw.md").read_text(encoding="utf-8")
            merged_before = (root / "wiki" / "entities" / "openclaw-platform.md").read_text(encoding="utf-8")

            dry_run_result = run_thinkwiki(
                "entity-merge-apply",
                "--root",
                str(root),
                "--identity-key",
                "openclaw",
                "--canonical",
                "wiki/entities/openclaw.md",
                "--dry-run",
            )

            self.assertIn("ThinkWiki Entity Merge Plan", dry_run_result.stdout)
            self.assertIn("Canonical: wiki/entities/openclaw.md", dry_run_result.stdout)
            self.assertIn("preview merge: wiki/entities/openclaw-platform.md -> wiki/entities/openclaw.md", dry_run_result.stdout)
            self.assertIn("Entity merge plan: output/graph/entity-merge-plan.html", dry_run_result.stdout)
            self.assertIn("Output hub: output/index.html", dry_run_result.stdout)

            canonical_after = (root / "wiki" / "entities" / "openclaw.md").read_text(encoding="utf-8")
            merged_after = (root / "wiki" / "entities" / "openclaw-platform.md").read_text(encoding="utf-8")
            self.assertEqual(canonical_before, canonical_after)
            self.assertEqual(merged_before, merged_after)

            plan_json_path = root / "output" / "graph" / "entity-merge-plan.json"
            plan_md_path = root / "output" / "graph" / "entity-merge-plan.md"
            plan_html_path = root / "output" / "graph" / "entity-merge-plan.html"
            self.assertTrue(plan_json_path.exists())
            self.assertTrue(plan_md_path.exists())
            self.assertTrue(plan_html_path.exists())

            plan = json.loads(plan_json_path.read_text(encoding="utf-8"))
            self.assertEqual(plan["identityKey"], "openclaw")
            self.assertEqual(plan["canonical"]["id"], "wiki/entities/openclaw.md")
            self.assertEqual(plan["stats"]["mergedPageCount"], 1)
            self.assertEqual(plan["stats"]["addedAliasCount"], 2)
            self.assertEqual(plan["stats"]["addedSourceCount"], 0)
            self.assertEqual(plan["stats"]["addedTopicCount"], 0)
            self.assertEqual(plan["canonical"]["addedAliases"], ["OpenClaw Platform", "OpenClaw Delivery Platform"])
            self.assertEqual(len(plan["mergedPages"]), 1)
            self.assertEqual(plan["mergedPages"][0]["id"], "wiki/entities/openclaw-platform.md")
            self.assertEqual(plan["mergedPages"][0]["afterStatus"], "merged")

            plan_html = plan_html_path.read_text(encoding="utf-8")
            self.assertIn("ThinkWiki Entity Merge Plan", plan_html)
            self.assertIn("Dry-run preview for entity merge apply", plan_html)
            self.assertIn("Open Workspace Home", plan_html)
            self.assertIn("Open Entity Merge Review", plan_html)

            hub_html = (root / "output" / "index.html").read_text(encoding="utf-8")
            self.assertIn("graph/entity-merge-plan.html", hub_html)
            self.assertIn("Entity Merge Plan", hub_html)
            log_text = (root / "log.md").read_text(encoding="utf-8")
            self.assertIn("entity-merge-plan | openclaw", log_text)
            self.assertIn("output/graph/entity-merge-plan.html", log_text)

    def test_clip_text_creates_inbox_item_and_next_step(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir) / "wiki"
            run_script("init_wiki.py", "--root", str(root), "--title", "Test Wiki")

            result = run_script(
                "clip.py",
                "--root",
                str(root),
                "--title",
                "Inbox Note",
                "--text",
                "# Inbox Note\n\nThis is a clipped note for later ingest.",
            )

            inbox_files = sorted((root / "normalized" / "inbox").glob("*.md"))
            self.assertEqual(len(inbox_files), 1)
            inbox_text = inbox_files[0].read_text(encoding="utf-8")
            self.assertIn("# Inbox Note", inbox_text)
            self.assertIn("This is a clipped note for later ingest.", inbox_text)
            self.assertIn("Clipped Inbox Note into inbox", result.stdout)
            self.assertIn("Inbox normalized: normalized/inbox/", result.stdout)
            self.assertIn("Inbox review: output/inbox/index.html", result.stdout)
            self.assertIn("Output hub: output/index.html", result.stdout)
            self.assertIn("Next: run `python scripts/thinkwiki ingest --root", result.stdout)
            self.assertIn("normalized/inbox/", (root / "log.md").read_text(encoding="utf-8"))
            self.assertTrue((root / "output" / "inbox" / "index.html").exists())
            self.assertTrue((root / "output" / "index.html").exists())

    def test_clip_refreshes_output_home_and_creates_missing_inbox_dirs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir) / "wiki"
            write_text(root / ".wiki-schema.md", "# marker")
            write_text(root / "index.md", "# Legacy Wiki")
            (root / "output" / "viewer").mkdir(parents=True, exist_ok=True)
            write_text(root / "output" / "viewer" / "index.html", "<html><body>viewer</body></html>")

            result = run_script(
                "clip.py",
                "--root",
                str(root),
                "--title",
                "Fresh Capture",
                "--text",
                "# Fresh Capture\n\nA clipped note for the inbox queue.",
            )

            self.assertTrue((root / "raw" / "inbox").exists())
            self.assertTrue((root / "normalized" / "inbox").exists())
            hub_html = (root / "output" / "index.html").read_text(encoding="utf-8")
            inbox_html = (root / "output" / "inbox" / "index.html").read_text(encoding="utf-8")
            self.assertIn("Inbox Queue", hub_html)
            self.assertIn("Inbox Review", hub_html)
            self.assertIn("Fresh Capture", hub_html)
            self.assertIn("inbox/index.html", hub_html)
            self.assertIn(">1</strong><span>Inbox</span>", hub_html)
            self.assertIn("Next ingest command", inbox_html)
            self.assertIn("python scripts/thinkwiki ingest --root", inbox_html)
            self.assertIn("Fresh Capture", inbox_html)
            self.assertIn("../normalized/inbox/", inbox_html)
            self.assertIn("Inbox review: output/inbox/index.html", result.stdout)
            self.assertIn("Output hub: output/index.html", result.stdout)
            self.assertIn("Output hub URI: file://", result.stdout)

    def test_build_inbox_command_creates_review_page(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir) / "wiki"
            run_script("init_wiki.py", "--root", str(root), "--title", "Inbox Wiki")
            write_text(root / "normalized" / "inbox" / "2026-06-20-team-note.md", "# Team Note\n\nReview this before ingest.")
            write_text(
                root / "normalized" / "inbox" / "2026-06-20-team-note.json",
                json.dumps({
                    "kind": "web",
                    "adapter": "generic",
                    "title": "Team Note",
                    "siteName": "Example Blog",
                    "author": "Ada Lovelace",
                    "publishDate": "2026-06-20",
                    "url": "https://example.com/team-note",
                }, ensure_ascii=False, indent=2),
            )

            result = run_script("build_inbox.py", "--root", str(root))

            inbox_html = (root / "output" / "inbox" / "index.html").read_text(encoding="utf-8")
            self.assertIn("ThinkWiki Inbox Review", inbox_html)
            self.assertIn("Priority Queue", inbox_html)
            self.assertIn("Ready To Ingest", inbox_html)
            self.assertIn("python scripts/thinkwiki batch-ingest --root", inbox_html)
            self.assertIn("Team Note", inbox_html)
            self.assertIn("Review this before ingest.", inbox_html)
            self.assertIn("python scripts/thinkwiki ingest --root", inbox_html)
            self.assertIn("Inbox review: output/inbox/index.html", result.stdout)
            self.assertIn("Output hub: output/index.html", result.stdout)

    def test_clip_url_writes_generic_web_metadata_and_review_details(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir) / "wiki"
            site_root = Path(tmp_dir) / "site"
            run_script("init_wiki.py", "--root", str(root), "--title", "Web Wiki")
            write_text(
                site_root / "article.html",
                """
                <html>
                  <head>
                    <title>Ignored Browser Title</title>
                    <meta property="og:site_name" content="Example Blog">
                    <meta name="author" content="Ada Lovelace">
                    <meta property="article:published_time" content="2026-06-21">
                  </head>
                  <body>
                    <main>
                      <h1>Captured Article</h1>
                      <p>This article should land in ThinkWiki inbox with metadata.</p>
                    </main>
                  </body>
                </html>
                """,
            )

            with serve_directory(site_root) as base_url:
                result = run_script("clip.py", "--root", str(root), "--url", f"{base_url}/article.html")

            metadata_files = sorted((root / "normalized" / "inbox").glob("*.json"))
            self.assertEqual(len(metadata_files), 1)
            payload = json.loads(metadata_files[0].read_text(encoding="utf-8"))
            self.assertEqual(payload["kind"], "web")
            self.assertEqual(payload["adapter"], "generic")
            self.assertEqual(payload["title"], "Captured Article")
            self.assertEqual(payload["siteName"], "Example Blog")
            self.assertEqual(payload["author"], "Ada Lovelace")
            self.assertEqual(payload["publishDate"], "2026-06-21")
            self.assertTrue(payload["url"].endswith("/article.html"))
            self.assertIn("Web adapter: generic", result.stdout)
            self.assertIn("Inbox metadata: normalized/inbox/", result.stdout)
            inbox_html = (root / "output" / "inbox" / "index.html").read_text(encoding="utf-8")
            self.assertIn("Example Blog", inbox_html)
            self.assertIn("Ada Lovelace", inbox_html)
            self.assertIn("2026-06-21", inbox_html)
            self.assertIn("Quality", inbox_html)
            self.assertIn("ready", inbox_html)
            self.assertIn("Open metadata", inbox_html)
            hub_html = (root / "output" / "index.html").read_text(encoding="utf-8")
            self.assertIn("Prioritize Ready Inbox", hub_html)
            self.assertIn("inbox/index.html#ready", hub_html)

    def test_clip_url_auto_detects_wechat_adapter_from_dom(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir) / "wiki"
            site_root = Path(tmp_dir) / "site"
            run_script("init_wiki.py", "--root", str(root), "--title", "WeChat Wiki")
            write_text(
                site_root / "wechat.html",
                """
                <html>
                  <body>
                    <div id="activity-name"><span class="js_title_inner">WeChat Capture</span></div>
                    <div id="js_author_name">Grace Hopper</div>
                    <div id="js_name">ThinkWiki Channel</div>
                    <div id="js_content">
                      <p>This looks like a public WeChat article body.</p>
                    </div>
                    <script>var ct = "1718928000";</script>
                  </body>
                </html>
                """,
            )

            with serve_directory(site_root) as base_url:
                run_script("clip.py", "--root", str(root), "--url", f"{base_url}/wechat.html")

            metadata_files = sorted((root / "normalized" / "inbox").glob("*.json"))
            self.assertEqual(len(metadata_files), 1)
            payload = json.loads(metadata_files[0].read_text(encoding="utf-8"))
            self.assertEqual(payload["adapter"], "wechat")
            self.assertEqual(payload["title"], "WeChat Capture")
            self.assertEqual(payload["siteName"], "ThinkWiki Channel")
            self.assertEqual(payload["author"], "Grace Hopper")
            self.assertTrue(payload["publishDate"].startswith("2024-06-21"))

    def test_clip_url_wechat_code_blocks_are_preserved_for_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir) / "wiki"
            site_root = Path(tmp_dir) / "site"
            run_script("init_wiki.py", "--root", str(root), "--title", "Code Wiki")
            write_text(
                site_root / "wechat-code.html",
                """
                <html>
                  <body>
                    <div id="activity-name"><span class="js_title_inner">WeChat Code Capture</span></div>
                    <div id="js_name">ThinkWiki Channel</div>
                    <div id="js_content">
                      <div class="js_code_area" data-lang="python">
                        <pre>print("hello thinkwiki")</pre>
                      </div>
                    </div>
                    <script>var ct = "1718928000";</script>
                  </body>
                </html>
                """,
            )

            with serve_directory(site_root) as base_url:
                run_script("clip.py", "--root", str(root), "--url", f"{base_url}/wechat-code.html")

            normalized_files = sorted((root / "normalized" / "inbox").glob("*.md"))
            self.assertEqual(len(normalized_files), 1)
            normalized_text = normalized_files[0].read_text(encoding="utf-8")
            self.assertIn('print("hello thinkwiki")', normalized_text)

    def test_build_inbox_marks_low_quality_items_for_manual_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir) / "wiki"
            run_script("init_wiki.py", "--root", str(root), "--title", "Weak Inbox Wiki")
            write_text(root / "normalized" / "inbox" / "2026-06-20-weak-item.md", "# Weak Item\n\nshort")
            write_text(
                root / "normalized" / "inbox" / "2026-06-20-weak-item.json",
                json.dumps({
                    "kind": "web",
                    "adapter": "generic",
                    "title": "Weak Item",
                    "url": "",
                }, ensure_ascii=False, indent=2),
            )

            run_script("build_inbox.py", "--root", str(root))

            inbox_html = (root / "output" / "inbox" / "index.html").read_text(encoding="utf-8")
            self.assertIn("weak", inbox_html)
            self.assertIn("Too little information was extracted. Check the article body and source details manually first.", inbox_html)

    def test_clip_url_wait_mode_polls_until_content_is_ready(self) -> None:
        class PollingHandler(http.server.BaseHTTPRequestHandler):
            counter = 0

            def do_GET(self) -> None:
                type(self).counter += 1
                if type(self).counter == 1:
                    body = """
                    <html>
                      <body>
                        <main>
                          <h1>Loading Article</h1>
                          <p>Loading...</p>
                        </main>
                      </body>
                    </html>
                    """
                else:
                    body = """
                    <html>
                      <head>
                        <meta property="og:site_name" content="Polling Blog">
                        <meta name="author" content="Retry Author">
                      </head>
                      <body>
                        <main>
                          <h1>Loaded Article</h1>
                          <p>This is the fully loaded article body after the page finishes rendering and exposes the main content.</p>
                          <p>It should be long enough for ThinkWiki to treat the capture as ready instead of leaving it in a weak or review state.</p>
                        </main>
                      </body>
                    </html>
                    """
                payload = textwrap.dedent(body).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, format: str, *args: object) -> None:
                return

        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir) / "wiki"
            run_script("init_wiki.py", "--root", str(root), "--title", "Wait Wiki")

            with serve_handler(PollingHandler) as base_url:
                result = run_script(
                    "clip.py",
                    "--root",
                    str(root),
                    "--url",
                    f"{base_url}/article.html",
                    "--mode",
                    "wait",
                    "--wait-seconds",
                    "2",
                )

            metadata_files = sorted((root / "normalized" / "inbox").glob("*.json"))
            self.assertEqual(len(metadata_files), 1)
            payload = json.loads(metadata_files[0].read_text(encoding="utf-8"))
            self.assertEqual(payload["captureMode"], "wait")
            self.assertEqual(payload["captureState"], "wait_completed")
            self.assertGreaterEqual(payload["captureAttempts"], 2)
            self.assertIn("Capture mode: wait", result.stdout)
            self.assertIn("Capture state: wait_completed", result.stdout)
            inbox_html = (root / "output" / "inbox" / "index.html").read_text(encoding="utf-8")
            self.assertIn("wait_completed", inbox_html)
            self.assertIn("Polling Blog", inbox_html)

    def test_clip_url_loading_placeholder_reason_is_exposed_in_review(self) -> None:
        class LoadingHandler(http.server.BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                body = """
                <html>
                  <body>
                    <main>
                      <h1>Loading Article</h1>
                      <p>Loading...</p>
                    </main>
                  </body>
                </html>
                """
                payload = textwrap.dedent(body).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, format: str, *args: object) -> None:
                return

        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir) / "wiki"
            run_script("init_wiki.py", "--root", str(root), "--title", "Reason Wiki")

            with serve_handler(LoadingHandler) as base_url:
                result = run_script(
                    "clip.py",
                    "--root",
                    str(root),
                    "--url",
                    f"{base_url}/loading.html",
                )

            metadata_files = sorted((root / "normalized" / "inbox").glob("*.json"))
            self.assertEqual(len(metadata_files), 1)
            payload = json.loads(metadata_files[0].read_text(encoding="utf-8"))
            self.assertEqual(payload["captureState"], "needs_review")
            self.assertEqual(payload["captureReason"], "loading_placeholder")
            self.assertIn("Capture reason: loading_placeholder", result.stdout)
            inbox_html = (root / "output" / "inbox" / "index.html").read_text(encoding="utf-8")
            self.assertIn("loading_placeholder", inbox_html)
            self.assertIn("The page still looks like a loading placeholder", inbox_html)

    def test_clip_url_media_always_downloads_and_rewrites_markdown(self) -> None:
        tiny_png = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9WnR0p8AAAAASUVORK5CYII="
        )
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir) / "wiki"
            site_root = Path(tmp_dir) / "site"
            run_script("init_wiki.py", "--root", str(root), "--title", "Media Wiki")
            write_text(
                site_root / "article.html",
                """
                <html>
                  <head>
                    <meta property="og:site_name" content="Image Blog">
                  </head>
                  <body>
                    <main>
                      <h1>Image Article</h1>
                      <p>This article includes an image.</p>
                      <img src="/pixel.png" alt="pixel">
                    </main>
                  </body>
                </html>
                """,
            )
            (site_root / "pixel.png").parent.mkdir(parents=True, exist_ok=True)
            (site_root / "pixel.png").write_bytes(tiny_png)

            with serve_directory(site_root) as base_url:
                result = run_script(
                    "clip.py",
                    "--root",
                    str(root),
                    "--url",
                    f"{base_url}/article.html",
                    "--media",
                    "always",
                )

            metadata_files = sorted((root / "normalized" / "inbox").glob("*.json"))
            self.assertEqual(len(metadata_files), 1)
            payload = json.loads(metadata_files[0].read_text(encoding="utf-8"))
            self.assertEqual(payload["mediaPolicy"], "always")
            self.assertEqual(payload["mediaStatus"], "localized")
            self.assertEqual(payload["mediaCount"], 1)
            self.assertEqual(payload["localizedMediaCount"], 1)
            self.assertIn("Media status: localized (1/1)", result.stdout)
            media_dir = root / str(payload["mediaDir"])
            self.assertTrue(media_dir.exists())
            normalized_files = sorted((root / "normalized" / "inbox").glob("*.md"))
            self.assertEqual(len(normalized_files), 1)
            normalized_text = normalized_files[0].read_text(encoding="utf-8")
            self.assertIn("../assets/inbox/", normalized_text)
            self.assertNotRegex(normalized_text, r"!\[[^\]]*\]\(https?://")
            inbox_html = (root / "output" / "inbox" / "index.html").read_text(encoding="utf-8")
            self.assertIn("localized", inbox_html)
            self.assertIn("Media files", inbox_html)

    def test_viewer_distinguishes_page_links_and_file_links(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir) / "wiki"
            write_text(root / ".wiki-schema.md", "# marker")
            (root / "raw" / "articles").mkdir(parents=True, exist_ok=True)
            (root / "output" / "viewer").mkdir(parents=True, exist_ok=True)
            (root / "wiki" / "sources").mkdir(parents=True, exist_ok=True)
            (root / "wiki" / "topics").mkdir(parents=True, exist_ok=True)
            (root / "raw" / "articles" / "platform.docx").write_text("raw", encoding="utf-8")

            write_text(
                root / "wiki" / "topics" / "platform.md",
                """
                ---
                title: Platform
                type: topic
                created: 2026-06-15
                updated: 2026-06-15
                summary: Topic summary.
                sources:
                  - wiki/sources/platform-spec.md
                tags:
                  - topic
                confidence: mixed
                status: active
                ---

                # Platform
                """,
            )
            write_text(
                root / "wiki" / "sources" / "platform-spec.md",
                """
                ---
                title: Platform Spec
                type: source
                created: 2026-06-15
                updated: 2026-06-15
                summary: Source summary.
                sources:
                  - raw/articles/platform.docx
                tags:
                  - source
                confidence: extracted
                status: active
                ---

                # Platform Spec

                ## Connections

                - [Platform Topic](../topics/platform.md)
                - [Raw Doc](../../raw/articles/platform.docx)
                """,
            )

            run_script("build_viewer.py", "--root", str(root))
            payload = json.loads((root / "output" / "viewer" / "viewer.json").read_text(encoding="utf-8"))
            page = next(item for item in payload["pages"] if item["id"] == "wiki/sources/platform-spec.md")
            section = next(item for item in page["sections"] if item["title"] == "Connections")

            self.assertIn(
                {
                    "label": "platform.md",
                    "raw": "../topics/platform.md",
                    "targetId": "wiki/topics/platform.md",
                    "href": "",
                },
                section["links"],
            )
            self.assertIn(
                {
                    "label": "platform.docx",
                    "raw": "../../raw/articles/platform.docx",
                    "targetId": "",
                    "href": "../../raw/articles/platform.docx",
                },
                section["links"],
            )
            html_text = (root / "output" / "viewer" / "index.html").read_text(encoding="utf-8")
            self.assertIn("../graph/index.html#node=", html_text)
            self.assertTrue((root / "output" / "index.html").exists())

    def test_query_command_reports_output_hub_when_present(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir) / "wiki"
            write_text(root / ".wiki-schema.md", "# marker")
            (root / "output" / "viewer").mkdir(parents=True, exist_ok=True)
            write_text(root / "output" / "viewer" / "index.html", "<html><body>viewer</body></html>")

            result = run_script(
                "query_wiki.py",
                "--root",
                str(root),
                "--question",
                "What is alpha?",
                "--answer",
                "Alpha is the first concept.",
            )

            self.assertIn("Created wiki/queries/what-is-alpha.md", result.stdout)
            self.assertIn("Output hub: output/index.html", result.stdout)
            self.assertIn("Output hub URI: file://", result.stdout)
            self.assertTrue((root / "output" / "index.html").exists())

    def test_ingest_reports_output_hub_when_viewer_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir) / "wiki"
            source = Path(tmp_dir) / "alpha.md"
            write_text(source, "# Alpha\n\nAlpha summary.")
            run_script("init_wiki.py", "--root", str(root), "--title", "Test Wiki")
            (root / "output" / "viewer").mkdir(parents=True, exist_ok=True)
            write_text(root / "output" / "viewer" / "index.html", "<html><body>viewer</body></html>")

            result = run_script("ingest.py", "--root", str(root), "--source", str(source))

            self.assertIn("Ingested Alpha", result.stdout)
            self.assertIn("Output hub: output/index.html", result.stdout)
            self.assertIn("Output hub URI: file://", result.stdout)
            self.assertTrue((root / "output" / "index.html").exists())

    def test_serve_print_urls_lists_workspace_home(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir) / "wiki"
            write_text(root / ".wiki-schema.md", "# marker")
            write_text(root / "output" / "index.html", "<html><body>ThinkWiki Outputs</body></html>")

            result = run_script("serve_outputs.py", "--root", str(root), "--print-urls")

            self.assertIn("ThinkWiki output server: http://127.0.0.1:8765", result.stdout)
            self.assertIn("Workspace Home: http://127.0.0.1:8765/index.html", result.stdout)
            self.assertIn("OpenClaw browser: openclaw browser --browser-profile openclaw open http://127.0.0.1:8765/index.html", result.stdout)

    def test_serve_command_serves_output_hub(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir) / "wiki"
            write_text(root / ".wiki-schema.md", "# marker")
            write_text(root / "output" / "index.html", "<html><body>ThinkWiki Outputs</body></html>")

            proc = subprocess.Popen(
                [
                    runtime_python(),
                    str(REPO_ROOT / "scripts" / "serve_outputs.py"),
                    "--root",
                    str(root),
                    "--port",
                    "28765",
                ],
                cwd=REPO_ROOT,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            try:
                deadline = time.time() + 5
                while time.time() < deadline:
                    try:
                        response = urllib.request.urlopen("http://127.0.0.1:28765/index.html")
                        body = response.read().decode("utf-8")
                        self.assertIn("ThinkWiki Outputs", body)
                        return
                    except urllib.error.URLError:
                        time.sleep(0.05)
                self.fail("Timed out waiting for ThinkWiki serve command")
            finally:
                proc.terminate()
                proc.wait(timeout=5)

    def test_serve_fails_when_output_directory_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir) / "wiki"
            write_text(root / ".wiki-schema.md", "# marker")

            result = run_thinkwiki("serve", "--root", str(root), "--print-urls", check=False)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Output directory not found", result.stderr)

    def test_viewer_prints_serve_hint(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir) / "wiki"
            write_text(root / ".wiki-schema.md", "# marker")
            write_text(root / "index.md", "# Demo Wiki")
            (root / "wiki" / "sources").mkdir(parents=True, exist_ok=True)
            write_text(
                root / "wiki" / "sources" / "alpha.md",
                """
                ---
                title: Alpha Source
                type: source
                created: 2026-06-19
                updated: 2026-06-19
                summary: Alpha summary.
                sources:
                  - raw/articles/alpha.md
                confidence: extracted
                status: active
                ---

                # Alpha Source
                """,
            )

            result = run_script("build_viewer.py", "--root", str(root))

            self.assertIn("Browse via HTTP:", result.stdout)
            self.assertIn("python scripts/thinkwiki serve --root", result.stdout)
            self.assertIn("http://127.0.0.1:8765/index.html", result.stdout)


class ThinkWikiSecurityTest(unittest.TestCase):
    def test_llm_and_embed_disabled_without_configuration(self) -> None:
        import importlib

        import ai_config

        ai_keys = [
            key
            for key in os.environ
            if key.startswith(("THINKWIKI_", "MINIMAX_", "SILICONFLOW_", "BGE_"))
        ]
        preserved = {key: os.environ[key] for key in ai_keys}
        try:
            for key in ai_keys:
                del os.environ[key]
            importlib.reload(ai_config)
            self.assertFalse(ai_config.llm_is_configured())
            self.assertFalse(ai_config.embed_is_configured())
        finally:
            for key in ai_keys:
                os.environ.pop(key, None)
            os.environ.update(preserved)
            importlib.reload(ai_config)

    def test_llm_requires_complete_configuration(self) -> None:
        import importlib

        import ai_config

        ai_keys = [
            key
            for key in os.environ
            if key.startswith(("THINKWIKI_", "MINIMAX_", "SILICONFLOW_", "BGE_"))
        ]
        preserved = {key: os.environ[key] for key in ai_keys}
        try:
            for key in ai_keys:
                del os.environ[key]
            importlib.reload(ai_config)
            os.environ["THINKWIKI_LLM_API_KEY"] = "test-key"
            os.environ["THINKWIKI_LLM_BASE_URL"] = "https://api.example.com/v1/chat/completions"
            os.environ["THINKWIKI_LLM_MODEL"] = "demo-model"
            importlib.reload(ai_config)
            self.assertTrue(ai_config.llm_is_configured())
            config = ai_config.resolve_llm_config()
            self.assertEqual(config.model, "demo-model")
        finally:
            for key in ai_keys:
                os.environ.pop(key, None)
            os.environ.update(preserved)
            importlib.reload(ai_config)

    def test_embed_defaults_to_siliconflow_when_only_key_is_set(self) -> None:
        import importlib

        import ai_config

        ai_keys = [
            key
            for key in os.environ
            if key.startswith(("THINKWIKI_", "MINIMAX_", "SILICONFLOW_", "BGE_"))
        ]
        preserved = {key: os.environ[key] for key in ai_keys}
        try:
            for key in ai_keys:
                del os.environ[key]
            importlib.reload(ai_config)
            os.environ["THINKWIKI_EMBED_API_KEY"] = "test-key"
            importlib.reload(ai_config)
            self.assertTrue(ai_config.embed_is_configured())
            config = ai_config.resolve_embed_config()
            self.assertEqual(config.base_urls, (ai_config.DEFAULT_EMBED_BASE_URL,))
            self.assertEqual(config.model, ai_config.DEFAULT_EMBED_MODEL)
        finally:
            for key in ai_keys:
                os.environ.pop(key, None)
            os.environ.update(preserved)
            importlib.reload(ai_config)

    def test_legacy_env_vars_are_ignored(self) -> None:
        import importlib

        import ai_config

        ai_keys = [
            key
            for key in os.environ
            if key.startswith(("THINKWIKI_", "MINIMAX_", "SILICONFLOW_", "BGE_"))
        ]
        preserved = {key: os.environ[key] for key in ai_keys}
        try:
            for key in ai_keys:
                del os.environ[key]
            os.environ["MINIMAX_API_KEY"] = "legacy-key"
            os.environ["MINIMAX_BASE_URL"] = "https://api.example.com/v1/chat/completions"
            os.environ["MINIMAX_MODEL"] = "legacy-model"
            os.environ["SILICONFLOW_API_KEY"] = "legacy-embed-key"
            importlib.reload(ai_config)
            self.assertFalse(ai_config.llm_is_configured())
            self.assertFalse(ai_config.embed_is_configured())
        finally:
            for key in ai_keys:
                os.environ.pop(key, None)
            os.environ.update(preserved)
            importlib.reload(ai_config)

    def test_url_safety_blocks_loopback_fetch(self) -> None:
        from url_safety import validate_fetch_url

        with self.assertRaises(ValueError):
            validate_fetch_url("http://127.0.0.1/metadata")

    def test_url_safety_blocks_private_network_fetch(self) -> None:
        from url_safety import validate_fetch_url

        with self.assertRaises(ValueError):
            validate_fetch_url("http://192.168.1.10/internal")

    def test_serve_refuses_non_loopback_without_allow_lan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir) / "wiki"
            write_text(root / ".wiki-schema.md", "# marker")
            write_text(root / "output" / "index.html", "<html><body>ThinkWiki Outputs</body></html>")

            result = subprocess.run(
                [
                    runtime_python(),
                    str(REPO_ROOT / "scripts" / "serve_outputs.py"),
                    "--root",
                    str(root),
                    "--host",
                    "0.0.0.0",
                    "--print-urls",
                ],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("--allow-lan", result.stderr)


if __name__ == "__main__":
    unittest.main()
