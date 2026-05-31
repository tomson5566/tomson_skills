# memory-powermem-integration

**Hermes Agent 记忆集成工具** — 将 AI 会话记忆自动沉淀至 PowerMem，实现长期记忆存储、语义检索与自动备份。

## 📌 项目简介

本项目是一款 **AI 记忆集成与自动化运维工具**，旨在解决 AI Agent 会话记忆中"短期易失、难以检索"的核心痛点。通过与 PowerMem（LLM 记忆数据库）的深度集成，实现会话记忆的自动沉淀、语义搜索与持久化存储，大幅提升 AI 对历史上下文的学习和检索能力。

适用于个人 AI 助手、多 Agent 协作系统、企业知识管理等多种场景，支持定时自动执行、幂等写入、数据库备份等生产级特性。

## ✨ 核心特性

- **按需记忆检索**：AI 在需要时主动搜索 PowerMem 历史记忆，无需定时轮询，避免干扰正常对话流程
- **自动记忆沉淀**：每天凌晨 1:00 自动将 MEMORY.md / USER.md 沉淀至 PowerMem（"做梦"巩固记忆机制）
- **智能 10 标签系统**：每条记忆自动提取时间、主题、关键词、项目、动作、状态、优先级等 10 个维度标签
- **幂等写入机制**：依赖 PowerMem 内部智能去重，无需手动 content hash 检查，写入前自动相似度检测
- **自动数据库备份**：每周日 1:00 自动备份 PowerMem 数据库至 `/root/memory/`，保留 4 周历史版本
- **Ollama Embedding 优化**：解决 Ollama Embedding Base URL 环境变量名陷阱，连接远程 Embedding 服务
- **生产级稳定性**：跳过 LLM 推理（`--no-infer`），写入耗时从 35~90s 降至 3~6s

## 📋 环境依赖

- 操作系统：Linux（CentOS / Ubuntu / Debian）
- 运行环境：Python 3.10+
- 依赖工具：Git, PowerMem CLI (`/root/miniconda3/bin/pmem`)
- 可选：Cron（用于定时任务自动执行）

## 🚀 快速安装

### 一：直接使用

```bash
# 克隆到 Hermes Agent skills 目录（已集成到 Hermes 工作流）
git clone https://github.com/tomson5566/tomson_skills.git \
  ~/.hermes/skills/devops
```

## 💡 快速使用

### 1. 配置环境变量

确保 `/root/.env` 中包含正确的 Ollama Embedding 配置：

```bash
# ⚠️ 注意：PowerMem 只识别这两个变量名
OLLAMA_EMBEDDING_BASE_URL=http://目标地址:11434
# 或
ollama_base_url=http://目标地址:11434

# 不要用这个（PowerMem 不识别）：
# OPEN_EMBEDDING_BASE_URL=...  # ❌ 会导致连接默认 localhost:11434
```

.env_temp文件

```shell
# --- PowerMem + 火山引擎 Coding Plan  ---
# 开发测试推荐使用 SQLite，纯本地无需额外数据库服务
DATABASE_PROVIDER=sqlite
SQLITE_PATH=./data/powermem_dev.db
SQLITE_ENABLE_WAL=true
SQLITE_TIMEOUT=30

# Enable sparse vector
SPARSE_VECTOR_ENABLE=true

# LLM：火山引擎 Coding Plan（ark-code-latest）
LLM_PROVIDER=openai
LLM_API_KEY=  # 换成你的 Coding Plan Key
LLM_MODEL=ark-code-latest
LLM_TEMPERATURE=0.7
LLM_MAX_TOKENS=8192
# Coding Plan 专用端点
OPENAI_LLM_BASE_URL=https://ark.cn-beijing.volces.com/api/coding/v3
LLM_TOP_P=1.0


# Embedding：远程 Ollama（bge-m3:latest）用户要求测试远程欧拉玛
EMBEDDING_PROVIDER=ollama
EMBEDDING_API_KEY=ollama
EMBEDDING_MODEL=embeddinggemma:latest
OLLAMA_EMBEDDING_BASE_URL=http://10.229.190.87:11434
EMBEDDING_DIMS=1024
OCEANBASE_EMBEDDING_MODEL_DIMS=1024
```

### 2. 验证 PowerMem 配置

```bash
# 停掉本机 ollama（避免干扰）
systemctl stop ollama

# 验证远程连接是否正常
pmem config test
# 期望输出：三项全 PASS
(base) root@raspberrypi:~# systemctl stop ollama.service 
(base) root@raspberrypi:~# pmem config test
[INFO] Testing configuration connectivity...
[INFO] Testing database connection...
[SUCCESS] Database: Connected
[INFO] Testing LLM connection...
[SUCCESS] LLM: Connected
[INFO] Testing embedder connection...
[SUCCESS] Embedder: Connected (dims=768)

Results: 3 passed, 0 failed, 0 skipped
```

### 3. 手动触发记忆检索

```bash
# 当用户说 "搜一下之前关于部署的记忆" 时
pmem memory search "部署"

# 查看返回的标签列表，决定是否获取完整内容
pmem memory get <id>
```

### 4. 手动触发记忆沉淀

```bash
# Cron Job 自动执行，或手动调用
python3 scripts/memory_sync.py

# 或直接调用 pmem（推荐带 --no-infer）
pmem memory add "你的记忆内容摘要" \
  --metadata '{"tag1_time":"2025-05-24","tag2_topicA":"服务器",...}' \
  --no-infer
```

### 5. 手动触发数据库备份

```bash
bash scripts/backup_powermem.sh
```

## 📚 详细文档

- [完整流程详解](./README_FLOW.md) — 深入理解记忆沉淀的完整数据流
- [PowerMem CLI 命令参考](./references/pmem_cli_commands.md)
- [故障排查指南](./references/pmem_troubleshooting.md) — 502 错误、Embedding URL 陷阱等
- [PowerMem SQLite 表结构](./references/memory_schema.md)

## 📂 项目结构

```
memory-powermem-integration/
├── SKILL.md                      # 主技能定义（Hermes Agent Skill）
├── README_FLOW.md                # 完整流程详解
├── scripts/
│   ├── memory_sync.py            # 记忆同步脚本（Cron Job 调用）
│   ├── backup_powermem.sh        # 数据库备份脚本（每周日执行）
│   ├── tag_extractor.py          # 标签提取规则（参考）
│   └── read_memory.py            # 记忆读取工具
├── references/
│   ├── pmem_cli_commands.md      # pmem CLI 命令参考
│   ├── pmem_add_behavior.md      # pmem add 实测行为记录
│   ├── pmem_troubleshooting.md  # 故障排查指南
│   └── memory_schema.md          # PowerMem SQLite 表结构
└── README.md                     # 项目说明文档
```

## 💖 支持项目

如果本项目对你有帮助，欢迎 **Star ⭐** 支持！

也欢迎分享给更多 AI 开发者，助力 AI 记忆管理生态建设。

## 📄 开源协议

本项目基于 **Apache License** 开源，可自由用于个人、商业项目，使用时请遵守协议规范。

详细协议内容请查看 [LICENSE](LICENSE) 文件。

---

> 注：部分文档内容由 AI 辅助生成

