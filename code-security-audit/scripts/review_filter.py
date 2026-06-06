#!/usr/bin/env python3
"""Filter code-security-audit JSON findings to reduce noisy false positives.

The filter is deterministic and offline. It borrows the hard-exclusion idea from
PR security review workflows: remove issue classes that are usually operational
noise for focused vulnerability review unless the caller explicitly keeps them.
It never prints matched source content.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

DEFAULT_EXCLUDED_CLASSES = {
    "dos",
    "rate-limit",
    "resource-leak",
    "open-redirect",
    "memory-safety",
}

PATTERNS: dict[str, list[re.Pattern[str]]] = {
    "dos": [
        re.compile(r"\b(denial of service|dos attack|resource exhaustion)\b", re.I),
        re.compile(r"\b(infinite|unbounded)\s+(loop|recursion)\b", re.I),
        re.compile(r"\b(redos|regular expression denial of service)\b", re.I),
    ],
    "rate-limit": [
        re.compile(r"\b(missing|lack of|no)\s+rate\s+limit", re.I),
        re.compile(r"\brate\s+limiting\s+(missing|required|not implemented)", re.I),
        re.compile(r"\bunlimited\s+(requests|calls|api)", re.I),
    ],
    "resource-leak": [
        re.compile(r"\b(resource|memory|file|connection)\s+leak", re.I),
        re.compile(r"\bunclosed\s+(resource|file|connection|socket)", re.I),
        re.compile(r"\b(close|cleanup|release)\s+(resource|file|connection)", re.I),
    ],
    "open-redirect": [
        re.compile(r"\b(open redirect|unvalidated redirect)\b", re.I),
        re.compile(r"\bredirect\s+(attack|exploit|vulnerability)\b", re.I),
    ],
    "memory-safety": [
        re.compile(r"\b(buffer|stack|heap)\s+overflow\b", re.I),
        re.compile(r"\b(out.?of.?bounds|oob)\b", re.I),
        re.compile(r"\b(use.?after.?free|double.?free|null.?pointer)\b", re.I),
        re.compile(r"\bmemory\s+(safety|corruption)\b", re.I),
    ],
}


@dataclass
class FilterStats:
    total_findings: int = 0
    excluded: int = 0
    kept: int = 0
    exclusion_breakdown: dict[str, int] = field(default_factory=dict)


def load_report(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        return {"findings": data, "total": len(data)}
    if not isinstance(data, dict):
        raise ValueError("input JSON must be an object or array")
    return data


def get_findings(report: dict[str, Any]) -> list[dict[str, Any]]:
    findings = report.get("findings") or report.get("results") or report.get("issues") or []
    return [f for f in findings if isinstance(f, dict)]


def finding_text(finding: dict[str, Any]) -> str:
    parts = []
    for key in ("id", "rule", "ruleId", "check_id", "message", "description", "title", "fix"):
        value = finding.get(key)
        if value is not None:
            parts.append(str(value))
    return "\n".join(parts)


def classify(finding: dict[str, Any], enabled_classes: set[str]) -> str | None:
    text = finding_text(finding)
    for cls in sorted(enabled_classes):
        for pattern in PATTERNS.get(cls, []):
            if pattern.search(text):
                return cls
    return None


def recompute_summary(report: dict[str, Any], findings: list[dict[str, Any]]) -> None:
    severities: dict[str, int] = {}
    for finding in findings:
        sev = str(finding.get("severity", "INFO")).upper()
        severities[sev] = severities.get(sev, 0) + 1
    report["findings"] = findings
    report["total"] = len(findings)
    report["severities"] = severities


def parse_classes(value: str | None) -> set[str]:
    if not value:
        return set(DEFAULT_EXCLUDED_CLASSES)
    classes = {item.strip() for item in value.split(",") if item.strip()}
    unknown = classes - set(PATTERNS)
    if unknown:
        raise ValueError(f"unknown classes: {', '.join(sorted(unknown))}")
    return classes


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Filter noisy security findings from a code-security-audit JSON report")
    parser.add_argument("input", help="Input JSON report from semgrep_scan.js or audit_skill.py")
    parser.add_argument("--output", "-o", help="Output JSON path; defaults to stdout")
    parser.add_argument("--exclude-classes", default=",".join(sorted(DEFAULT_EXCLUDED_CLASSES)), help="Comma-separated classes to exclude")
    parser.add_argument("--keep-classes", default="", help="Comma-separated classes to keep even if excluded by default")
    parser.add_argument("--stats-only", action="store_true", help="Print only filter statistics as JSON")
    args = parser.parse_args(argv)

    excluded_classes = parse_classes(args.exclude_classes)
    keep_classes = parse_classes(args.keep_classes) if args.keep_classes else set()
    enabled_classes = excluded_classes - keep_classes

    report = load_report(Path(args.input))
    findings = get_findings(report)
    stats = FilterStats(total_findings=len(findings))
    kept: list[dict[str, Any]] = []

    for finding in findings:
        cls = classify(finding, enabled_classes)
        if cls:
            stats.excluded += 1
            stats.exclusion_breakdown[cls] = stats.exclusion_breakdown.get(cls, 0) + 1
            continue
        kept.append(finding)
    stats.kept = len(kept)

    report["filter"] = {
        "tool": "review_filter.py",
        "excluded_classes": sorted(enabled_classes),
        "stats": asdict(stats),
    }
    recompute_summary(report, kept)

    output_obj: Any = asdict(stats) if args.stats_only else report
    text = json.dumps(output_obj, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(text + "\n", encoding="utf-8")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"review_filter.py: {exc}", file=sys.stderr)
        raise SystemExit(1)
