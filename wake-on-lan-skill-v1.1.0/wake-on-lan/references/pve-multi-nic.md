# PVE 多网卡 WOL 实战

> 来源：192.168.3.254 VUModule 实战（2026-08-06）。
> 适用：Proxmox VE / Debian ifupdown 主机有 ≥ 2 块物理网卡且想双保险唤醒。

## 1. 拓扑

```
                      +----------+----------+
LAN (192.168.3.0/24) |   switch A    |  LAN (192.168.12.0/24) |   switch B     |
                      +------------+----------+
                                  |                   |
                                  v                   v
+----------------------+   +----------------------+
| enp7s0 (RTL8125B)    |   | enp8s0f0 (e1000e)    |
| vmbr0 / 192.168.3.254 |  | 192.168.12.254 (闲置) |
| 主用, 8 个 VM 走这里   |  | 备用, 当前无 VM      |
| Wake-on: g           |   | Wake-on: g           |
+----------------------+   +----------------------+
                                  |
                                  v
                          PVE 主机 (Debian 13)
```

## 2. 完整 recipe（已验证，2026-08-06）

```bash
# === A. 准备 ===
ssh root@<pve>
ip -br addr show                 # 确认 IP 绑哪个接口
ethtool enp7s0   | grep -iE "supports|wake-on|link"
ethtool enp8s0f0 | grep -iE "supports|wake-on|link"
# 两块都必须有 'g' 在 Supports 行，Link detected: yes

# === B. 立即开启 ===
/usr/sbin/ethtool -s enp7s0   wol g
/usr/sbin/ethtool -s enp8s0f0 wol g

# === C. 持久化（双钩子 × 双网卡 = 4 处写入）===

# C-1. 备份 — 用 PVE 自己的命名风格
cp /etc/network/interfaces /etc/network/interfaces.bak_$(date +%Y%m%d_%H%M%S)_wol-<note>
cp /etc/rc.local            /etc/rc.local.bak_$(date +%Y%m%d_%H%M%S)_wol-<note>

# C-2. /etc/network/interfaces — 在 iface 段下加 post-up / pre-down
# enp7s0 段：
#   iface enp7s0 inet manual
#       post-up /usr/sbin/ethtool -s enp7s0 wol g
#       pre-down /usr/sbin/ethtool -s enp7s0 wol g
# enp8s0f0 段（已存在 static IP）：
#   iface enp8s0f0 inet static
#       address 192.168.12.254/24
#       post-up /usr/sbin/ethtool -s enp8s0f0 wol g
#       pre-down /usr/sbin/ethtool -s enp8s0f0 wol g

# C-3. /etc/rc.local 兜底
#   /usr/sbin/ethtool -s enp7s0   wol g >/dev/null 2>&1 || true
#   /usr/sbin/ethtool -s enp8s0f0 wol g >/dev/null 2>&1 || true

# === D. 不重启验证 ===
ethtool enp7s0   | grep "Wake-on"   # g
ethtool enp8s0f0 | grep "Wake-on"   # g
```

## 3. 唤醒脚本（双 NIC 双发，注意段限制）

```python
#!/usr/bin/env python3
# WOL 双网卡发包脚本 — PVE 192.168.3.254
# 注意：广播只在本机所在段内传播
- enp7s0 在 192.168.3.0/24，广播 3.255 有效
- enp8s0f0 在 192.168.12.0/24，该段无机器时 3.255 发包到不了
  → 备用 NIC 的 WOL 仅在物理层面有意义（双网线 + 主 NIC 故障时兜底）
  → 实际唤醒仍以主 NIC 收包为主
'''
import socket, time

s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

MAC_MAIN = b'\x74\x56\x3c\x49\x9a\xc4'  # enp7s0 (主)
MAC_BAK  = b'\x1c\x86\x0b\x20\x8f\x86'  # enp8s0f0 (备)

BROADCAST = ('192.168.3.255', 9)
MAGIC = b'\xff' * 6

for _ in range(3):
    s.sendto(MAGIC + MAC_MAIN * 16, BROADCAST)
    s.sendto(MAGIC + MAC_BAK * 16, BROADCAST)
    time.sleep(2)

s.close()
print('Sent 3x WOL to enp7s0 + enp8s0f0')
```

## 4. 关键决策

| 决策点 | 选择 | 理由 |
| --- | --- | --- |
| 是否真机关机验证 | **跳过** | 无 BMC，关了回不来，8 个 VM 全死 |
| 双钩子是否都要写 | 都要 | interfaces (network 阶段) + rc.local (multi-user 阶段) |
| 双 NIC 是否都开 wol | 都开 | 单价 0 风险、双网卡双保险 |
| 备用 NIC 是否要新加段 IP | 保留原 PVE 自动配的 192.168.12.254 | 该段闲置但 IP 已在 |
| 备份命名 | `interfaces.bak_YYYYMMDD_HHMMSS_wol-<note>` | 与 PVE 自动备份一致 |

## 5. 已知限制

- enp8s0f0 段（192.168.12.0/24）无其他机器，从 3.x 段发包到它需要路由器允许 directed broadcast 或同段机器发包
- 备用 NIC 的 WOL 价值主要在"机器断电 + 双网线都接 + 主 NIC PHY 故障"场景下兜底
- PVE Web UI 改网络会重生成 `/etc/network/interfaces`，手工段需要重写——设置巡检 `grep -c ethtool /etc/network/interfaces`
