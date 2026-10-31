#!/usr/bin/env bash
#===============================================================================
# server-check.sh — 服务器安全巡检 + 巡检结果回写档案库
#
# 用法:
#   server-check.sh <host> [--user U] [--timeout N] [--no-update]
#
# 巡检内容:
#   1) 系统信息(主机名/OS/内核/内存/磁盘)  2) 登录用户(未授权告警)
#   3) 网络流量与连接数                    4) 监听端口与服务
#   5) 可疑进程扫描                        6) authorized_keys 风险
#   7) 关注服务(watch_services)状态与自动拉起
#
# 输出:
#   - 完整报告存 reports/<host>_<时间戳>.log；结束后自动清理超过保留期的旧报告（默认30天）
#   - 自动回写 servers.json: last_check/hostname/os/kernel/listening_ports
#   - 服务/数据库/中间件/凭证等结构化信息由 agent 解读报告后用 server-update.sh 迭代回写
#===============================================================================
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/lib-common.sh"

HOST="" USER="" NO_UPDATE=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --user|--username) USER="$2"; shift 2;;
    --timeout) RSC_SSH_TIMEOUT="$2"; shift 2;;
    --no-update) NO_UPDATE="true"; shift 1;;
    -h|--help) sed -n '2,19p' "$0"; exit 0;;
    *) [[ -z "$HOST" ]] && HOST="$1" || rsc_die "未知参数: $1"; shift 1;;
  esac
done
[[ -n "$HOST" ]] || rsc_die "用法: server-check.sh <host> [--user U] [--timeout N]"

SRV=$(rsc_server_json "$HOST" "$USER" "")
USER=$(jq -r '.auth.username' <<<"$SRV")
PORT=$(jq -r '.port' <<<"$SRV")

# ---------- 生成远程巡检脚本 ----------
REMOTE_SCRIPT=$(mktemp)
cat > "$REMOTE_SCRIPT" <<'RSC_REMOTE'
#!/bin/sh
echo "📊 [1/7] 系统信息"
echo "----------------------------------------------------"
HN=$(hostname 2>/dev/null || cat /proc/sys/kernel/hostname)
OS=$( (. /etc/os-release 2>/dev/null && echo "$PRETTY_NAME") || uname -s )
KR=$(uname -r)
echo "主机名: $HN"
echo "系统:   $OS"
echo "内核:   $KR"
echo "时间:   $(date '+%F %T')"
echo "负载:   $(uptime)"
echo "内存:"; free -h 2>/dev/null | head -3
echo "磁盘:"
df -h 2>/dev/null | grep -vE 'tmpfs|devtmpfs|squashfs|overlay|Filesystem' || df -h
# 磁盘超 80% 告警
df -P 2>/dev/null | grep -vE 'tmpfs|devtmpfs|squashfs|overlay|Filesystem' | awk '$5+0 > 80 {print "⚠️  磁盘告警: " $6 " 使用率 " $5}'

echo ""
echo "👤 [2/7] 登录用户检查"
echo "----------------------------------------------------"
who 2>/dev/null || true
echo "系统可登录用户:"
grep -E "/bin/(ba)?sh|/usr/bin/(ba)?sh" /etc/passwd 2>/dev/null | cut -d: -f1 | sort | tr '\n' ' '; echo

echo ""
echo "📈 [3/7] 网络流量与连接"
echo "----------------------------------------------------"
IFACE=$(ip -4 route ls 2>/dev/null | awk '/default/ {print $5; exit}')
if [ -n "$IFACE" ]; then
  RX=$(cat /sys/class/net/$IFACE/statistics/rx_bytes 2>/dev/null)
  TX=$(cat /sys/class/net/$IFACE/statistics/tx_bytes 2>/dev/null)
  [ -n "$RX" ] && echo "外网接口 $IFACE 累计收: $((RX/1024/1024)) MB / 发: $((TX/1024/1024)) MB"
fi
echo "ESTABLISHED 连接数: $( (netstat -an 2>/dev/null || ss -an) | grep -c ESTABLISHED )"

echo ""
echo "🌐 [4/7] 监听端口与服务"
echo "----------------------------------------------------"
if command -v ss >/dev/null 2>&1; then
  ss -tulnp 2>/dev/null || ss -tuln
else
  netstat -tulpn 2>/dev/null || netstat -tuln
fi

echo ""
echo "🔍 [5/7] 可疑进程扫描"
echo "----------------------------------------------------"
ps aux 2>/dev/null | grep -E "(minerd|cryptonight|xmrig|backdoor|trojan|malware|sshuttle|nc\.|netcat|ncat|socat|mining|stratum)" | grep -v grep \
  && echo "⚠️  发现可疑进程，请人工确认" || echo "✓ 未发现已知恶意进程特征"

echo ""
echo "🔑 [6/7] authorized_keys 风险检查"
echo "----------------------------------------------------"
for u in $(grep -E "/bin/(ba)?sh|/usr/bin/(ba)?sh" /etc/passwd 2>/dev/null | cut -d: -f1); do
  home=$(grep "^$u:" /etc/passwd | cut -d: -f6)
  ak="$home/.ssh/authorized_keys"
  if [ -f "$ak" ]; then
    cnt=$(grep -vc '^#' "$ak" 2>/dev/null)
    echo "➜ $u: $cnt 个授权密钥"
    [ "$cnt" -gt 2 ] && echo "  ⚠️  密钥数量较多，注意是否存在未授权注入"
  fi
done

echo ""
echo "⚙️ [7/7] 关注服务状态"
echo "----------------------------------------------------"
RSC_REMOTE

