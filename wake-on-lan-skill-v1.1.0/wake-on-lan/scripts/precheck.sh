#!/usr/bin/env bash
# precheck.sh — 唤醒前的存活验证 (v1.0+)
# 用法:  precheck.sh <lan_ip> [备选IP...]
# 返回:  0 = 机器活着（LAN 或备选通道通），1 = 真离线

set -euo pipefail

LAN_IP="${1:?usage: precheck.sh <lan_ip> [alt_ip...]}"
shift
ALT_IPS=("$@")

echo "==> [1/4] ARP 缓存状态"
arp_state=$(ip neigh show "$LAN_IP" 2>/dev/null | awk '{print $NF}' | head -1)
echo "    state: ${arp_state:-UNKNOWN}"
case "$arp_state" in
    FAILED)      echo "    → 机器真不在线（ARP 解析失败）" ;;
    INCOMPLETE)  echo "    → 网络活着，机器不响应 ARP" ;;
    REACHABLE|STALE|DELAY|PROBE)  echo "    → ARP 实际可达" ;;
esac

echo "==> [2/4] LAN ping $LAN_IP"
if timeout 3 ping -c 1 -W 2 "$LAN_IP" >/dev/null 2>&1; then
    echo "    ✅ LAN 通"
    exit 0
fi
echo "    LAN 不通"

echo "==> [3/4] 备选通道"
if [[ ${#ALT_IPS[@]} -eq 0 ]]; then
    echo "    无备选 IP 配置，跳过"
else
    for alt in "${ALT_IPS[@]}"; do
        if timeout 3 ping -c 1 -W 2 "$alt" >/dev/null 2>&1; then
            echo "    ✅ $alt 通 → 机器活着，问题在 LAN"
            echo "    💡 不要发 WOL 包，去查网线/交换机/路由器"
            exit 0
        fi
        echo "    ✗ $alt 不通"
    done
fi

echo "==> [4/4] zerotier peers（最后诊断）"
if command -v docker >/dev/null && docker ps --format '{{.Names}}' 2>/dev/null | grep -q zerotier; then
    echo "    zerotier-one 容器在跑："
    docker exec zerotier-one zerotier-cli listpeers 2>&1 | head -10
elif command -v zerotier-cli >/dev/null; then
    zerotier-cli listpeers 2>&1 | head -10
else
    echo "    zerotier 未安装"
fi

echo "==> 所有通道都不通 → 机器可能真关机，可以发 WOL"
exit 1
