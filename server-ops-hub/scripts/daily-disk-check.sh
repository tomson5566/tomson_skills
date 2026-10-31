#!/usr/bin/env bash
#===============================================================================
# daily-disk-check.sh — 批量每日巡检（磁盘/内存/负载），超阈值告警
#
# 用法:
#   daily-disk-check.sh [--threshold 80] [--category 生产]
#
# 说明:
#   - 遍历档案库 servers.json 中所有服务器（可按分类过滤）
#   - 报告写入 reports/daily_YYYYMMDD.log
#   - 磁盘使用率 > 阈值（默认80%）告警，退出码 1
#   - 单台失败不影响其他服务器
#
# crontab 示例（每天 9:00）:
#   0 9 * * * /path/to/server-ops-hub/scripts/daily-disk-check.sh >/dev/null 2>&1
#===============================================================================
set -uo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/lib-common.sh"

THRESHOLD=80 CATEGORY=""
while [[ $# -gt 0 ]]; do case "$1" in
  --threshold) THRESHOLD="$2"; shift 2;;
  --category) CATEGORY="$2"; shift 2;;
  -h|--help) sed -n '2,16p' "$0"; exit 0;;
  *) rsc_die "未知参数: $1";; esac; done

rsc_ensure_files
FILTER='.servers[]'
[[ -n "$CATEGORY" ]] && FILTER="$FILTER | select(.category == \$cat)"

LOG="$RSC_REPORTS_DIR/daily_$(date +%Y%m%d).log"
HAS_ALERT=0

{
  echo "==================== 每日巡检 $(date '+%F %T') 阈值>${THRESHOLD}% ===================="
} >> "$LOG"

while IFS= read -r srv; do
  H=$(jq -r '.host' <<<"$srv"); U=$(jq -r '.auth.username' <<<"$srv"); P=$(jq -r '.port' <<<"$srv")
  echo "" >> "$LOG"
  echo "▶ $U@$H:$P" >> "$LOG"
  OUT=$(RSC_SSH_TIMEOUT="${RSC_SSH_TIMEOUT}" rsc_ssh_run "$srv" '
    hostname
    df -P | grep -vE "tmpfs|devtmpfs|squashfs|overlay|Filesystem"
    free -h | head -2
    uptime
  ' 2>&1) && RC=0 || RC=1

  if [[ $RC -ne 0 ]]; then
    echo "  ❌ 连接失败: $(tail -1 <<<"$OUT")" >> "$LOG"
    HAS_ALERT=1
    continue
  fi
  # 磁盘行分析
  while IFS= read -r line; do
    if [[ "$line" =~ ^/dev/ ]]; then
      PCT=$(awk '{print $5}' <<<"$line" | tr -d '%')
      MNT=$(awk '{print $6}' <<<"$line")
      if [[ "$PCT" =~ ^[0-9]+$ && "$PCT" -gt "$THRESHOLD" ]]; then
        echo "  ⚠️ 告警: $MNT ${PCT}%" >> "$LOG"; HAS_ALERT=1
      else
        echo "  ✅ $MNT ${PCT}%" >> "$LOG"
      fi
    else
      echo "  $line" >> "$LOG"
    fi
  done <<<"$OUT"
done < <(jq -c --arg cat "$CATEGORY" "$FILTER" "$RSC_CONFIG")

{
  echo ""
  if [[ $HAS_ALERT -eq 1 ]]; then echo "❌ 巡检完成，存在告警，详见上文"; else echo "✅ 全部正常"; fi
} >> "$LOG"

tail -5 "$LOG"
rsc_report_cleanup
[[ $HAS_ALERT -eq 1 ]] && exit 1 || exit 0
