#!/usr/bin/env bash
#===============================================================================
# server-list.sh — 列出档案库中的服务器
#
# 用法:
#   server-list.sh                    # 全部服务器概览表
#   server-list.sh --category 生产    # 按分类过滤
#   server-list.sh --json             # 输出原始 JSON（供 agent 程序化处理）
#===============================================================================
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/lib-common.sh"

CATEGORY="" AS_JSON=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --category) CATEGORY="$2"; shift 2;;
    --json) AS_JSON="true"; shift 1;;
    -h|--help) sed -n '2,10p' "$0"; exit 0;;
    *) rsc_die "未知参数: $1";;
  esac
done

rsc_ensure_files

FILTER='.servers'
[[ -n "$CATEGORY" ]] && FILTER="$FILTER | map(select(.category == \$cat))"

if [[ "$AS_JSON" == "true" ]]; then
  jq --arg cat "$CATEGORY" "$FILTER" "$RSC_CONFIG"
  exit 0
fi

COUNT=$(jq --arg cat "$CATEGORY" "$FILTER | length" "$RSC_CONFIG")
[[ "$COUNT" == "0" ]] && { rsc_warn "没有匹配的服务器档案"; exit 0; }

printf '\033[1m%-16s %-6s %-12s %-9s %-10s %-20s %-12s %s\033[0m\n' \
  "HOST" "PORT" "USER" "AUTH" "CATEGORY" "HOSTNAME/OS" "LAST_CHECK" "TAGS"
jq --arg cat "$CATEGORY" -r '
  '"$FILTER"' | sort_by(.category, .host) | .[] |
  [
    .host,
    (.port | tostring),
    .auth.username,
    (if .auth.type == "key" then
       (((.auth.key_names // []) + [(.auth.key_name // "")]) | map(select(length>0)) | unique) as $ks
       | "key:" + (($ks[0] // "?") + (if ($ks | length) > 1 then "+" + (($ks | length) - 1 | tostring) else "" end))
     else "password" end),
    .category,
    ((.inspection.hostname // "") + (if (.inspection.os // "") != "" then "/" + (.inspection.os | .[0:14]) else "" end)),
    (if (.inspection.last_check // "") == "" then "未巡检" else .inspection.last_check end),
    (.tags | join(","))
  ] | @tsv
' "$RSC_CONFIG" | while IFS=$'\t' read -r h p u a c ho lc t; do
  printf '%-16s %-6s %-12s %-9s %-10s %-20s %-12s %s\n' "$h" "$p" "$u" "$a" "$c" "$ho" "$lc" "$t"
done

echo
rsc_info "共 $COUNT 台。详情: server-show.sh <host>；巡检: server-check.sh <host>"
