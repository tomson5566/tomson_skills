#!/bin/bash
set -Eeuo pipefail


PORT="${DEPLOY_RUN_PORT:-${PORT:-5000}}"
COZE_WORKSPACE_PATH="${COZE_WORKSPACE_PATH:-$(pwd)}"
DEPLOY_RUN_PORT="${DEPLOY_RUN_PORT:-${PORT}}"


cd "${COZE_WORKSPACE_PATH}"

list_port_pids() {
    local port=$1
    local pids=""
    local has_tool=0

    if command -v ss >/dev/null 2>&1; then
      has_tool=1
      pids=$(ss -H -lntp 2>/dev/null | awk -v port="${port}" '$4 ~ ":"port"$"' | grep -o 'pid=[0-9]*' | cut -d= -f2 | sort -u | paste -sd' ' - || true)
    fi
    if [[ -z "${pids}" ]] && command -v lsof >/dev/null 2>&1; then
      has_tool=1
      pids=$(lsof -t -iTCP:"${port}" -sTCP:LISTEN 2>/dev/null | sort -u | paste -sd' ' - || true)
    fi
    if [[ "${has_tool}" -eq 0 ]]; then
      echo "Warning: neither ss nor lsof available, cannot inspect port ${port}." >&2
    fi

    echo "${pids}"
}

kill_port_if_listening() {
    local pids
    pids=$(list_port_pids "${DEPLOY_RUN_PORT}")
    if [[ -z "${pids}" ]]; then
      echo "Port ${DEPLOY_RUN_PORT} is free."
      return
    fi
    echo "Port ${DEPLOY_RUN_PORT} in use by PIDs: ${pids} (SIGKILL)"
    echo "${pids}" | xargs -I {} kill -9 {} || true
    sleep 1
    pids=$(list_port_pids "${DEPLOY_RUN_PORT}")
    if [[ -n "${pids}" ]]; then
      echo "端口 ${DEPLOY_RUN_PORT} 被 PID ${pids} 占用且无法清理（SIGKILL 后仍在监听），dev server 无法启动。" >&2
      exit 1
    fi
    echo "Port ${DEPLOY_RUN_PORT} cleared."
}

# Next 的路由清单由 watchpack 每次启动重新扫 src 下的 app/pages 目录现算，而 watchpack
# 不会进入软链目录，软链子树里的 page/route 会被静默跳过：既不注册路由，也不打任何日志，
# 表现为该路由一直 404 而 .next 里没有它的产物。这里只做提示，不改动源码。
warn_source_symlinks() {
    local source_dir="${COZE_WORKSPACE_PATH}/src"
    local links link
    if [[ ! -e "${source_dir}" ]]; then
      return
    fi
    links=$(find "${source_dir}" -type l 2>/dev/null || true)
    if [[ -z "${links}" ]]; then
      return
    fi
    echo "Warning: 以下路径是软链，Next 不会进入其中，里面的 page/route 不会被编译：" >&2
    while IFS= read -r link; do
      echo "  ${link}" >&2
    done <<< "${links}"
}

