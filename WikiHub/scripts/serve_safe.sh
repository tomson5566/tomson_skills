#!/usr/bin/env bash
# WikiHub safe serve wrapper.
# Writes PID + port files scoped to <workspace>/.wikihub/, runs in background, never touches other workspaces.
set -euo pipefail

NAME=""
ROOT=""
HOST="0.0.0.0"
PORT=""
WORKSPACE=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --name) NAME="$2"; shift 2;;
    --root) ROOT="$2"; shift 2;;
    --host) HOST="$2"; shift 2;;
    --port) PORT="$2"; shift 2;;
    --workspace) WORKSPACE="$2"; shift 2;;
    *) echo "unknown arg: $1" >&2; exit 1;;
  esac
done

if [[ -z "$NAME" || -z "$ROOT" || -z "$WORKSPACE" ]]; then
  echo "usage: serve_safe.sh --name N --root R --host H --port P --workspace W" >&2
  exit 1
fi

# Safety: refuse if workspace path contains fqd_pro or other workspaces we should not touch
case "$WORKSPACE" in
  *fqd_pro*)
    echo "REFUSE: workspace path contains 'fqd_pro'; WikiHub will not operate there" >&2
    exit 2
    ;;
esac

STATE_DIR="$WORKSPACE/.wikihub"
mkdir -p "$STATE_DIR"
PID_FILE="$STATE_DIR/$NAME.pid"
PORT_FILE="$STATE_DIR/$NAME.port"
LOG_FILE="$STATE_DIR/$NAME.log"
OUTPUT_DIR="$ROOT/output"

if [[ ! -d "$OUTPUT_DIR" ]]; then
  echo "REFUSE: output dir not found: $OUTPUT_DIR" >&2
  exit 1
fi

# Pick port if busy (simple netstat fallback)
is_port_busy() {
  local p=$1
  if command -v ss >/dev/null 2>&1; then
    ss -ltn 2>/dev/null | awk '{print $4}' | grep -qE "[.:]$p$" && return 0
  fi
  if command -v netstat >/dev/null 2>&1; then
    netstat -ltn 2>/dev/null | awk '{print $4}' | grep -qE "[.:]$p$" && return 0
  fi
  # Fallback: try binding
  python3 -c "import socket;s=socket.socket();s.bind(('$HOST',$p));s.close()" 2>/dev/null && return 1 || return 0
}

if is_port_busy "$PORT"; then
  echo "DEBUG: port $PORT busy per probe; scanning for next free" >&2
  for try in $(seq "$PORT" 8999); do
    if ! is_port_busy "$try"; then PORT=$try; break; fi
  done
else
  echo "DEBUG: port $PORT free per probe; using as-is" >&2
fi

echo "$PORT" > "$PORT_FILE"

# Launch background python http server, fully detached
cd "$OUTPUT_DIR"
nohup python3 -m http.server "$PORT" --bind "$HOST" \
  >> "$LOG_FILE" 2>&1 &
SERVER_PID=$!
disown "$SERVER_PID" 2>/dev/null || true
echo "$SERVER_PID" > "$PID_FILE"

# Give it a moment to bind, then verify
sleep 0.3
if ! kill -0 "$SERVER_PID" 2>/dev/null; then
  echo "REFUSE: server died on startup; check $LOG_FILE" >&2
  rm -f "$PID_FILE" "$PORT_FILE"
  exit 1
fi

echo "WikiHub serving '$NAME' on $HOST:$PORT (pid $SERVER_PID)"
echo "  workspace=$WORKSPACE"
echo "  log=$LOG_FILE"