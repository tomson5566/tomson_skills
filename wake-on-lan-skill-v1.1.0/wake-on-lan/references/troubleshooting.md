# 故障排查（8 条 known-issues 速查）

> 这个文件是这个 skill 真正值钱的地方。
> 每一条背后都是一次"以为修好了结果没修好"。
> 维护顺序：踩到 → 修 → 加进 known-issues → 版本号 +0.1。

---

## 坑 1：单包失败，连发 3 包才稳

**症状**：发一个 WOL 包，等了 60 秒机器没醒；再发一个，醒了。

**真相**：网卡从上电到 PHY 接收有几百毫秒的初始化窗口，**单包正好错过这个窗口的概率不低**。

**诊断**：

```bash
# 连续发包观察成功率
for i in 1 2 3 4 5; do
    python3 -c "import socket; s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM); s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1); s.sendto(b'\xff'*6+b'\x<MAC>'*16, ('192.168.3.255', 9)); s.close()"
    sleep 30
    timeout 3 ping -c1 -W2 192.168.3.X
done
```

**修复**：

```python
# scripts/wake.sh v1.0 默认就是三包连发
for _ in range(3):
    s.sendto(b'\xff'*6 + mac*16, (broadcast, 9))
    time.sleep(2)
```

**修复后版本**：v0.6

---

## 坑 2：bond 模式下，eth0 MAC 没反应，必须用 eth1 MAC

**症状**：群晖 DS1821+（或任何用 bond0 绑 eth0+eth1 的机器）用 eth0 MAC 发包，等 60 秒没反应。

**真相**：bond0 是 Linux 内核的软件抽象，**真正的 PHY 在 eth1 上**。WOL 魔法包在 PHY 层解码，bond 本身不接 PHY。

**诊断**：

```bash
# 看 bond 模式
cat /proc/net/bonding/bond0
# Slave Interface: eth0 / eth1
# 哪个是 active slave，物理 PHY 在哪

# 分别试两个 MAC
python3 -c "..."  # 用 eth0 MAC
python3 -c "..."  # 用 eth1 MAC
```

**修复**：

skill 的 `machines.md` 里 NAS 那条要标注 bond/eth1 MAC，并且**双发**：

```python
mac0 = b'\x00\x11\x32\xb3\x31\x16'  # eth0
mac1 = b'\x00\x11\x32\xb3\x31\x15'  # eth1/bond0
s.sendto(magic+mac0*16, ('192.168.3.255', 9))
s.sendto(magic+mac1*16, ('192.168.3.255', 9))
```

**修复后版本**：v0.7

---

## 坑 3：bridge / bond 接口配 WOL 没用

**症状**：管理 IP 在 `vmbr0` 上，跑 `ethtool vmbr0 wol g` 报 `Operation not supported`，或 `Supports Wake-on: no`。

**真相**：bridge / bond 都是**软件设备**，没有自己的 PHY 电路，**WOL 永远配在物理 slave 上**。

**诊断**：

```bash
# 找物理 slave
bridge link show
# 输出示例: 3: enp7s0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 master vmbr0

# 配物理网卡
ethtool -s enp7s0 wol g
```

**修复**：见 [persistence.md](persistence.md) Step 5。

**修复后版本**：v0.7（搭配坑 2 一起修）

---

## 坑 4：PVE 不读 systemd-networkd .link 文件

**症状**：在 PVE 主机上写 `/etc/systemd/network/10-enp7s0.link`，`WakeOnLan=magic`，重启后 `ethtool` 看到 `Wake-on: d`。

**真相**：PVE 是 ifupdown + systemd 混合，**`systemd-networkd` 在 PVE 上默认不读 link 文件**。

**诊断**：

```bash
# 看 networkd 在不在跑
systemctl is-active systemd-networkd
# 一般是 inactive 或 not-found

# 确认 link 文件本身没问题
systemd-analyze verify /etc/systemd/network/10-enp7s0.link
```

**修复**：放弃 link 文件，走 `/etc/network/interfaces` post-up + rc.local 双钩子。详见 [persistence.md](persistence.md) Step 3。

**修复后版本**：v0.8

---

## 坑 5：m 不是 magic，g 才是

