#!/usr/bin/env bash
# 依赖漏洞扫描统一入口脚本
# 用法: dep_audit.sh <项目根目录> [语言: python|node|go|java|auto]
set -euo pipefail

PROJECT_DIR="${1:-.}"
LANG="${2:-auto}"
REPORT_FILE="${PROJECT_DIR}/dep-audit-results.json"

detect_lang() {
  local dir="$1"
  local langs=()
  [[ -f "$dir/requirements.txt" || -f "$dir/Pipfile" || -f "$dir/pyproject.toml" || -f "$dir/setup.py" ]] && langs+=("python")
  [[ -f "$dir/package.json" || -f "$dir/yarn.lock" || -f "$dir/pnpm-lock.yaml" ]] && langs+=("node")
  [[ -f "$dir/go.mod" ]] && langs+=("go")
  [[ -f "$dir/pom.xml" || -f "$dir/build.gradle" || -f "$dir/build.gradle.kts" ]] && langs+=("java")
  echo "${langs[*]}"
}

audit_python() {
  echo "=== Python 依赖审计 ==="
  if command -v pip-audit &>/dev/null; then
    echo "[pip-audit]"
    pip-audit --desc --format json -r "$PROJECT_DIR/requirements.txt" 2>/dev/null || \
    pip-audit --desc --format json "$PROJECT_DIR" 2>/dev/null || \
    echo '{"error": "pip-audit 执行失败，请检查 requirements.txt"}'
  elif command -v safety &>/dev/null; then
    echo "[safety]"
    safety check --json -r "$PROJECT_DIR/requirements.txt" 2>/dev/null || \
    echo '{"error": "safety 执行失败"}'
  else
    echo '{"warning": "未找到 pip-audit 或 safety，建议安装: pip install pip-audit"}'
  fi
}

audit_node() {
  echo "=== Node.js 依赖审计 ==="
  if [[ -f "$PROJECT_DIR/package-lock.json" ]] || [[ -f "$PROJECT_DIR/package.json" ]]; then
    (cd "$PROJECT_DIR" && npm audit --json 2>/dev/null) || echo '{"warning": "npm audit 需要 package-lock.json"}'
  elif [[ -f "$PROJECT_DIR/yarn.lock" ]]; then
    (cd "$PROJECT_DIR" && yarn audit --json 2>/dev/null) || echo '{"warning": "yarn audit 执行失败"}'
  elif [[ -f "$PROJECT_DIR/pnpm-lock.yaml" ]]; then
    (cd "$PROJECT_DIR" && pnpm audit --json 2>/dev/null) || echo '{"warning": "pnpm audit 执行失败"}'
  fi
}

audit_go() {
  echo "=== Go 依赖审计 ==="
  if command -v govulncheck &>/dev/null; then
    (cd "$PROJECT_DIR" && govulncheck ./... 2>/dev/null) || echo '{"warning": "govulncheck 执行失败"}'
  else
    echo '{"warning": "未找到 govulncheck，建议安装: go install golang.org/x/vuln/cmd/govulncheck@latest"}'
  fi
}
