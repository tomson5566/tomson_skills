#!/usr/bin/env bash
# wake.sh — 通用 Wake-on-LAN 唤醒脚本 (v1.1.0)
# 用法:  wake.sh <ip末位|完整IP|主机名> [--no-precheck]
#
# 行为:
#   1. 默认先跑 precheck.sh，机器活着直接退出
#   2. 解析 machines.md 取 MAC + 启动等待
#   3. 发 3 个 WOL 包（间隔 2 秒）
#   4. 等待 N 秒
#   5. ping 验证

set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "usage: $0 <ip|hostname> [--no-precheck]" >&2
  echo "       e.g. $0 192.168.3.254" >&2
  echo "       e.g. $0 vumodule" >&2
  echo "       e.g. $0 254 --no-precheck" >&2
  exit 2
fi

TARGET=$1
shift || true
PRECHECK=1
for arg in "$@"; do
  case "$arg" in
    --no-precheck) PRECHECK=0 ;;
    -h|--help) sed -n '2,12p' "$0"; exit 0 ;;
    *) echo "unknown arg: $arg" >&2; exit 2 ;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MACHINES="${MACHINES_MD:-${SCRIPT_DIR}/../references/machines.md}"
PRECHECK_SH="${SCRIPT_DIR}/precheck.sh"

if [[ ! -f "$MACHINES" ]]; then
  echo "machines.md not found at: $MACHINES" >&2
  echo "set MACHINES_MD env var to override" >&2
  exit 2
fi

# === 解析 machines.md 取 IP / MAC / 启动等待 ===
eval "$(python3 - "$MACHINES" "$TARGET" <<'PYEOF'
import re, sys, pathlib

machines_path, target = sys.argv[1], sys.argv[2]
src = pathlib.Path(machines_path).read_text()

# Normalize target: allow shorthand like "254" -> "192.168.3.254"
def resolve(t, src):
    if re.match(r'^\d+\.\d+\.\d+\.\d+$', t):
        return t
    if t.isdigit() and len(t) <= 3:
        for m in re.finditer(r'(\d+\.\d+\.\d+\.)(\d+)\s*[—\-]\s*([^\n]+)', src):
            if m.group(2) == t:
                return m.group(1) + t
    for m in re.finditer(r'(\d+\.\d+\.\d+\.\d+)\s*[—\-]\s*([^\n]+)', src):
        if t.lower() in m.group(3).lower():
            return m.group(1)
    return None

ip = resolve(target, src)
if not ip:
    print(f"# target {target!r} not found in {machines_path}", file=sys.stderr)
    sys.exit(3)

# Find section belonging to that IP
sections = re.split(r'\n## ', src)
for sec in sections:
    if not sec.startswith(ip):
        continue
    mac_match = re.search(r'`([0-9a-f]{2}(?::[0-9a-f]{2}){5})`', sec)
    if not mac_match:
        print(f"# no MAC for {ip} in table", file=sys.stderr)
        sys.exit(3)
    mac = mac_match.group(1)
    wait_match = re.search(r'启动等待[^\d]*(\d+)\s*秒?', sec)
    wait = int(wait_match.group(1)) if wait_match else 60
    name_match = re.match(rf'{re.escape(ip)}\s*[—\-]\s*([^\n]+)', sec)
    name = name_match.group(1).strip() if name_match else ip
    broadcast = '.'.join(ip.split('.')[:3]) + '.255'

    # 抓 zerotier IP 作备选通道
    zt_match = re.search(r'\*\*?Zerotier IP[^\*]*\*\*?\s*[`|]?\s*([\d.]+)', sec)
    zt_ip = zt_match.group(1) if zt_match else ''

    print(f"WOL_IP={ip}")
    print(f"WOL_NAME={name}")
    print(f"WOL_MAC={mac}")
    print(f"WOL_WAIT={wait}")
    print(f"WOL_BROADCAST={broadcast}")
    if zt_ip:
        print(f"WOL_ZEROTIER={zt_ip}")
    sys.exit(0)

print(f"# section for {ip} not parseable", file=sys.stderr)
sys.exit(3)
PYEOF
)" || { echo "target ${TARGET} not in machine table at $MACHINES" >&2; exit 3; }

: "${WOL_IP:?parser did not set WOL_IP}"
: "${WOL_MAC:?parser did not set WOL_MAC}"
: "${WOL_WAIT:=60}"
: "${WOL_BROADCAST:=}"

echo "==> target: ${WOL_NAME} (${WOL_IP})"
echo "==> MAC:    ${WOL_MAC}"
echo "==> wait:   ${WOL_WAIT}s after send"

# === v1.0 强制 precheck ===
if [[ $PRECHECK -eq 1 ]]; then
  if [[ -x "$PRECHECK_SH" ]]; then
    echo "==> precheck: multi-channel verification"
    ALT_IPS=()
    [[ -n "${WOL_ZEROTIER:-}" ]] && ALT_IPS+=("$WOL_ZEROTIER")
    if "$PRECHECK_SH" "$WOL_IP" "${ALT_IPS[@]}"; then
      echo "==> machine appears online (LAN or alt channel) — WOL not needed"
      echo "    use --no-precheck to force send anyway"
      exit 0
    fi
    echo "==> precheck: all channels down — proceeding with WOL"
  else
    echo "==> precheck: $PRECHECK_SH not executable, falling back to simple ping"
    if timeout 3 ping -c1 -W2 "$WOL_IP" >/dev/null 2>&1; then
      echo "    already online — WOL not needed"
      exit 0
    fi
    echo "    no response — proceeding with WOL"
  fi
fi

# === 发 3 个 WOL 包，间隔 2 秒 ===
echo "==> sending 3x magic packet to ${WOL_BROADCAST}:9"
python3 - "${WOL_MAC}" "${WOL_BROADCAST}" <<'PYEOF'
import socket, sys, time
mac = bytes.fromhex(sys.argv[1].replace(':', ''))
broadcast = sys.argv[2]
magic = b'\xff' * 6
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
for i in range(3):
    s.sendto(magic + mac * 16, (broadcast, 9))
    time.sleep(2)
s.close()
print(f"    sent 3x to {broadcast}:9")
PYEOF

# === 等待 + 验证 ===
echo "==> waiting ${WOL_WAIT}s for boot..."
sleep "${WOL_WAIT}"

echo "==> verifying: ping ${WOL_IP}"
if timeout 5 ping -c3 -W3 "${WOL_IP}"; then
  echo "==> ✅ ${WOL_NAME} online"
  exit 0
else
  echo "==> ❌ ${WOL_NAME} not responding after ${WOL_WAIT}s" >&2
  echo "    check: BIOS Wake-on-LAN enabled? AC power present? switch port up?" >&2
  echo "    see: references/troubleshooting.md" >&2
  exit 1
fi
