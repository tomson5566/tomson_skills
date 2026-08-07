# Changelog

> 一个 agent skill 的演进史。**不是功能的堆砌，是踩坑的轨迹。**

## v1.1.0（2026-08-07）— 当前

### 新增

- **`scripts/install-wol.sh`** — 目标机器一键配置 WOL + 持久化
  - 自动检测系统类型（ifupdown / NetworkManager / systemd-networkd）
  - 立即开 wol g
  - 按系统类型加 hook
  - 备份原文件
  - 验证
- **`references/precheck.md`** — 多通道存活验证独立文档
- **`references/persistence.md`** — 整合原 `wol-persistence.md`，覆盖 4 种系统
- **`references/pve-multi-nic.md`** — 整合原 `wol-pve-multinic.md`
- **`references/troubleshooting.md`** — 8 条 known-issues 速查表
- **`CHANGELOG.md`** — 本文件
- **`README.md`** — 人类视角速读

### 改进

- 主 `SKILL.md` 改 agent-first 视角，明确 v1.0+ 强制 precheck
- `machines.md` 拆出独立文件，加"添加新机器"步骤
- `wake.sh` 集成 precheck 流程（默认会跑，可 `--no-precheck` 跳过）
- `precheck.sh` 独立可用，支持多备选 IP

### 文件结构

```
v0.x: SKILL.md (内嵌 machines 表) + scripts/wake.sh
v1.0: + precheck 流程强制化
v1.1: + references/ 拆分 + install-wol.sh + 完整文档
```

## v1.0（2026-08-06）— 决定性一坑

### 关键变化

- **强制 precheck 流程**：唤醒前必须验证机器真死
- 触发：k8s01 误判事件（LAN 不通但 zerotier 通，发了 6 个无效 WOL 包）
- 修复：`wake.sh` 默认先跑 `precheck.sh`

### 影响

- v0.x 的 skill 是"功能"
- v1.0 的 skill 是"流程"
- 用户的"误判"风险降到 0

## v0.9（2026-08-06 之前）

- MAC 撞表检测与标注
- m 不是 magic 的字符含义表
- machines.md 加 ⚠️ 标注

## v0.8（2026-08 早期）

- PVE 不读 systemd-networkd .link 的发现
- 改用 ifupdown post-up + rc.local 双钩子

## v0.7

- bond 模式必须用 eth1 MAC 的发现
- WOL 包双发 eth0 + eth1

## v0.6

- 单包失败实测
- 改三包连发（间隔 2 秒）

## v0.5

- 支持多台机器
- 通用 `wake.sh` 自动解析 `machines.md`

## v0.1

- 第一版 `wake-230.sh`
- `wakeonlan` 单包发到 MAC
- 能用

---

## 演进原则

> **skill 不是功能。skill 是踩坑文档。**

每加一条 known-issue，就升一个小版本。每修一条 known-issue，不升版本（因为"修"本身可能就是新的"坑"的入口）。

下一条 known-issue 写什么？通常是用户**再次撞到的**——只要被撞两次，就值得写进 troubleshooting.md。