**症状**：看到 `ethtool` 输出里有 `m` 还以为支持 WOL，结果发包没反应。

**真相**：

| 字符 | 含义 |
| --- | --- |
| `m` | multicast（多播） |
| **`g`** | **magic packet** |

**诊断**：

```bash
ethtool <nic> | grep "Supports Wake-on"
# 必须含 'g'
```

**修复**：用 `g`，永远不要用 `m`。

**修复后版本**：v0.9（加进字符含义表）

---

## 坑 6：MAC 撞表要警觉

**症状**：`machines.md` 里两台机器的 MAC 一样，发包发到错的机器（或两台都不响应）。

**真相**：几乎肯定是记错了。两台物理机器不会真有同一 MAC。

**诊断**：

```bash
# 机器上线第一时间实抓核对
ssh root@192.168.3.230 'ip link show | grep ether'
ssh root@192.168.3.254 'ip link show | grep ether'
# 对照 machines.md
```

**修复**：

1. 撞表的两条都标 ⚠️ 待实测
2. 机器上线第一时间 `ip link` 实抓
3. 错的改正
4. 下次发包前先确认 MAC

**修复后版本**：v0.9

---

## 坑 7：LAN ping 不通 ≠ 机器关机（最危险！）

**症状**：发 6 个 WOL 包给 k8s01（192.168.3.50），等 100 秒没醒。准备下结论"机器坏了"。

**真相**：k8s01 装了 zerotier，**通过 zerotier 通道 `10.229.190.50` 仍然可达、SSH 22 端口监听中**。LAN 是断的（网线松/交换机重启/路由器 WAN 切换），机器根本没关机。

**诊断**（**唤醒前必做**）：

```bash
# 1) 查 ARP
ip neigh show <lan_ip>
# FAILED = 机器不在线，INCOMPLETE = 还在 arp 解析

# 2) 试备选通道
for alt in <zerotier_ip> <tailscale_ip> <vpn_ip>; do
    timeout 3 ping -c1 -W2 $alt && echo "通：$alt"
done

# 3) 任一备选通道通 → 机器没死，跳过 WOL，去查 LAN 故障
# 4) 所有通道都不通 → 真离线，可以 WOL
```

**修复**：

skill 在 v1.0 加了**强制 precheck 流程**。`wake.sh` 默认先跑 `precheck.sh`，机器活着就直接退出。

```bash
bash wake.sh 50              # 默认会跑 precheck
bash wake.sh 50 --no-precheck  # 强制发包（已知 LAN 故障时用）
```

**修复后版本**：v1.0（决定性一坑）

---

## 坑 8：关机是不可逆操作（无 BMC 时）

**症状**：图省事直接 `poweroff` 了 PVE 主机（VUModule），WOL 没生效。8 个 VM 全死，要去搬显示器+键盘救。

**真相**：PVE 没 IPMI/iLO/iDRAC。WOL 是唯一的远程唤醒路径，**没有"第二条命"**。

**诊断**（**poweroff 之前必做**）：

```bash
# 至少确认一项备选通道存在
# - zerotier / tailscale / VPN
# - IPMI / iLO / iDRAC
# - 物理显示器 + 键盘（你愿意去机房就当我没说）

# 任一项存在 → 可以 poweroff
# 都不存在 → 拒绝 poweroff，去买 IPMI 再说
```

**修复**：

skill 在用户让我 `poweroff` 一台无 BMC 机器时，**必须先做这个检查**。如果不通过，拒绝执行并报告原因。

**修复后版本**：v1.1（当前）

---

## 速查表

| 坑 | 一句话判断 | 修复版本 |
| --- | --- | --- |
| 1. 单包失败 | 多发几包 | v0.6 |
| 2. bond MAC | 用 eth1 MAC 或双发 | v0.7 |
| 3. bridge 无 PHY | 配物理 slave | v0.7 |
| 4. PVE 不读 link | 走 ifupdown + rc.local | v0.8 |
| 5. m ≠ magic | 用 g | v0.9 |
| 6. MAC 撞表 | 机器上线实抓核对 | v0.9 |
| 7. LAN ≠ 死 | precheck 多通道 | v1.0 |
| 8. poweroff 不可逆 | 至少一个备选通道 | v1.1 |
