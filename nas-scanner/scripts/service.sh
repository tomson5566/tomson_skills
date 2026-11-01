#!/bin/bash
# NAS 勒索软件威胁扫描器 —— 源码部署服务管理脚本
#
# 用法：
#   bash scripts/service.sh start     启动服务（后台常驻，日志写入 logs/app.log）
#   bash scripts/service.sh stop      停止服务
#   bash scripts/service.sh restart   重启服务
#   bash scripts/service.sh status    查看运行状态
#   bash scripts/service.sh logs      跟踪日志
set -Eeuo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
cd "${PROJECT_ROOT}"

PORT="${DEPLOY_RUN_PORT:-${PORT:-5000}}"
HOSTNAME_BIND="${HOSTNAME:-0.0.0.0}"
LOG_DIR="${COZE_LOG_DIR:-${PROJECT_ROOT}/logs}"
LOG_FILE="${LOG_DIR}/app.log"
PID_FILE="${LOG_DIR}/server.pid"

export PORT HOSTNAME COZE_PROJECT_ENV=PROD

list_port_pids() {
  local port=$1 pids=""
  if command -v ss >/dev/null 2>&1; then
    pids="$(ss -H -lntp 2>/dev/null | grep -E "[:.]${port}[[:space:]]" \
      | grep -o 'pid=[0-9]*' | cut -d= -f2 | sort -u | paste -sd' ' - || true)"
  fi
  if [[ -z "${pids}" ]] && command -v lsof >/dev/null 2>&1; then
    pids="$(lsof -t -iTCP:"${port}" -sTCP:LISTEN 2>/dev/null | sort -u | paste -sd' ' - || true)"
  fi
  echo "${pids}"
}

stop_service() {
  local pids
  pids="$(list_port_pids "${PORT}")"
  if [[ -n "${pids}" ]]; then
    echo "Stopping PID(s): ${pids}"
    # shellcheck disable=SC2086
    kill -TERM ${pids} 2>/dev/null || true
    for _ in $(seq 1 10); do
      [[ -z "$(list_port_pids "${PORT}")" ]] && break
      sleep 1
    done
    pids="$(list_port_pids "${PORT}")"
    if [[ -n "${pids}" ]]; then
      echo "Port ${PORT} still held, sending SIGKILL."
      # shellcheck disable=SC2086
      kill -KILL ${pids} 2>/dev/null || true
      sleep 1
    fi
  fi
  rm -f "${PID_FILE}"
  echo "Stopped."
}

start_service() {
  if [[ -n "$(list_port_pids "${PORT}")" ]]; then
    echo "Port ${PORT} already in use. Run 'stop' first." >&2
    exit 1
  fi
  if [[ ! -f dist/server.js ]]; then
    echo "dist/server.js not found. Run: bash scripts/build.sh" >&2
    exit 1
  fi

  mkdir -p "${LOG_DIR}"
  # setsid 让服务脱离当前终端会话，SSH 断开后依然存活。
  (setsid nohup node dist/server.js >> "${LOG_FILE}" 2>&1 < /dev/null &)

  for _ in $(seq 1 30); do
    if [[ -n "$(list_port_pids "${PORT}")" ]]; then
      echo "Started. Listening on http://${HOSTNAME_BIND}:${PORT} (PID: $(list_port_pids "${PORT}"))"
      echo "Log file: ${LOG_FILE}"
      return 0
    fi
    sleep 1
  done

  echo "Service failed to listen on port ${PORT} within 30s." >&2
  tail -n 30 "${LOG_FILE}" >&2 || true
  exit 1
}

status_service() {
  local pids
  pids="$(list_port_pids "${PORT}")"
  if [[ -n "${pids}" ]]; then
    echo "Status: RUNNING (PID: ${pids})"
    echo "Address: http://${HOSTNAME_BIND}:${PORT}"
    ps -o pid,ppid,etime,rss,cmd -p ${pids} 2>/dev/null || true
  else
    echo "Status: STOPPED"
  fi
}

case "${1:-status}" in
  start)   start_service ;;
  stop)    stop_service ;;
  restart) stop_service; start_service ;;
  status)  status_service ;;
  logs)    mkdir -p "${LOG_DIR}"; tail -f "${LOG_FILE}" ;;
  smb-logs)
    # SMB 连接诊断日志：记录「为什么登不上」的完整线索（密码已脱敏）
    mkdir -p "${LOG_DIR}"
    SMB_LOG="${LOG_DIR}/smb-debug.log"
    if [[ ! -f "${SMB_LOG}" ]]; then
      echo "尚无 SMB 诊断日志：${SMB_LOG}"
      echo "请先在页面上发起一次扫描。"
      exit 0
    fi
    if [[ "${2:-}" == "-f" ]]; then
      tail -f "${SMB_LOG}"
    else
      tail -n "${2:-40}" "${SMB_LOG}"
    fi
    ;;
  *) echo "Usage: $0 {start|stop|restart|status|logs|smb-logs}" >&2; exit 1 ;;
esac
