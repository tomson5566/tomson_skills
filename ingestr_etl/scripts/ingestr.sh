#!/usr/bin/env bash
# ingestr.sh - ingestr 二进制 wrapper
# 用法：
#   scripts/ingestr.sh --version
#   scripts/ingestr.sh ingest --source-uri ... --dest-uri ... --yes
#   scripts/ingestr.sh server --port 8080
#   scripts/ingestr.sh install   # 显式安装
#
# 搜索顺序：
#   1. $INGESTR_BIN 环境变量（直接覆盖）
#   2. ./ingestr（当前目录）
#   3. 仓库附带的 /home/tangzhiang/.copaw/workspaces/data_etl_agent/docs/ingestr_Linux_x86_64.tar.gz
#   4. /usr/local/bin/ingestr
#   5. $(go env GOPATH)/bin/ingestr
#   6. pip install ingestr（最后兜底）
#
# 安装路径：
#   - 优先解包附带 tar.gz 到 ~/.local/bin/ingestr
#   - 或 pip install --user ingestr

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_ROOT="$(cd "$SKILL_DIR/../.." && pwd)"
BUNDLED_TAR="$REPO_ROOT/docs/ingestr_Linux_x86_64.tar.gz"
BUNDLED_ZIP="$REPO_ROOT/docs/ingestr-1.0.21.zip"
INSTALL_DIR="${INGESTR_INSTALL_DIR:-$HOME/.local/bin}"

log() { printf '\033[1;34m[ingestr.sh]\033[0m %s\n' "$*" >&2; }
warn() { printf '\033[1;33m[ingestr.sh]\033[0m %s\n' "$*" >&2; }
err() { printf '\033[1;31m[ingestr.sh]\033[0m %s\n' "$*" >&2; }

find_binary() {
    # 1. 显式覆盖
    if [[ -n "${INGESTR_BIN:-}" && -x "$INGESTR_BIN" ]]; then
        echo "$INGESTR_BIN"; return 0
    fi

    # 2. 当前目录
    if [[ -x "./ingestr" ]]; then
        echo "$(pwd)/ingestr"; return 0
    fi

    # 3. /usr/local/bin
    if [[ -x "/usr/local/bin/ingestr" ]]; then
        echo "/usr/local/bin/ingestr"; return 0
    fi

    # 4. go bin
    if command -v go >/dev/null 2>&1; then
        local gopath
        gopath="$(go env GOPATH 2>/dev/null || true)"
        if [[ -n "$gopath" && -x "$gopath/bin/ingestr" ]]; then
            echo "$gopath/bin/ingestr"; return 0
        fi
    fi

    # 5. pip user bin
    if command -v python3 >/dev/null 2>&1; then
        local user_bin
        user_bin="$(python3 -m site --user-base 2>/dev/null)/bin/ingestr"
        if [[ -x "$user_bin" ]]; then
            echo "$user_bin"; return 0
        fi
    fi

    return 1
}

install_bundled_binary() {
    if [[ ! -f "$BUNDLED_TAR" ]]; then
        err "未找到打包的二进制：$BUNDLED_TAR"
        return 1
    fi
    mkdir -p "$INSTALL_DIR"
    local tmp
    tmp="$(mktemp -d)"
    log "解包 $BUNDLED_TAR 到 $tmp ..."
    tar xzf "$BUNDLED_TAR" -C "$tmp"
    install -m 0755 "$tmp/ingestr" "$INSTALL_DIR/ingestr"
    rm -rf "$tmp"
    log "已安装到 $INSTALL_DIR/ingestr"
    export PATH="$INSTALL_DIR:$PATH"
    echo "$INSTALL_DIR/ingestr"
}

install_via_pip() {
    if ! command -v pip >/dev/null 2>&1 && ! command -v pip3 >/dev/null 2>&1; then
        err "未找到 pip，且未打包二进制"
        return 1
    fi
    local pip_cmd
    pip_cmd="$(command -v pip3 || command -v pip)"
    log "运行 $pip_cmd install --user ingestr ..."
    "$pip_cmd" install --user ingestr
    local user_bin
    user_bin="$(python3 -m site --user-base)/bin/ingestr"
    echo "$user_bin"
}

install_ingestr() {
    if [[ -f "$BUNDLED_TAR" ]]; then
        install_bundled_binary && return 0
    fi
    install_via_pip
}

# 主流程
if [[ "${1:-}" == "install" || "${INGESTR_FORCE_INSTALL:-0}" == "1" ]]; then
    install_ingestr
    exit $?
fi

BIN="$(find_binary || true)"
if [[ -z "$BIN" ]]; then
    warn "未找到 ingestr，尝试自动安装 ..."
    BIN="$(install_ingestr || true)"
fi

if [[ -z "$BIN" || ! -x "$BIN" ]]; then
    err "无法定位或安装 ingestr。请手动安装："
    err "  1) pip install ingestr"
    err "  2) curl -LsSf https://getbruin.com/install/ingestr | sh"
    err "  3) 或设置 INGESTR_BIN=/path/to/ingestr"
    exit 127
fi

log "使用 $BIN"
exec "$BIN" "$@"
