#!/usr/bin/env bash
#===============================================================================
# server-remove.sh — 从档案库删除服务器
#
# 用法:
#   server-remove.sh <host> [--user <name>] [--port <port>] --yes
#
# 说明: 必须显式传 --yes 才会删除；同 host 多账号时必须用 --user 限定。
#===============================================================================
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/lib-common.sh"

HOST="" USER="" PORT="" YES=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --user|--username) USER="$2"; shift 2;;
    --port) PORT="$2"; shift 2;;
    --yes) YES="true"; shift 1;;
    -h|--help) sed -n '2,10p' "$0"; exit 0;;
    *) [[ -z "$HOST" ]] && HOST="$1" || rsc_die "未知参数: $1"; shift 1;;
  esac
done
[[ -n "$HOST" ]] || rsc_die "用法: server-remove.sh <host> [--user <name>] --yes"
[[ "$YES" == "true" ]] || rsc_die "请显式加 --yes 确认删除"

# 先确认能唯一定位（复用查找逻辑，多重匹配会在这里报错）
SRV=$(rsc_server_json "$HOST" "$USER" "$PORT")
PORT=$(jq -r '.port' <<<"$SRV")
USER=$(jq -r '.auth.username' <<<"$SRV")

rsc_jq_update '
  .servers |= map(select((.host == $h and .port == ($p|tonumber) and .auth.username == $u) | not))
' --arg h "$HOST" --arg p "$PORT" --arg u "$USER"

rsc_info "已删除档案: $USER@$HOST:$PORT（reports/ 中的历史巡检报告保留未删）"
