# Wake-on-LAN Skill (v1.1.0)

> 一个 agent skill 真正成熟的标志，不是它能跑多少功能，而是它**知道自己哪里会坏**。

## 这是什么

让 agent 能在用户局域网里**远程唤醒**任何一台关机或休眠的机器。用户说一句"开机 254" 就行。

## 文件清单

```
wake-on-lan/
├── SKILL.md                      # 主入口（agent 视角）
├── README.md                     # 本文件（人类视角速读）
├── CHANGELOG.md                  # 演进史
├── references/
│   ├── machines.md               # 机器配置表（IP/MAC/启动等待）
│   ├── precheck.md               # 多通道存活验证（v1.0 新增）
│   ├── persistence.md            # 持久化配置（4 种系统）
│   ├── pve-multi-nic.md          # PVE 多网卡 WOL
│   └── troubleshooting.md        # 8 条 known-issues 速查
└── scripts/
    ├── wake.sh                   # 通用唤醒脚本（含 precheck）
    ├── precheck.sh               # 独立 precheck 脚本
    └── install-wol.sh            # 目标机一键配 WOL + 持久化
```

## 快速开始

### 1. 配置目标机器（每台只做一次）

在目标机器上以 root 跑：

```bash
bash install-wol.sh <nic>
# 例: bash install-wol.sh enp7s0
```

会自动：立即开 wol g + 按系统类型加 hook + 备份原文件 + 验证。

### 2. 配置 skill 端

把 `machines.md` 编辑成你自己的机器表，每台一段 `## <IP> — <名字>`。

### 3. 唤醒

```bash
bash scripts/wake.sh 254           # 末位简写
bash scripts/wake.sh 192.168.3.50  # 完整 IP
bash scripts/wake.sh nas           # 主机名
bash scripts/wake.sh 254 --no-precheck  # 跳过存活验证
```

### 4. 添加新机器

参考 `references/machines.md` 末尾的"添加新机器的步骤"。

## 已知问题（8 条）

完整排查见 [`references/troubleshooting.md`](references/troubleshooting.md)。摘要：

1. 单包失败，连发 3 包
2. bond 模式必须用 eth1 MAC
3. PVE 不读 systemd-networkd .link
4. bridge/bond 接口不能直接配 WOL
5. m 不是 magic，g 才是
6. MAC 撞表要警觉
7. **LAN ping 不通 ≠ 机器关机**（v1.0 强制 precheck）
8. poweroff 不可逆（无 BMC 时）

## 设计原则

> 一个 skill 的成熟度 = 它的 known-issues 列表有多长。

每条 known-issue 背后都是一次"以为修好了结果没修好"的故事。维护节奏：

1. 踩到坑
2. 修
3. 加进 troubleshooting.md
4. 版本号 +0.1

## 演进史

见 [`CHANGELOG.md`](CHANGELOG.md)。
