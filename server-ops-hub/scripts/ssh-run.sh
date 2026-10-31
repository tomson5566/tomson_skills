#!/usr/bin/env bash
#===============================================================================
# ssh-run.sh — 在指定服务器上执行任意命令（自动按档案选择密钥/密码认证）
#
# 用法:
#   ssh-run.sh <host> [--user U] [--timeout N] <远程命令>
#   ssh-run.sh <host> [--user U] --root <远程命令>     # su - root 提权执行
#
# 示例:
#   ssh-run.sh 192.168.1.10 "df -h"
#   ssh-run.sh 203.0.113.10 --root "systemctl status nginx"
#   RSC_SSH_TIMEOUT=90 ssh-run.sh 192.168.1.10 "du -h --max-depth=1 /"
#===============================================================================
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/lib-common.sh"

HOST="" USER="" AS_ROOT=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --user|--username) USER="$2"; shift 2;;
    --timeout) RSC_SSH_TIMEOUT="$2"; shift 2;;
    --root) AS_ROOT="yes"; shift 1;;
    -h|--help) sed -n '2,13p' "$0"; exit 0;;
    *) break;;
  esac
done
HOST="${1:-}"; shift || rsc_die "缺少远程命令"
[[ -n "$HOST" ]] || rsc_die "用法: ssh-run.sh <host> [--user U] [--root] <远程命令>"
CMD="$*"

SRV=$(rsc_server_json "$HOST" "$USER" "")

if [[ "$AS_ROOT" == "yes" ]]; then
  RP=$(jq -r '.auth.root_password // ""' <<<"$SRV")
  [[ -n "$RP" ]] || rsc_die "档案中无 root_password，无法提权。先用 server-add.sh --root-password 补充"
  # 脚本文件方式走 su 管道
  TMP=$(mktemp)
  printf '%s\n' "$CMD" > "$TMP"
  rsc_ssh_run_script "$SRV" "$TMP" "yes"
  rm -f "$TMP"
else
  rsc_ssh_run "$SRV" "$CMD"
fi
