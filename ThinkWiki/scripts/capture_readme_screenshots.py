#!/usr/bin/env python3
from __future__ import annotations

"""
ThinkWiki Script: capture_readme_screenshots

Purpose:
- Capture repository screenshots from the demo wiki outputs for the README.

Usage:
- Run directly when refreshing repository assets.
- Run `python scripts/<script> --help` for direct CLI details when the file exposes its own arguments.
"""


import argparse
from pathlib import Path

from playwright.sync_api import sync_playwright


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Capture README screenshots from the ThinkWiki demo output pages.")
    parser.add_argument(
        "--demo-root",
        default="docs/demo-wiki",
        help="Demo wiki root that contains output/index.html plus the inbox, viewer, graph, and graph-report HTML pages",
    )
    parser.add_argument(
        "--assets-dir",
        default="docs/assets",
        help="Directory where README screenshot assets will be written",
    )
    return parser.parse_args()


def screenshot_specs(repo_root: Path, demo_root: Path, assets_dir: Path) -> list[dict[str, object]]:
    demo_output = (repo_root / demo_root / "output").resolve()
    return [
        {
            "url": (demo_output / "index.html").as_uri(),
            "output": (repo_root / assets_dir / "output-hub-preview.png").resolve(),
            "viewport": {"width": 1440, "height": 1180},
        },
        {
            "url": (demo_output / "inbox" / "index.html").as_uri() + "#ready",
            "output": (repo_root / assets_dir / "inbox-preview.png").resolve(),
            "viewport": {"width": 1440, "height": 1600},
        },
        {
            "url": (demo_output / "viewer" / "index.html").as_uri() + "#page=wiki%2Fconcepts%2Fai-native-team.md",
            "output": (repo_root / assets_dir / "viewer-preview.png").resolve(),
            "viewport": {"width": 1440, "height": 1080},
        },
        {
            "url": (demo_output / "graph" / "index.html").as_uri(),
            "output": (repo_root / assets_dir / "graph-preview.png").resolve(),
            "viewport": {"width": 1600, "height": 1080},
        },
        {
            "url": (demo_output / "graph" / "report.html").as_uri(),
            "output": (repo_root / assets_dir / "graph-report-preview.png").resolve(),
            "viewport": {"width": 1440, "height": 1500},
        },
    ]


def capture(repo_root: Path, demo_root: Path, assets_dir: Path) -> None:
    specs = screenshot_specs(repo_root, demo_root, assets_dir)
    for spec in specs:
        Path(spec["output"]).parent.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            for spec in specs:
                page = browser.new_page(viewport=spec["viewport"])
                page.goto(str(spec["url"]), wait_until="load")
                page.wait_for_timeout(1200)
                page.screenshot(path=str(spec["output"]))
                print(spec["output"])
                page.close()
        finally:
            browser.close()


def main() -> int:
    args = parse_args()
    repo_root = Path(__file__).resolve().parent.parent
    capture(repo_root, Path(args.demo_root), Path(args.assets_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
