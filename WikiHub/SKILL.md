---
name: "WikiHub"
description: "Use this skill when an agent needs to run, manage, or migrate isolated local Markdown knowledge bases across machines or workspaces, with safe port handling, per-wiki PID files, and a workspace-scoped CLI. WikiHub is workspace-scoped — install one copy per workspace for multi-agent isolation."
license: "MIT"
compatibility: "Requires Python 3.8+ with shell access, markitdown (for .docx/.pptx/.pdf clip), and either an OpenAI-compatible LLM endpoint or local Ollama for embeddings. WikiHub bootstraps per-wiki state under `<workspace>/.wikihub/`. Designed for multi-agent, multi-workspace isolation; will never touch another workspace's files."
---

# WikiHub

WikiHub 是一个**面向多智能体 / 多 workspace / 多 wiki 隔离**的本地知识库管理 Skill。

## 适用场景

- 你手上跑着 N 个并行项目 / 客户 / 环境，每个项目要一份独立 wiki
- 你在一台机器上有 N 个 agent workspace，每个 workspace 要独立的 wiki 管理
- 你想让多个 agent 共享一台机器但 wiki 互不串味
- 你想要一个**绝对安全**的端口管理机制（探测空闲、写 PID、加 banner、按键名停）

## 快速开始

### 0. 一行创建并启动一个 wiki

```bash
wikihub init my-proj --title "客户 X 项目" --port 8766
wikihub serve my-proj
```

### 1. 列出本 workspace 跑着的所有 wiki

```bash
wikihub list
```

输出：

```
NAME              PORT    PID    STATUS    TITLE                       ROOT
ops-demo-wiki     8766    41599  running   运维老炮的多 Wiki 隔离演示  ops-demo-wiki
devops-platform   8767    41801  running   内部平台 wiki               devops-platform
```

### 2. 按名字停（**绝不按端口**，避免误杀别的 workspace 的服务）

```bash
wikihub stop my-proj
```

### 3. 看日志

```bash
wikihub logs my-proj
```

## 工作流

| 你想做的事 | 命令 |
|---|---|
| 新建一个 wiki | `wikihub init <name> --title ... [--port ...]` |
| 收一份素材进 inbox | `wikihub clip <name> --source <path>` |
| 批量入典 | `wikihub batch-ingest <name>` |
| 起 web 前端 | `wikihub serve <name>`（自动探测空闲端口） |
| 列出本 workspace 全部 wiki | `wikihub list` |
| 看 wiki 状态 | `wikihub status <name>` |
| 看日志 | `wikihub logs <name>` |
| 停 | `wikihub stop <name>` |
| 自检 | `wikihub doctor` |

## 隔离硬规则（绝对遵守）

| 资源 | 边界 |
|---|---|
| Skill 目录 | 每个 workspace 一份 WikiHub 副本 |
| Wiki 数据 | `<workspace>/<wiki-name>/` |
| 嵌入缓存 | 每个 wiki 自己一份 |
| 端口 | 本 workspace 用 8766-8770；跨 workspace 无约定 |
| PID / 日志 | `<workspace>/.wikihub/<wiki-name>.{pid,log}` |
| Banner | `<workspace>/<wiki-name> · port <port> · <date>` |

**绝不会做的事**：

- 读 / 写 / 删任何其他 workspace 的文件
- kill 任何其他 workspace 的进程（按 PID 文件匹配，跨 workspace 永远不匹配）
- 占着别的 workspace 已用的端口（除非用户明确 `--force`）

## 命令参考

```
wikihub init <name> --title T [--port P]       # 创建 wiki 根
wikihub clip <name> --source PATH              # 收素材
wikihub batch-ingest <name>                    # 批量入典
wikihub serve <name> [--port P] [--host H]     # 起 web
wikihub list                                   # 列本 workspace 全部 wiki
wikihub status <name>                          # 单个 wiki 状态
wikihub stop <name>                            # 停
wikihub logs <name> [--tail N]                 # 看日志
wikihub doctor                                 # 自检
```

## 已知不足

- 嵌入（embed）走的是 SiliconFlow BGE-M3 / OpenAI 兼容端点；没配 `WIKIHUB_EMBED_API_KEY` 时退化为本地启发式
- 没有 LLM 端点时 `crystallize` / `digest` 走本地启发式
- `list` / `stop` 只看当前 workspace 下的 `.wikihub/` —— 这是设计意图，**不是 bug**
