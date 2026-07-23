# WikiHub

WikiHub 是一个**面向多智能体 / 多 workspace / 多 wiki 隔离**的本地知识库管理工具，提供完整的 CLI 来创建、管理和迁移多个并行 wiki。

> **v1.3.0 新增**：迁移能力。`wikihub export / import` 支持跨机器搬运 wiki；`wikihub preflight` 是新机器迁移第一步的环境自检。

中文版：[README.md](README.md) · Skill 入口：[SKILL.md](SKILL.md)

---

## 核心特性

### 1. 26 个命令的统一 CLI

```
Wiki 操作（17）：init / clip / batch-ingest / ingest / ask / query / crystallize /
                digest / viewer / graph / graph-report / entity-merge-review /
                entity-merge-apply / inbox / rebuild-index / doctor / health

隔离护栏 + 运维（9）：serve / list / status / stop / logs / rebuild / preflight /
                     export / import
```

### 2. 端口探测与自动跳转

启动前自动探测空闲端口，**占用就跳下一个空闲端口**（8766-8999 范围）。支持 Linux（/proc/net/tcp）和 macOS/Windows（socket bind 回退）。

### 3. PID / Port / Log 三件套

每个 wiki 三个状态文件限定在 `<workspace>/.wikihub/` 下：`NAME.{pid,port,log}`。

### 4. 跨 workspace 安全墙

`stop` 读 `/proc/<pid>/cwd` 验证 PID 归属，跨 workspace 拒绝 kill。

### 5. `batch-ingest` 默认 `--quality all`

启发式默认打 review，`batch-ingest` 自动传 `--quality all`。

### 6. `rebuild` 一键重建

顺序跑 `batch-ingest --quality all → inbox → graph → viewer`，少打 4 条命令。

### 7. `export / import` 跨机器迁移

支持将 wiki 导出为 tar.gz 并在另一台机器导入，包含 manifest.json 元数据校验。

### 8. `preflight` 环境自检

新机器迁移第一步：8 项检查（Python >= 3.8 / markitdown / WIKIHUB_EMBED_* / WIKIHUB_LLM_* / embed 端点 / LLM 端点 / LibreOffice / workspace 可写）。

---

## 快速开始

### 安装

把 WikiHub 整个目录复制到你的 workspace 的 `skills/` 下：

```bash
cp -r WikiHub/ ~/.copaw/workspaces/<your-workspace>/skills/
```

### 配置 .env

```bash
# 1. 复制模板
cp skills/WikiHub/.env.example skills/WikiHub/.env
vim skills/WikiHub/.env    # 填入真实 key

# 2. 第一次跑，先看环境
wikihub preflight
```

**两类配置，必选 vs 可选**：

| 变量 | 必选？ | 用途 | 不配会怎样 |
|---|---|---|---|
| `WIKIHUB_LLM_*` | **必选** | `ask / query / crystallize / digest` 走 AI 问答 | 这几个命令跑不动 |
| `WIKIHUB_EMBED_*` | **可选** | 仅 `entity-merge-review` 流程找出"语义重复但命名不同"的 entity 候选 | review 退化为字符串匹配，仍可用 |

**关键事实**：

- `ask / graph / viewer / build / clip / batch-ingest / rebuild` 这些**核心流程完全不依赖嵌入**——ask 用的是 token 重叠 + n-gram 匹配打分，graph 走 schema v2 的 frontmatter 关系
- `WIKIHUB_EMBED_*` 只在 `entity-merge-review` 流程被使用（找出"语义相近但字符串不同"的 entity）
- 所以**小 wiki（10 个 entity 以内）可以不配嵌入**；50+ entity 命名风格不一致时建议配
- 任何 OpenAI 兼容端点都支持 LLM：MiniMax / OpenAI / Anthropic-via-proxy / 本地 Ollama（qwen2.5:7b 等）

### 创建第一个 wiki

```bash
W=./skills/WikiHub/scripts/wikihub

$W init my-proj --title "我的第一个 wiki" --port 8766
$W clip my-proj --source /path/to/README.md --title "项目 README"
$W clip my-proj --source /path/to/spec.pdf --title "需求规格"
$W rebuild my-proj            # 一键：batch-ingest + viewer + graph + inbox
$W serve my-proj --port 8766
```

