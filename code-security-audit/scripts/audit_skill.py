#!/usr/bin/env python3
"""Audit an OpenClaw/Agent Skill package.

This wrapper focuses on Skill-specific checks and delegates code/security pattern
scanning to scripts/semgrep_scan.js when available. Reports intentionally avoid
printing matched source lines to reduce secondary secret leakage.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

SKILL_ROOT = Path(__file__).resolve().parents[1]
SEMGREP_SCAN = SKILL_ROOT / "scripts" / "semgrep_scan.js"
DEFAULT_REPORT_DIR = Path.home() / "workspaces" / "ai_agent_self_upgrade" / "code-security-audit"
DEFAULT_EXCLUDES = {
    ".git", ".svn", ".hg", "node_modules", ".venv", "venv", "env", "__pycache__",
    "dist", "build", "coverage", ".next", ".nuxt", "target", ".cache", ".npm",
    ".pnpm-store", ".pytest_cache", ".mypy_cache",
}
TEXT_EXTENSIONS = {
    ".md", ".txt", ".json", ".json5", ".yaml", ".yml", ".toml", ".ini", ".conf",
    ".config", ".env", ".py", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".sh",
    ".bash", ".zsh", ".fish", ".ps1", ".sql", ".xml", ".html", ".css", ".scss",
    ".java", ".go", ".rs", ".php", ".rb", ".cs", ".c", ".cc", ".cpp", ".h", ".hpp",
}
EXTRA_DOC_NAMES = {
    "README.md", "CHANGELOG.md", "CONTRIBUTING.md", "INSTALL.md", "INSTALLATION_GUIDE.md",
    "QUICK_REFERENCE.md", "SUMMARY.md",
}
SEVERITY_ORDER = {"INFO": 0, "MINOR": 1, "MAJOR": 2, "CRITICAL": 3, "BLOCKER": 4}

DANGEROUS_COMMAND_RULES = [
    ("skill.danger.rm-root", "BLOCKER", re.compile(r"\brm\s+-rf\s+(?:/|/\*)\b"), "疑似删除根目录/根目录通配符。", "禁止在 Skill 中出现不可恢复删除命令；改用 trash/交互确认/白名单路径。"),
    ("skill.danger.rm-home", "CRITICAL", re.compile(r"\brm\s+-rf\s+(?:~|\$HOME|/home/)[^\n]*"), "疑似递归删除用户目录。", "删除动作必须显式确认，优先使用 trash，并限制到临时目录。"),
    ("skill.danger.disk-format", "BLOCKER", re.compile(r"\b(mkfs(?:\.[a-z0-9]+)?|wipefs|sgdisk\s+--zap-all)\b"), "疑似磁盘格式化/擦除命令。", "除非技能就是磁盘运维且有强确认流程，否则移除。"),
    ("skill.danger.block-write", "BLOCKER", re.compile(r"(?:dd\s+if=|>\s*)/dev/(?:sd[a-z]|nvme\d+n\d+|mapper/)"), "疑似直接写入块设备。", "避免直接块设备写入；需要时加入只读检查、确认门和恢复方案。"),
    ("skill.danger.remote-shell", "CRITICAL", re.compile(r"\b(?:curl|wget)\b[^\n|;]*(?:\||\$\()\s*(?:sudo\s+)?(?:bash|sh|zsh)\b"), "疑似下载远程脚本后直接执行。", "改为下载到文件、校验签名/哈希、人工审阅后执行。"),
    ("skill.danger.chmod-777", "MAJOR", re.compile(r"\bchmod\s+(?:-R\s+)?777\b"), "发现 chmod 777。", "按最小权限设置，例如 600/700/755，避免全局可写。"),
    ("skill.danger.fork-bomb", "BLOCKER", re.compile(r":\(\)\s*\{\s*:\|:\s*&\s*\}\s*;\s*:"), "发现 fork bomb 特征。", "移除该内容；文档示例也应转义并注明禁止执行。"),
]
SECRET_HINT_RULES = [
    ("skill.secret.assignment", "CRITICAL", re.compile(r"\b(?:api[_-]?key|secret|token|password|passwd|pwd|access[_-]?key|private[_-]?key|client[_-]?secret)\b\s*[:=]\s*['\"]?[^'\"\s]{8,}", re.I), "疑似硬编码敏感字段。", "改用环境变量/密钥管理系统；若已泄露请立即轮换。"),
    ("skill.secret.aws-access-key", "CRITICAL", re.compile(r"AKIA[0-9A-Z]{16}"), "疑似 AWS Access Key。", "立即轮换密钥并检查提交历史。"),
    ("skill.secret.github-token", "CRITICAL", re.compile(r"\b(?:ghp|github_pat)_[A-Za-z0-9_]{20,}\b"), "疑似 GitHub Token。", "立即吊销/轮换 token，改用安全配置。"),
    ("skill.secret.private-key", "BLOCKER", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA |)?PRIVATE KEY-----"), "发现私钥块。", "Skill 包不应携带私钥；移出仓库并轮换。"),
]

@dataclass
class Issue:
    file: str
    line: int
    severity: str
    rule: str
    message: str
    fix: str
    category: str = "skill-audit"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="审计 OpenClaw/Agent Skill 目录：结构、危险命令、敏感信息和代码安全基线。")
    p.add_argument("skill_path", help="Skill 目录路径")
    p.add_argument("-o", "--output", help="报告输出路径，支持 .md/.json；默认写入 ai_agent_self_upgrade/code-security-audit/")
    p.add_argument("--format", choices=["markdown", "json"], default=None, help="报告格式；默认根据 output 后缀推断，未指定 output 时为 markdown")
    p.add_argument("--engine", choices=["auto", "semgrep", "builtin", "none"], default="auto", help="代码扫描引擎；none 只做 Skill 专项审计")
    p.add_argument("--severities", default="BLOCKER,CRITICAL,MAJOR,MINOR,INFO", help="保留的风险等级，逗号分隔")
    p.add_argument("--exclude", action="append", default=[], help="额外排除目录/路径片段，可重复传入或逗号分隔")
    p.add_argument("--max-file-size-kb", type=int, default=1024, help="专项文本扫描的单文件大小上限，默认 1024KB")
    p.add_argument("--no-delegate", action="store_true", help="不调用 semgrep_scan.js，只运行 Python 专项规则")
    p.add_argument("--strict", action="store_true", help="严格模式：MAJOR 也返回非零退出码")
    p.add_argument("--print-issues", action="store_true", help="终端输出问题明细；默认只输出汇总和报告路径")
    return p.parse_args()


def normalize_csv(items: Iterable[str]) -> list[str]:
    out: list[str] = []
    for item in items:
        out.extend(x.strip() for x in str(item).split(",") if x.strip())
    return out


def allowed_severity_filter(raw: str) -> set[str]:
    values = {x.upper() for x in normalize_csv([raw])}
    return values or set(SEVERITY_ORDER)


def should_skip(path: Path, root: Path, excludes: set[str]) -> bool:
    rel_parts = path.relative_to(root).parts if path != root else ()
    return any(part in excludes for part in rel_parts) or any(str(path).endswith(os.sep + ex) for ex in excludes)


def is_text_file(path: Path) -> bool:
    return path.name == "SKILL.md" or path.name.startswith(".env") or path.suffix.lower() in TEXT_EXTENSIONS


def iter_text_files(root: Path, excludes: set[str], max_bytes: int) -> Iterable[Path]:
    if root.is_file():
        if is_text_file(root) and root.stat().st_size <= max_bytes:
            yield root
        return
    for cur, dirs, files in os.walk(root):
        cur_path = Path(cur)
        dirs[:] = [d for d in dirs if d not in excludes and not should_skip(cur_path / d, root, excludes)]
        for name in files:
            p = cur_path / name
            try:
                if not should_skip(p, root, excludes) and is_text_file(p) and p.stat().st_size <= max_bytes:
                    yield p
            except OSError:
                continue


def safe_read(path: Path) -> list[str]:
    try:
        raw = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return []
    if "\x00" in raw:
        return []
    return raw.splitlines()


def is_probable_example(line: str) -> bool:
    stripped = line.strip()
    return (
        not stripped
        or stripped.startswith(("#", "//", "<!--"))
        or stripped.startswith(("- ", "* ", "> "))
        or stripped.startswith("`")
        or stripped.endswith("`")
        or "DANGEROUS_COMMAND_RULES" in line
        or "SECRET_HINT_RULES" in line
        or "re.compile" in line
        or "regex" in line.lower()
    )


def is_scanner_fixture(file: Path, line: str) -> bool:
    base = file.name
    if base == "smoke_test.js":
        return True
    if base == "audit_skill.py" and ("re.compile" in line or "DANGEROUS_COMMAND_RULES" in line or "SECRET_HINT_RULES" in line):
        return True
    return False


def add_issue(issues: list[Issue], file: Path, line: int, severity: str, rule: str, message: str, fix: str, category: str = "skill-audit") -> None:
    issues.append(Issue(str(file.resolve()), line, severity, rule, message, fix, category))


def audit_structure(root: Path) -> list[Issue]:
    issues: list[Issue] = []
    skill_md = root / "SKILL.md"
    if not skill_md.exists():
        add_issue(issues, root, 1, "BLOCKER", "skill.structure.missing-skill-md", "缺少必需的 SKILL.md。", "在 Skill 根目录创建 SKILL.md，并包含 YAML frontmatter 的 name/description。", "structure")
        return issues

    lines = safe_read(skill_md)
    text = "\n".join(lines[:80])
    if not text.startswith("---"):
        add_issue(issues, skill_md, 1, "MAJOR", "skill.structure.missing-frontmatter", "SKILL.md 未以 YAML frontmatter 开头。", "按 OpenClaw Skill 规范添加 --- / name / description / ---。", "structure")
    else:
        fm_end = None
        for idx, line in enumerate(lines[1:80], 2):
            if line.strip() == "---":
                fm_end = idx
                break
        frontmatter = "\n".join(lines[1:fm_end - 1]) if fm_end else ""
        if not fm_end:
            add_issue(issues, skill_md, 1, "MAJOR", "skill.structure.bad-frontmatter", "SKILL.md frontmatter 未闭合。", "补齐第二个 ---。", "structure")
        for key in ("name", "description"):
            if not re.search(rf"^{key}\s*:\s*\S+", frontmatter, re.M):
                add_issue(issues, skill_md, 1, "MAJOR", f"skill.structure.missing-{key}", f"SKILL.md frontmatter 缺少 {key}。", f"在 frontmatter 中添加 {key}: ...。", "structure")

    if len(lines) > 500:
        add_issue(issues, skill_md, 1, "MINOR", "skill.structure.skill-md-large", "SKILL.md 超过 500 行，可能浪费上下文窗口。", "将长篇参考资料移入 references/，SKILL.md 保留核心流程和导航。", "structure")

    for name in EXTRA_DOC_NAMES:
        p = root / name
        if p.exists():
            add_issue(issues, p, 1, "INFO", "skill.structure.extra-doc", f"发现额外文档 {name}。", "Skill 包应尽量精简；确需保留时确认不会干扰触发和维护。", "structure")

    for heavy in ("node_modules", ".venv", "venv"):
        p = root / heavy
        if p.exists() and p.is_dir():
            add_issue(issues, p, 1, "INFO", "skill.structure.heavy-runtime-dir", f"Skill 包内包含 {heavy} 运行时目录。", "如需发布/分享 Skill，建议排除运行时依赖，仅保留安装说明或锁定脚本。", "structure")

    return issues


def audit_text_patterns(root: Path, excludes: set[str], max_bytes: int) -> list[Issue]:
    issues: list[Issue] = []
    for file in iter_text_files(root, excludes, max_bytes):
        for idx, line in enumerate(safe_read(file), 1):
            if is_scanner_fixture(file, line):
                continue
            example = is_probable_example(line)
            for rule, sev, regex, msg, fix in DANGEROUS_COMMAND_RULES:
                if not example and regex.search(line):
                    add_issue(issues, file, idx, sev, rule, msg, fix, "dangerous-command")
            for rule, sev, regex, msg, fix in SECRET_HINT_RULES:
                if not example and regex.search(line):
                    add_issue(issues, file, idx, sev, rule, msg, fix, "secret")
    return issues


def run_delegate_scan(root: Path, engine: str, severities: str, excludes: list[str], max_kb: int) -> tuple[list[Issue], str, str | None]:
    if engine == "none" or not SEMGREP_SCAN.exists():
        return [], "none", None
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    cmd = [
        "node", str(SEMGREP_SCAN),
        "--path", str(root),
        "--engine", engine,
        "--severities", severities,
        "--output", str(tmp_path),
        "--max-file-size-kb", str(max_kb),
    ]
    for ex in excludes:
        cmd += ["--exclude", ex]
    proc = subprocess.run(cmd, cwd=str(SKILL_ROOT), text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if not tmp_path.exists() or tmp_path.stat().st_size == 0:
        return [], "delegate-failed", (proc.stderr or proc.stdout).strip()
    try:
        data = json.loads(tmp_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [], "delegate-failed", f"无法解析委托扫描 JSON：{exc}"
    finally:
        try:
            tmp_path.unlink()
        except OSError:
            pass
    engine_used = data.get("engine", engine)
    issues = []
    for x in data.get("issues", []):
        issues.append(Issue(
            file=str(Path(x.get("file", str(root))).resolve()),
            line=int(x.get("line", 1) or 1),
            severity=str(x.get("severity", "INFO")).upper(),
            rule=str(x.get("rule", "delegate.unknown")),
            message=str(x.get("message", "委托扫描发现问题。")),
            fix=str(x.get("fix", "参考扫描器建议修复。")),
            category=f"delegate:{engine_used}",
        ))
    return issues, str(engine_used), None


def filter_dedupe(issues: list[Issue], allowed: set[str]) -> list[Issue]:
    seen = set()
    out: list[Issue] = []
    for i in issues:
        if i.severity not in allowed:
            continue
        key = (i.file, i.line, i.rule, i.message)
        if key in seen:
            continue
        seen.add(key)
        out.append(i)
    return sorted(out, key=lambda x: (-SEVERITY_ORDER.get(x.severity, 0), x.file, x.line, x.rule))


def summarize(root: Path, issues: list[Issue], engine: str, delegate_error: str | None) -> dict:
    severities = {k: 0 for k in ["BLOCKER", "CRITICAL", "MAJOR", "MINOR", "INFO"]}
    categories: dict[str, int] = {}
    for issue in issues:
        severities[issue.severity] = severities.get(issue.severity, 0) + 1
        categories[issue.category] = categories.get(issue.category, 0) + 1
    return {
        "scanner": "audit_skill",
        "skillPath": str(root.resolve()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "delegateEngine": engine,
        "delegateError": delegate_error,
        "total": len(issues),
        "severities": severities,
        "categories": categories,
        "issues": [asdict(i) for i in issues],
        "securityNote": "报告不输出命中源码原文，只包含文件、行号、规则、描述和修复建议。",
    }


def render_markdown(summary: dict) -> str:
    s = "# audit_skill 审计报告\n\n"
    s += "## 审计概览\n\n"
    s += f"- 扫描器：{summary['scanner']}\n"
    s += f"- Skill 路径：`{summary['skillPath']}`\n"
    s += f"- 审计时间：{summary['timestamp']}\n"
    s += f"- 委托扫描引擎：{summary['delegateEngine']}\n"
    if summary.get("delegateError"):
        s += f"- 委托扫描异常：`{summary['delegateError']}`\n"
    s += f"- 总问题数：{summary['total']}\n"
    for sev in ["BLOCKER", "CRITICAL", "MAJOR", "MINOR", "INFO"]:
        s += f"- {sev}：{summary['severities'].get(sev, 0)}\n"
    s += "\n> 安全说明：报告默认不输出命中源码内容，只给出文件、行号、规则与修复建议，避免二次泄露密钥。\n\n"

    if not summary["issues"]:
        s += "## ✅ 未发现问题\n"
        return s

    labels = {"BLOCKER": "🔴 高危", "CRITICAL": "🟠 严重", "MAJOR": "🟡 重要", "MINOR": "🟢 次要", "INFO": "🔵 提示"}
    s += "## 问题详情\n\n"
    for sev in ["BLOCKER", "CRITICAL", "MAJOR", "MINOR", "INFO"]:
        arr = [i for i in summary["issues"] if i["severity"] == sev]
        if not arr:
            continue
        s += f"### {labels[sev]} {sev}（{len(arr)}）\n\n"
        for n, i in enumerate(arr, 1):
            s += f"{n}. **文件**：`{i['file']}`，**行号**：{i['line']}\n"
            s += f"   - **分类**：{i['category']}\n"
            s += f"   - **规则**：{i['rule']}\n"
            s += f"   - **描述**：{i['message']}\n"
            s += f"   - **修复建议**：{i['fix']}\n\n"
    return s


def choose_output(root: Path, requested: str | None, fmt: str | None) -> tuple[Path, str]:
    if requested:
        out = Path(requested).expanduser().resolve()
        if fmt is None:
            fmt = "json" if out.suffix.lower() == ".json" else "markdown"
        return out, fmt
    DEFAULT_REPORT_DIR.mkdir(parents=True, exist_ok=True)
    safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "-", root.name).strip("-") or "skill"
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    fmt = fmt or "markdown"
    suffix = "json" if fmt == "json" else "md"
    return DEFAULT_REPORT_DIR / f"audit-skill-{safe_name}-{ts}.{suffix}", fmt


def write_report(summary: dict, out: Path, fmt: str) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    if fmt == "json":
        out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    else:
        out.write_text(render_markdown(summary), encoding="utf-8")


def print_summary(summary: dict, report_path: Path, print_issues: bool) -> None:
    print("\n📊 audit_skill 审计完成")
    print(f"Skill：{summary['skillPath']}")
    print(f"委托引擎：{summary['delegateEngine']}")
    print(f"总问题数：{summary['total']}")
    for sev in ["BLOCKER", "CRITICAL", "MAJOR", "MINOR", "INFO"]:
        print(f"{sev}: {summary['severities'].get(sev, 0)}")
    print(f"📝 报告：{report_path}")
    if print_issues and summary["issues"]:
        print("\n问题明细（不含源码片段）：")
        for i in summary["issues"]:
            print(f"- [{i['severity']}] {i['file']}:{i['line']} {i['rule']} - {i['message']}")


def main() -> int:
    args = parse_args()
    root = Path(args.skill_path).expanduser().resolve()
    if not root.exists():
        print(f"❌ Skill 路径不存在：{root}", file=sys.stderr)
        return 1
    if not root.is_dir():
        print(f"❌ Skill 路径不是目录：{root}", file=sys.stderr)
        return 1

    allowed = allowed_severity_filter(args.severities)
    excludes = set(DEFAULT_EXCLUDES) | set(normalize_csv(args.exclude))
    max_bytes = max(1, args.max_file_size_kb) * 1024

    issues: list[Issue] = []
    issues.extend(audit_structure(root))
    issues.extend(audit_text_patterns(root, excludes, max_bytes))

    delegate_engine = "none"
    delegate_error = None
    if not args.no_delegate and args.engine != "none":
        delegated, delegate_engine, delegate_error = run_delegate_scan(
            root, args.engine, args.severities, sorted(excludes), args.max_file_size_kb
        )
        issues.extend(delegated)

    issues = filter_dedupe(issues, allowed)
    summary = summarize(root, issues, delegate_engine, delegate_error)
    report_path, fmt = choose_output(root, args.output, args.format)
    write_report(summary, report_path, fmt)
    print_summary(summary, report_path, args.print_issues)

    blockers = summary["severities"].get("BLOCKER", 0) + summary["severities"].get("CRITICAL", 0)
    majors = summary["severities"].get("MAJOR", 0)
    if blockers:
        return 2
    if args.strict and majors:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