# 云盘挂载偶尔会把新建文件的 mtime 设为 Unix epoch。Watchpack 会因此把路由文件当作
# 启动前的旧状态，导致 Next 的首轮扫描漏掉 route/page。只在云盘项目启动前刷新 app/pages
# 的目录和普通文件时间戳；不跟随软链、不改文件内容。
refresh_drive_route_mtimes() {
    local drive_root="${COZE_DRIVE_ROOT:-/Coze/Drive}"
    local project_root route_dir
    project_root="$(pwd -P)"
    if [[ -d "${drive_root}" ]]; then
      drive_root="$(cd "${drive_root}" && pwd -P)"
    else
      drive_root="${drive_root%/}"
    fi

    case "${project_root}" in
      "${drive_root}"|"${drive_root}"/*) ;;
      *) return ;;
    esac

    for route_dir in "${COZE_WORKSPACE_PATH}/src/app" "${COZE_WORKSPACE_PATH}/src/pages"; do
      [[ -d "${route_dir}" ]] || continue
      if ! find -P "${route_dir}" \( -type f -o -type d \) -exec touch {} + 2>/dev/null; then
        echo "Warning: failed to refresh Next route timestamps in ${route_dir}." >&2
      fi
    done
}


LOG_DIR="${COZE_LOG_DIR:-${COZE_WORKSPACE_PATH}/logs}"
LOG_FILE="${LOG_DIR}/app.log"
PID_FILE="${LOG_DIR}/server.pid"

# detached 出去的进程没人负责回收，超过这个时长就自己退出，避免端口与内存长期泄露。
MAX_RUNTIME_SECONDS=3600

timeout_watchdog_enabled() {
  [[ -z "${COZE_EVAL:-}" && -z "${COZE_PROJECT_TYPE:-}" ]]
}

# 真正被 detach 的是这层 bash wrapper：它是进程组 leader，组内 watchdog 到点回收整组
# （wrapper -> pnpm -> next -> node）；被包的进程自己先退出时也顺手清空进程组，不留残余。
RUN_WITH_TIMEOUT="$(declare -f timeout_watchdog_enabled)"'
timeout_seconds=$1
shift

"$@" &
child_pid=$!

# 先忽略 TERM，才能在向整组发 TERM（自己也在组里）之后存活下来补一发 KILL。
if timeout_watchdog_enabled; then
( trap "" TERM
  sleep "${timeout_seconds}"
  echo "[dev] 后台进程运行超过 ${timeout_seconds}s，回收进程组 $$。"
  kill -TERM -- "-$$" 2>/dev/null || true
  sleep 5
  kill -KILL -- "-$$" 2>/dev/null || true
) &
fi

wait "${child_pid}"
kill -KILL -- "-$$" 2>/dev/null || true
'

# 返回的 PID 是 wrapper 的，同时也是整个进程组的 PGID，后续按组回收。
spawn_detached() {
  local cwd="$1"
  local log_file="$2"
  shift 2

  node - "$cwd" "$log_file" \
    /bin/bash -c "${RUN_WITH_TIMEOUT}" detached-runner "${MAX_RUNTIME_SECONDS}" "$@" <<'NODE'
const fs = require('node:fs');
const { spawn } = require('node:child_process');

const [cwd, logFile, command, ...args] = process.argv.slice(2);
if (!cwd || !logFile || !command) {
  throw new Error('spawn_detached 缺少 cwd、log_file 或 command');
}

const logFd = fs.openSync(logFile, 'a');
try {
  const child = spawn(command, args, {
    cwd,
    detached: true,
    env: process.env,
    stdio: ['ignore', logFd, logFd],
  });
  child.unref();
  process.stdout.write(String(child.pid));
} finally {
  fs.closeSync(logFd);
}
NODE
}

stop_detached() {
  local pid="${1:-}"
  if [[ -z "${pid}" ]]; then
    return
  fi

  kill -TERM -- "-${pid}" 2>/dev/null || kill -TERM "${pid}" 2>/dev/null || true
  sleep 1
  kill -KILL -- "-${pid}" 2>/dev/null || true
}

READY_RETRIES=30
READY_PROBE_HOSTS=("127.0.0.1" "::1")
LOG_TAIL_LINES=40

dump_log() {
  echo "---- tail -n ${LOG_TAIL_LINES} ${LOG_FILE} ----" >&2
  tail -n "${LOG_TAIL_LINES}" "${LOG_FILE}" >&2 || true
  echo "---- end of ${LOG_FILE} ----" >&2
}

# 服务刚就绪时 app-paths-manifest.json 还是空的（dev 按需编译，没请求就没产物），
# 但 .next/dev/types/routes.d.ts 已经写出了本次启动发现到的全部路由。把它落进日志，
# 排查时才能区分“路由没被发现”和“路由发现了但还没编译”。
dump_discovered_routes() {
  local route_types="${COZE_WORKSPACE_PATH}/.next/dev/types/routes.d.ts"
  if [[ ! -f "${route_types}" ]]; then
    return
  fi
  {
    echo "---- discovered routes (${route_types}) ----"
    grep -E '^type (AppRoutes|AppRouteHandlerRoutes|PageRoutes) ' "${route_types}" || true
    echo "---- end of discovered routes ----"
  } >> "${LOG_FILE}"
}

# 仅用于无 ss/lsof 时的兜底探测。服务可能只 bind IPv4 loopback、只 bind IPv6 loopback
# （server.listen(port, 'localhost') 会变成 ::1 独占），或 bind 双栈通配地址，
port_connectable() {
  local port=$1
  local host
  for host in "${READY_PROBE_HOSTS[@]}"; do
    if command -v nc >/dev/null 2>&1; then
      if nc -z -w 1 "${host}" "${port}" >/dev/null 2>&1; then
        return 0
      fi
    elif (exec 3<>"/dev/tcp/${host}/${port}") >/dev/null 2>&1; then
      return 0
    fi
  done
  return 1
}

port_probe_available() {
  command -v ss >/dev/null 2>&1 || command -v lsof >/dev/null 2>&1
}

# 端口监听者是否属于本进程组：spawn detached 后 PID == PGID，子孙进程继承该 PGID。
#   0 = 是；1 = 不是（无人监听，或监听者不属于本进程组）；2 = 无探测工具，无法判断
port_listened_by_pgid() {
  local port=$1 pgid=$2
  local listener owner

  if ! port_probe_available; then
    return 2
  fi

  for listener in $(list_port_pids "${port}" 2>/dev/null); do
    owner=$(ps -o pgid= -p "${listener}" 2>/dev/null | tr -d ' ')
    if [[ "${owner}" == "${pgid}" ]]; then
      return 0
    fi
  done
  return 1
}

wait_for_ready() {
  local pid=$1 port=$2
  local attempt=0 owned

  if ! port_probe_available; then
    echo "Warning: 缺少 ss 与 lsof，无法确认端口监听者归属，仅按 loopback 可连接性判断就绪。" >&2
  fi

  while [[ "${attempt}" -lt "${READY_RETRIES}" ]]; do
    if ! kill -0 "${pid}" 2>/dev/null; then
      echo "Dev server 进程在启动过程中退出。" >&2
      return 1
    fi

    if port_listened_by_pgid "${port}" "${pid}"; then
      owned=0
    else
      owned=$?
    fi
    if [[ "${owned}" -eq 0 ]]; then
      return 0
    fi
    if [[ "${owned}" -eq 2 ]] && port_connectable "${port}"; then
      return 0
    fi

    sleep 1
    attempt=$((attempt + 1))
  done

  return 2
}

# 监听端口的是孙进程（pnpm -> next -> node），只清端口会漏掉上层 pnpm/next，
# 所以先按上次记录的 PID 把整个进程组回收掉。
if [[ -f "${PID_FILE}" ]]; then
  stop_detached "$(cat "${PID_FILE}" 2>/dev/null || true)"
  rm -f "${PID_FILE}"
fi

echo "Clearing port ${DEPLOY_RUN_PORT} before start."
kill_port_if_listening
bash "${COZE_WORKSPACE_PATH}/scripts/prepare-node-modules.sh" --prefer-frozen-lockfile --prefer-offline --loglevel debug --reporter=append-only
warn_source_symlinks
refresh_drive_route_mtimes
echo "Starting HTTP service on port ${DEPLOY_RUN_PORT} for dev..."

mkdir -p "${LOG_DIR}"
: > "${LOG_FILE}"

export PORT="${DEPLOY_RUN_PORT}"
server_pid="$(spawn_detached "${COZE_WORKSPACE_PATH}" "${LOG_FILE}" \
  "$(command -v pnpm)" next dev --webpack --hostname 0.0.0.0 --port "${DEPLOY_RUN_PORT}")"
if [[ -z "${server_pid}" ]]; then
  echo "Dev server failed to start: 未获取到后台进程 PID。" >&2
  dump_log
  exit 1
fi
echo "${server_pid}" > "${PID_FILE}"

if wait_for_ready "${server_pid}" "${DEPLOY_RUN_PORT}"; then
  ready_status=0
else
  ready_status=$?
fi

if [[ "${ready_status}" -ne 0 ]]; then
  if [[ "${ready_status}" -eq 2 ]]; then
    echo "Dev server did not listen on port ${DEPLOY_RUN_PORT} after ${READY_RETRIES} attempts; stopping PID ${server_pid}." >&2
  else
    echo "Dev server failed to start. See ${LOG_FILE}." >&2
  fi
  # 先 dump 再回收，避免 kill 的输出混进日志尾部；exit 1 意味着不留下任何后台进程。
  dump_log
  stop_detached "${server_pid}"
  rm -f "${PID_FILE}"
  exit 1
fi

dump_discovered_routes

echo "Dev server started (PID: ${server_pid}), listening on port ${DEPLOY_RUN_PORT}."
if timeout_watchdog_enabled; then
  echo "Auto stop after ${MAX_RUNTIME_SECONDS}s."
fi
echo "Log file: ${LOG_FILE}"
echo "PID file: ${PID_FILE}"

