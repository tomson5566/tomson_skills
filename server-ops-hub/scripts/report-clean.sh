#!/usr/bin/env bash
# report-clean.sh - 手动清理过期巡检报告
#
# 用法:
#   report-clean.sh [--days N] [--dry-run]
#
# 说明:
#   - 默认保留期读取顺序: 环境变量 RSC_REPORT_KEEP_DAYS > servers.json settings.report_keep_days > 30 天
#   - server-check.sh / daily-disk-check.sh 每次运行后也会自动执行同样的清理
#   - --dry-run 只列出将被删除的报告，不实际删除（建议先跑一次确认）
#
# 示例:
#   report-clean.sh --dry-run        # 先看看哪些报告会被删
#   report-clean.sh                  # 按保留期清理
#   report-clean.sh --days 7         # 临时按 7 天保留期清理
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib-common.sh"

DAYS="" DRY=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --days) DAYS="${2:?--days 需要数值}"; shift 2;;
    --dry-run) DRY="dry"; shift 1;;
    -h|--help)
      grep '^#' "$0" | sed 's/^# \{0,1\}//' | head -16; exit 0;;
    *) rsc_die "未知参数: $1（用 --help 查看用法）";;
  esac
done

rsc_ensure_files
[[ -n "$DAYS" && ! "$DAYS" =~ ^[0-9]+$ ]] && rsc_die "--days 必须是非负整数: $DAYS"

KEEP="${DAYS:-$(rsc_report_keep_days)}"
rsc_info "报告目录: $RSC_REPORTS_DIR（保留期: ${KEEP} 天）"
rsc_report_cleanup "$KEEP" ${DRY:+"$DRY"}