# 追加 watch_services 检查块（值来自 servers.json，拼进远程脚本）
WATCH_COUNT=$(jq '.watch_services | length' <<<"$SRV")
if [[ "$WATCH_COUNT" == "0" ]]; then
  echo 'echo "（未配置关注服务。用 server-update.sh watch 添加，如 openclaw/nginx）"' >> "$REMOTE_SCRIPT"
else
  while IFS= read -r ws; do
    W_NAME=$(jq -r '.name' <<<"$ws")
    W_MATCH=$(jq -r '.match' <<<"$ws")
    W_START=$(jq -r '.start_cmd // ""' <<<"$ws")
    W_AUTO=$(jq -r '.auto_restart // false' <<<"$ws")
    # 单引号消毒
    sq() { printf '%s' "$1" | sed "s/'/'\\\\''/g"; }
    {
      echo "echo '— 服务: $(sq "$W_NAME") —'"
      echo "if ps aux | grep -F '$(sq "$W_MATCH")' | grep -v grep >/dev/null 2>&1; then"
      echo "  echo \"✅ $(sq "$W_NAME") 运行中\""
      echo "else"
      echo "  echo \"⚠️  $(sq "$W_NAME") 未运行\""
      if [[ "$W_AUTO" == "true" && -n "$W_START" ]]; then
        echo "  echo '尝试自动拉起...'"
        echo "  sh -c '$(sq "$W_START")' >/dev/null 2>&1"
        echo "  sleep 3"
        echo "  ps aux | grep -F '$(sq "$W_MATCH")' | grep -v grep >/dev/null 2>&1 \\"
        echo "    && echo '✅ 拉起成功' || echo '❌ 拉起失败，请人工处理'"
      else
        echo "  echo '（auto_restart 未开启，仅告警不拉起）'"
      fi
      echo "fi"
    } >> "$REMOTE_SCRIPT"
  done < <(jq -c '.watch_services[]' <<<"$SRV")
fi

# 机器可读标记块（供本地解析回写档案）
cat >> "$REMOTE_SCRIPT" <<'RSC_REMOTE'

echo ""
echo "###RSC_META_BEGIN###"
echo "hostname=$HN"
echo "os=$OS"
echo "kernel=$KR"
echo "###RSC_META_END###"
echo "###RSC_PORTS_BEGIN###"
if command -v ss >/dev/null 2>&1; then
  ss -tulnp 2>/dev/null | awk 'NR>1 && $2=="LISTEN" { n=split($5,a,":"); port=a[n]; proc="-"; if (match($0, /"[^"]+"/)) proc=substr($0, RSTART+1, RLENGTH-2); printf "%s\t%s\t%s\n", $1, port, proc }'
else
  netstat -tulpn 2>/dev/null | awk '$6=="LISTEN" { n=split($4,a,":"); port=a[n]; split($7,b,"/"); proc=(b[2]==""?"-":b[2]); printf "%s\t%s\t%s\n", $1, port, proc }'
fi
echo "###RSC_PORTS_END###"
echo ""
echo "===== 巡检完成: $(date '+%F %T') ====="
RSC_REMOTE

# ---------- 执行巡检 ----------
TS=$(date '+%Y%m%d_%H%M%S')
REPORT="$RSC_REPORTS_DIR/${HOST}_${TS}.log"
mkdir -p "$RSC_REPORTS_DIR"

rsc_info "开始巡检 $USER@$HOST:$PORT ..."
echo "===== 巡检开始: $(date '+%F %T') 目标: $USER@$HOST:$PORT =====" | tee "$REPORT"

if rsc_ssh_run_script "$SRV" "$REMOTE_SCRIPT" "auto" 2>&1 | tee -a "$REPORT"; then
  :
else
  rsc_die "SSH 连接或远程执行失败，详见报告: $REPORT"
fi
rm -f "$REMOTE_SCRIPT"

# ---------- 解析并回写档案 ----------
if [[ "$NO_UPDATE" != "true" ]]; then
  META=$(sed -n '/###RSC_META_BEGIN###/,/###RSC_META_END###/p' "$REPORT")
  PORTS_TSV=$(sed -n '/###RSC_PORTS_BEGIN###/,/###RSC_PORTS_END###/p' "$REPORT" | grep -v '^###RSC_')
  HN=$(awk -F= '/^hostname=/{print substr($0, index($0,"=")+1)}' <<<"$META")
  OS=$(awk -F= '/^os=/{print substr($0, index($0,"=")+1)}' <<<"$META")
  KR=$(awk -F= '/^kernel=/{print substr($0, index($0,"=")+1)}' <<<"$META")
  PORTS_JSON=$(printf '%s\n' "$PORTS_TSV" | jq -R -s -c '
    split("\n") | map(select(index("\t") != null) | split("\t")
    | {proto: .[0], port: ((.[1] | tonumber) // 0), process: (.[2] // "-")})
    | unique | sort_by(.port)')

  rsc_jq_update '
    .servers |= map(
      if .host == $h and .port == ($p|tonumber) and .auth.username == $u then
        .inspection.last_check = $now
        | .inspection.hostname = (if $hn == "" then .inspection.hostname else $hn end)
        | .inspection.os = (if $os == "" then .inspection.os else $os end)
        | .inspection.kernel = (if $kr == "" then .inspection.kernel else $kr end)
        | .inspection.listening_ports = ($pj | fromjson)
        | .updated_at = $now
      else . end)
  ' --arg h "$HOST" --arg p "$PORT" --arg u "$USER" \
    --arg hn "$HN" --arg os "$OS" --arg kr "$KR" --arg pj "$PORTS_JSON"
  rsc_info "档案已回写: last_check/hostname/os/kernel/listening_ports"
fi

echo
rsc_info "✅ 巡检完成。报告: $REPORT"
rsc_report_cleanup
rsc_info "下一步(agent): 解读报告后，用 server-update.sh 把服务/数据库/中间件/端口/凭证迭代回写档案"
