#!/usr/bin/env bash
#===============================================================================
# server-show.sh — 查看单台服务器的完整档案（连接信息 + 巡检档案 + 凭证）
#
# 用法:
#   server-show.sh <host> [--user <name>] [--port <port>]
#
# 说明: 同 host 多账号时用 --user 区分；输出为 JSON，方便 agent 直接读取。
#===============================================================================
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/lib-common.sh"

HOST="" USER="" PORT=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --user|--username) USER="$2"; shift 2;;
    --port) PORT="$2"; shift 2;;
    -h|--help) sed -n '2,10p' "$0"; exit 0;;
    *) [[ -z "$HOST" ]] && HOST="$1" || rsc_die "未知参数: $1"; shift 1;;
  esac
done
[[ -n "$HOST" ]] || rsc_die "用法: server-show.sh <host> [--user <name>]"

rsc_server_json "$HOST" "$USER" "$PORT"
