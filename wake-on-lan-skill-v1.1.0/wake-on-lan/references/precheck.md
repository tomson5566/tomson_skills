# 多通道存活验证（v1.0 强制流程）

> **为什么这一节是 v1.0 最重要的升级**：因为盲目发 WOL 等于赌命。
> 真实事故：树莓派发 6 包 WOL 到 k8s01 没反应，深入排查发现 k8s01 通过 zerotier 通道活着。
> 如果当时先做 precheck，就能避免这次错误判断。

## 原则

> **LAN ping 不通 ≠ 机器关机。**
>
> 任何时候遇到 LAN ping 超时，按以下顺序排查：
>
> 1. ARP 状态
> 2. 备选网络通道（zerotier / tailscale / VPN）
> 3. 真离线才发 WOL

## 流程

```bash
#!/usr/bin/env bash
# precheck.sh — 唤醒前的存活验证
# 用法:  precheck.sh <lan_ip> [备选IP...]

set -euo pipefail

LAN_IP="${1:?usage: precheck.sh <lan_ip> [alt_ip...]}"
shift
ALT_IPS=("$@")

# 默认备选通道（每台机器有 zerotier IP 时配这里）
[[ ${#ALT_IPS[@]} -eq 0 ]] && ALT_IPS=(
    "10.229.190.50"    # k8s01
    "10.229.190.162"   # VUModule (PVE)
)

echo "==> 1) 查 ARP 缓存"
arp_state=$(ip neigh show "$LAN_IP" 2>/dev/null | awk '{print $NF}' | head -1)
echo "    ARP state: ${arp_state:-UNKNOWN}"
case "$arp_state" in
    FAILED)      echo "    → 机器真不在线（ARP 失败）" ;;
    INCOMPLETE)  echo "    → 网络活着，机器不响应" ;;
    REACHABLE|STALE|DELAY)  echo "    → 机器实际可达" ;;
esac

# LAN ping
echo "==> 2) 试 LAN ping"
if timeout 3 ping -c 1 -W 2 "$LAN_IP" >/dev/null 2>&1; then
    echo "    ✅ $LAN_IP LAN 通 → 机器已在线，无需唤醒"
    exit 0
fi
echo "    LAN 不通"

# 备选通道
echo "==> 3) 试备选通道"
for alt in "${ALT_IPS[@]}"; do
    if timeout 3 ping -c 1 -W 2 "$alt" >/dev/null 2>&1; then
        echo "    ✅ $alt 通 → 机器活着，问题在 LAN，去查网线/交换机"
        echo "    💡 不要发 WOL 包，去修 LAN 链路"
        exit 0
    fi
done

# zerotier peers（最后一道诊断）
echo "==> 4) 检查 zerotier peers"
if command -v docker >/dev/null && docker ps --format '{{.Names}}' 2>/dev/null | grep -q zerotier; then
    docker exec zerotier-one zerotier-cli listpeers 2>&1 | head -10
else
    echo "    zerotier-one 容器未运行"
fi

echo "==> 5) 所有通道都不通 → 机器可能真关机，可以发 WOL"
exit 1
```

## 备选通道怎么配

每台装了 zerotier/tailscale/VPN 的机器，在 `machines.md` 的表里加一行 `Zerotier IP`：

```markdown
| **Zerotier IP（备选通道）** | `10.229.190.50` |
```

skill 的 `wake.sh` 会读取这个 IP 作为备选通道。

## 实战经验

**真实事故时间线**（2026-08-06 之前）：

1. 树莓派发 6 包 WOL 到 k8s01（192.168.3.50），间隔 2 秒
2. 等 100 秒，机器没醒
3. 准备下结论"机器坏了"
4. 突然想起 k8s01 装了 zerotier
5. `ping 10.229.190.50` → 通
6. SSH 22 端口 → 监听中
7. SSH 协议层握手 → Permission denied（到达了 SSH 服务端）

**结论**：机器没死，是 LAN 链路断（网线松/交换机重启/路由器 WAN 切换）。

如果当时有 precheck 流程，根本不会发那 6 个 WOL 包。

## 在 wake.sh 里怎么用

`wake.sh` 默认会先调用 precheck。如果 precheck 返回 0（机器活着），直接退出不发 WOL。

如果想强制发包（用于已知 LAN 故障但用户确认要 WOL 的场景）：

```bash
bash wake.sh 254 --no-precheck
```
