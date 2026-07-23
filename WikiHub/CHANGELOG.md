# WikiHub CHANGELOG

所有版本的变动记录。格式参考 [Keep a Changelog](https://keepachangelog.com/)。

---

## [1.2.0] - 2026-07-23

### Added
- **MiniMax-M3 LLM 接入**：`WIKIHUB_LLM_*` 配 `https://api.minimaxi.com/v1` + `MiniMax-M3`
  - **走 OpenAI 兼容端点** `/v1/chat/completions`（无需改 llm_client.py）
  - **嵌入依然用 Ollama bge-m3**（不浪费 M3 推理做嵌入）
  - 实测 `wikihub ask` 端到端跑通：检索 5 个相关页面，AI 生成结构化答案 + 证据引用
- **`wikihub rebuild NAME`** 一键重建：batch-ingest + inbox + graph + viewer 顺序跑完

### Changed
- `templates/root/.wiki-schema.md` 第一行改为 `# Wiki Schema · {{TITLE}}`
- `wikihub list` 优先读 `名称：` 行（中文）/ `Name:` 行（英文）作为 title
- `wikihub ask / query` 现在用 `--question QUESTION` 转发到 wikihub_full（之前是位置参数，会被忽略）

### Fixed
- `wikihub list` 不再显示 "Wiki Schema"——现在显示真实项目名

### Verified On
- 23 个命令：init / clip / batch-ingest / ingest / ask / query / crystallize / digest / viewer / graph / graph-report / entity-merge-review / entity-merge-apply / inbox / rebuild-index / rebuild / doctor / health / serve / list / status / stop / logs
- ask 端到端：检索 5 页 → AI 生成 → 结构化输出 + Evidence + Consulted Pages
- list 显示：devops-platform "内部 DevOps 平台 wiki" / client-a "客户 A 私有化 wiki"
- rebuild 一次跑完 batch-ingest + graph（26 nodes / 60 edges）+ viewer（14 pages）

---

## [1.1.0] - 2026-07-23

### Added — 完整功能版
- **完整 25 个 Python 脚本**（独立 `scripts_full/` 目录）
- **独立 `WIKIHUB_*` 命名空间**（`.env` 独立配置）
- **`scripts/wikihub` CLI 扩展到 22 个命令**：
  - Wiki 操作（17 个）：init / clip / batch-ingest / ingest / ask / query / crystallize / digest / viewer / graph / graph-report / entity-merge-review / entity-merge-apply / inbox / rebuild-index / doctor / health
  - 隔离护栏（5 个）：serve / list / status / stop / logs
- **完整 Ollama 嵌入链路**：`WIKIHUB_EMBED_BASE_URL=http://127.0.0.1:11434/v1/embeddings` + `bge-m3`
- **完整知识图谱**：build_graph.py 生成 schema v2 / knowledge view / document view / suggested view
- **`batch-ingest` 默认传 `--quality all`**（启发式默认打 review，跳过 ready 才不卡）

### Changed
- `scripts/wikihub` 重写：保留隔离护栏（list/status/stop/logs/serve），Wiki 操作转发到 `scripts_full/wikihub_full`
- CLI 自动 `load_env()` source `<skill>/.env` 注入 `WIKIHUB_*` 到子进程

### Security
- `stop` 读 `/proc/<pid>/cwd` 验证跨 workspace
- `serve_safe.sh` 拒绝 workspace 路径含 `fqd_pro`

### Verified On
- 日期：2026-07-23
- 平台：Linux 6.12.0（el10_2 x86_64），Python 系统级，Ollama + bge-m3 本地运行
- 多 wiki 共存：devops-platform (8766) + client-a (8768) 同时运行，互不串味

---

## [1.0.0] - 2026-07-23

### Added
- 极简版 WikiHub（端口探测 + PID 文件 + 工作台首页 + 身份 banner）
- 简化版 batch-ingest（只搬文件，不跑嵌入）
- README.md / CHANGELOG.md

### Deprecated（自 1.1.0 起）
- 极简版 viewer / graph（被 wikihub_full 的 schema v2 完整版替代）
- 极简版 banner（被 wikihub_full 的深色 viewer 替代——但身份信息保留在 viewer 的根布局里）

### Known Issues（自 1.1.0 已修复）
- `wikihub list` 显示的 title 已改为读取 frontmatter 中的真实项目名
