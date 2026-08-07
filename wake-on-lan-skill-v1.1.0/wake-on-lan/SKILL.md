---
name: wake-on-lan
version: 1.1.0
description: Wake-on-LAN (WOL) remote power-on skill for the agent. Triggers when the user says "wake [机器]", "开机 [IP末位]", "魔法开机", "wol", or any WOL intent. Dispatches to the correct MAC by IP suffix or hostname. **Always runs multi-channel precheck first** (v1.0+).
triggers:
  - "开机"
  - "唤醒"
  - "魔法开机"
  - "wake"
  - "wol"
  - "远程开机"
  - "启动 [机器]"
---

# Wake-on-LAN（远程开机）— Agent Skill v1.1.0

> 一个 agent skill 真正成熟的标志，不是它能跑多少功能，而是它**知道自己哪里会坏**。
> 这个 skill 现在有 8 条 known-issues，每条背后都是一次"以为修好了结果没修好"的故事。

## 这是什么

我是 agent。这个 skill 让我能在用户的局域网里**远程唤醒一台关机或休眠的机器**。

用户说一句"开机 254"，我会：

1. 识别目标（IP 末位 / 主机名 / 完整 IP）
2. **先做多通道存活验证**——v1.0 强制流程
3. 查 `machines.md` 取 MAC
4. 发 3 个 WOL 包（间隔 2 秒）
5. 等机器启动（每台等待时间不同）
6. ping 验证 + 报告

## 何时用

**用这个 skill 当**：

- 用户说"开机 X"、"唤醒 X"、"wol X"——任何明确的唤醒意图
- 用户让我"开一下 NAS" / "把 k8s 节点叫起来"——自然语言 + 模糊指向
- 用户的"日常操作"——他们知道机器现在没开

**不要用这个 skill 当**：

- 机器本来就开着——`precheck` 会发现，skill 直接退出
- 用户没说要开机但机器确实没开（比如 SSH 失败）——**先做 precheck 再说，不要直接发 WOL**
- 跨网段唤醒（路由器不支持 directed broadcast）——见 [troubleshooting.md](references/troubleshooting.md) 第 9 条

## 怎么用

### 触发词识别

skill 监听（任意一个就触发）：

- "开机" / "唤醒" / "魔法开机" / "远程开机"
- "wake" / "wol"
- 后面跟：IP 末位（如 `254`）/ 完整 IP（如 `192.168.3.50`）/ 主机名（如 `nas`、`k8s01`）

### 调用

```bash
# 通用脚本
bash <skill_dir>/scripts/wake.sh <ip末位|完整IP|主机名> [--no-precheck]

# 例子
bash wake.sh 254          # 唤醒 PVE (192.168.3.254)
bash wake.sh 50           # 唤醒 k8s01
bash wake.sh nas          # 用主机名
bash wake.sh 254 --no-precheck   # 跳过存活验证（不推荐）
```

### 工作流程

```
[Step 0] precheck.sh（v1.0 强制）
   ├─ LAN ping 通？ → 已在线，结束
   ├─ 试备选通道（zerotier/tailscale/VPN）
   │   └─ 任一通？ → 机器没死，结束
   └─ 都不通？ → 真离线，继续

[Step 1] 解析 machines.md 取 MAC + 启动等待时间

[Step 2] 发 3 个 WOL 包（间隔 2 秒）到 192.168.X.255:9

[Step 3] sleep N 秒（每台机器不同：NAS 60s, PVE 60s+VM, 服务器 40s）

[Step 4] ping 验证
   ├─ 通？ → 报告 ✅
   └─ 不通？ → 报告 ❌ + 排查提示
```

## 已知问题（速查）

完整 8 条 known-issues 见 [troubleshooting.md](references/troubleshooting.md)。摘要：

1. 单包失败，连发 3 包
2. bond 模式必须用 eth1 MAC
3. PVE 不读 systemd-networkd .link
4. bridge/bond 接口不能直接配 WOL
5. m 不是 magic，g 才是
6. MAC 撞表要警觉
7. LAN ping 不通 ≠ 机器关机
8. poweroff 不可逆（无 BMC 时）

## 参考资料

- [machines.md](references/machines.md) — 机器配置表（IP、MAC、启动等待时间）
- [precheck.md](references/precheck.md) — 多通道存活验证（v1.0 新增）
- [persistence.md](references/persistence.md) — 持久化配置（ifupdown/NetworkManager/systemd-networkd）
- [pve-multi-nic.md](references/pve-multi-nic.md) — PVE 多网卡 WOL
- [troubleshooting.md](references/troubleshooting.md) — 8 条 known-issues 详细排查
- [CHANGELOG.md](../CHANGELOG.md) — 演进史

## 添加新机器

1. 编辑 `references/machines.md`，加一段 `## 192.168.X.Y — 机器名` + IP/MAC/启动等待时间表
2. skill 解析逻辑会自动识别新的机器
3. 上线后第一时间 `ssh ... ip link show | grep ether` 实抓核对 MAC
