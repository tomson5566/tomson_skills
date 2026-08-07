# 机器配置表

> 格式：每台机器一段，标题 `## <IP> — <名字>`，下接表格 + 备注。
> 唤醒脚本 (`wake.sh`) 通过解析这个文件自动取 MAC + 启动等待时间。

---

## 192.168.3.99 — 群晖 NAS (Synology DS1821+)

| 项目 | 值 |
| --- | --- |
| IP 地址 | 192.168.3.99 |
| MAC (bond0/eth1) | `00:11:32:b3:31:15` ✅ |
| MAC (eth0) | `00:11:32:b3:31:16` |
| WOL 端口 | 9 |
| **SSH 端口** | **10022**（默认 22，已改 10022 规避外网扫描） |
| 用户 | `nas` |
| 启动等待 | 60s |

> ⚠️ **bond 模式必须用 eth1 MAC**（`00:11:32:b3:31:15`）。
> eth0 MAC 在 bond 模式下 WoL 不生效——见 [troubleshooting.md 坑 2](troubleshooting.md#坑-2bond-模式下-eth0-mac-没反应必须用-eth1-mac)。
> 推荐双发 eth0 + eth1 确保唤醒成功。

---

## 192.168.3.130 — 开发机

| 项目 | 值 |
| --- | --- |
| IP 地址 | 192.168.3.130 |
| MAC 地址 | `08:62:66:b7:5d:e6` |
| WOL 端口 | 9 |
| SSH 端口 | 22 |
| 设备类型 | 通用服务器 |
| 启动等待 | 40s |

---

## 192.168.3.230 — 工作站

| 项目 | 值 |
| --- | --- |
| IP 地址 | 192.168.3.230 |
| MAC 地址 | `74:56:3c:49:9a:c4` ⚠️ **2026-08-06 待实测** |
| WOL 端口 | 9 |
| SSH 端口 | 22 |
| 设备类型 | 通用服务器 |
| 启动等待 | 40s |

> ⚠️ **MAC 撞表警告**：本机器记的 `74:56:3c:49:9a:c4` 与 `192.168.3.254` (PVE) 撞表。
> 几乎肯定是记错了——下次机器上线时**第一时间**用下面的命令核对：
>
> ```bash
> ssh root@192.168.3.230 'ip link show | grep ether'
> # 对照 MAC 是否为 74:56:3c:49:9a:c4
> # 如果不是，改正本文件
> ```
>
> 详见 [troubleshooting.md 坑 6](troubleshooting.md#坑-6mac-撞表要警觉)。

---

## 192.168.3.50 — k8s01 (Kubernetes 节点)

| 项目 | 值 |
| --- | --- |
| IP 地址 | 192.168.3.50 |
| MAC (enp3s0 / 有线 RTL8111) | `8c:16:45:20:94:4b` ✅ |
| MAC (wlp5s0 / WiFi RTL8821CE) | `70:c9:4e:e3:0e:2b` ⚠️ WiFi **不支持 WOL** |
| WOL 端口 | 9 |
| SSH 端口 | 22 |
| 用户 | `root`（免密） |
| 设备类型 | K8s 节点（Realtek RTL8111 有线 + RTL8821CE WiFi） |
| 启动等待 | 40s |
| ethtool 能力 | `pumbg` (物理/单播/多播/广播/魔包均支持) |
| **Zerotier IP（备选通道）** | **`10.229.190.50`** ✅ |
| zerotier 网络 | `1905728313e54e1f` (homenetwork_group) |

### ⚠️ 使用前必须配置

1. **BIOS 开启 PCIe 唤醒**：BIOS → 电源管理 / APM 设置 → `Power On by PCIe` / `Wake on LAN` = **Enabled**
2. **当前网卡 WoL 状态为 `d` (disabled)**，需在每台执行机上：
   ```bash
   ssh root@192.168.3.50 'ethtool -s enp3s0 wol g'
   ```
3. **持久化**：用 [scripts/install-wol.sh](../scripts/install-wol.sh) 一键完成（包含 rc.local 兜底）

### 备选通道说明

这台机器装了 zerotier（IP `10.229.190.50`）。当 LAN ping 不通时，**永远先试 zerotier**——经验：树莓派曾发 6 包 WOL 到 k8s01 没反应，但 zerotier 通道通、SSH 22 端口监听中。

详见 [precheck.md](precheck.md)。

---

## 192.168.3.254 — VUModule (Proxmox VE 主机)

| 项目 | 值 |
| --- | --- |
| IP 地址 | 192.168.3.254 |
| MAC (enp7s0 / RTL8125B) | `74:56:3c:49:9a:c4` ✅ 2026-08-06 实测 |
| MAC (enp8s0f0 / e1000e 备用) | `1c:86:0b:20:8f:86` ✅ 2026-08-06 实测，192.168.12.254/24 闲置 |
| WOL 端口 | 9 |
| SSH 端口 | 22 |
| 设备类型 | Proxmox VE 8 / Debian 13 / 8 个 VM / 1 个 CT |
| 启动等待 | 60s（PVE 自检） + VM 启动等待 |
| 网卡能力 | `pumbg` |
| 默认网关 | `192.168.3.1`（路由器） |
| Zerotier IP（备选通道） | `10.229.190.162` |

### WOL 配置状态（2026-08-06 完成）

- `/etc/network/interfaces`：`iface enp7s0 inet manual` 段下加 `post-up ethtool -s enp7s0 wol g` + `pre-down ...`（双保险）
- `/etc/rc.local`：开机兜底 `ethtool -s enp7s0 wol g`
- 备份命名：`/etc/network/interfaces.bak.YYYYMMDD` + `/etc/rc.local.bak.HHMM`

### 已知边界

| 情况 | 影响 |
| --- | --- |
| **真关机后无法回血** | 8 个 VM 全死，要物理显示器/键盘修 |
| **无 BMC/IPMI** | `ipmitool` 不存在，无法辅助唤醒 |
| **vmbr0 绑 enp7s0** | 重启 PVE 网桥会瞬断 → VM 短暂断网（正常） |

### 唤醒命令

LAN 广播发包（连发 3 包）：

```python
import socket, time
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
mac = b'\x74\x56\x3c\x49\x9a\xc4'
magic = b'\xff' * 6
for _ in range(3):
    s.sendto(magic + mac*16, ('192.168.3.255', 9))
    time.sleep(2)
s.close()
```

详见 [pve-multi-nic.md](pve-multi-nic.md)。

---

## 添加新机器的步骤

1. 在本文件加一段 `## <IP> — <名字>` 段
2. 写表格：IP / MAC / 启动等待时间（建议先用 SSH 实抓，不靠记忆）
3. **首次配置 WOL**：用 [scripts/install-wol.sh](../scripts/install-wol.sh) 一键完成
4. 在 `SKILL.md` 的"已知问题"部分看有没有这台机器的特殊坑
5. **至少离线测试一次**——发包 → 等 → ping 通，验证 skill 能跑通