打开 `http://localhost:8766/` 看效果。

### 跑第二个 wiki（同时跑）

```bash
$W init client-a --title "客户 A 私有化" --port 8768
$W clip client-a --source ~/Downloads/客户A拓扑.pdf --title "客户A拓扑"
$W rebuild client-a
$W serve client-a --port 8768
```

`http://localhost:8766/` 和 `http://localhost:8768/` 各自跑着**完整功能 + 物理隔离**的 wiki。

### 列出本 workspace 全部 wiki

```bash
$W list
```

### 停

```bash
$W stop client-a   # 按 wiki 名停，不靠端口
```

### 迁移到另一台机器 / workspace

**新机器第一步**：

```bash
$W preflight   # 8 项环境检查
```

**源机器导出**：

```bash
$W export compliance-meeting --out /tmp/cm.tar.gz
# /tmp/cm.tar.gz 含 manifest.json + data/ + port hint，约几十到几百 KB
```

**目标机器导入**：

```bash
$W stop compliance-meeting         # 先停
$W import /tmp/cm.tar.gz --port 8780 --force
$W rebuild compliance-meeting      # 重建 frontmatter + graph.json + viewer.html
$W serve compliance-meeting --port 8780
```

**manifest.json 字段**：

- `wiki` / `title` / `source_workspace` —— 来源标识
- `suggested_port` —— 源端用的端口（导入时可作为 hint）
- `source_count` / `entity_count` —— 内容规模
- `embedding_model` —— 源端配的嵌入模型（**仅记录**，不打包嵌入数据）
- `exported_at` —— 导出时间
- `manifest_version` —— 必须 = 1 才接受（防止跨版本错配）

**关于嵌入**：WikiHub **不缓存 embedding 向量**（每次 ask / graph / entity-merge-review 实时调嵌入 API）。所以 export 也不带嵌入数据。`wikihub rebuild` 不是"重建嵌入"，而是**重建 frontmatter / graph.json / viewer.html / inbox.html**——这些是从源文件衍生的渲染产物，**跨机器重建即可**。

### 收 `.doc` 老 Word 格式

`wikihub clip` 不直接吃 `.doc`（markitdown 只认 `.docx`）。用 `docs/clip-doc.sh` 一行搞定：

```bash
skills/WikiHub/docs/clip-doc.sh compliance-meeting /path/to/某文件.doc --title "某标题"
# 内部：soffice --headless --convert-to docx → wikihub clip
```

---

## 命令参考（26 个）

```
Wiki 操作（17）：
  wikihub init <name> --title T [--port P] [--force]
  wikihub clip <name> --source PATH [--title T]
  wikihub batch-ingest <name>                 # 自动 --quality all
  wikihub ingest <name> --source PATH
  wikihub ask <name> "问题"
  wikihub query <name> "问题" [--title T]
  wikihub crystallize <name> [--from-ask-id ID] [--title T]
  wikihub digest <name>
  wikihub viewer <name>
  wikihub graph <name>
  wikihub graph-report <name>
  wikihub entity-merge-review <name>
  wikihub entity-merge-apply <name> [--identity-key K] [--canonical C]
  wikihub inbox <name>
  wikihub rebuild-index <name>
  wikihub doctor <name>
  wikihub health <name>

隔离护栏 + 运维（9）：
  wikihub serve <name> [--port P] [--host H]
  wikihub list
  wikihub status <name>
  wikihub stop <name>
  wikihub logs <name> [--tail N]
  wikihub rebuild <name>                       # 一键：batch-ingest + viewer + graph + inbox
  wikihub preflight                            # 环境自检（迁移到新机器第一步）
  wikihub export <name> [--out FILE] [--embeddings] [--force]
  wikihub import <input> [--port P] [--force]
```

---

## 许可

MIT

---

## 致谢

WikiHub 基于 ThinkWiki 的完整代码构建，感谢 ThinkWiki 项目的开源贡献。
