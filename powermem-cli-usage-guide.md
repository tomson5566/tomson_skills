# PowerMem CLI 完全使用指南：构建 OpenClaw 的外部记忆外脑

> PowerMem 是一个强大的智能记忆管理系统，它提供了完整的命令行工具 `pmem`，让我们可以在终端中完成记忆的增删改查、配置管理、备份恢复等所有操作。对于 AI 助手如 OpenClaw 来说，PowerMem 可以作为一个优秀的**外部记忆外脑**，扩展自身的记忆能力，实现更高效的知识存储和语义检索。

本文基于官方 [CLI Usage Guide](https://www.powermem.ai/docs/guides/cli_usage) 整理，涵盖从安装到高级使用的完整内容，适合作为日常操作参考手册。

## 目录

- [一、安装与基本调用](#一安装与基本调用)
- [二、全局选项详解](#二全局选项详解)
  - [2.1 全局选项列表](#21-全局选项列表)
  - [2.2 环境文件路径规则](#22-环境文件路径规则)
  - [2.3 使用示例](#23-使用示例)
- [三、命令总览](#三命令总览)
- [四、记忆操作命令](#四记忆操作命令)
  - [4.1 `pmem memory add` - 添加新记忆](#41-pmem-memory-add---添加新记忆)
  - [4.2 `pmem memory search` - 语义搜索记忆](#42-pmem-memory-search---语义搜索记忆)
  - [4.3 `pmem memory get` - 通过 ID 获取记忆](#43-pmem-memory-get---通过-id-获取记忆)
  - [4.4 `pmem memory update` - 更新已有记忆](#44-pmem-memory-update---更新已有记忆)
  - [4.5 `pmem memory delete` - 删除记忆](#45-pmem-memory-delete---删除记忆)
  - [4.6 `pmem memory list` - 列出记忆](#46-pmem-memory-list---列出记忆)
  - [4.7 `pmem memory delete-all` - 批量删除记忆](#47-pmem-memory-delete-all---批量删除记忆)
- [五、配置管理命令](#五配置管理命令)
  - [5.1 `pmem config show` - 查看当前配置](#51-pmem-config-show---查看当前配置)
  - [5.2 `pmem config validate` - 验证配置文件](#52-pmem-config-validate---验证配置文件)
  - [5.3 `pmem config test` - 测试连接性](#53-pmem-config-test---测试连接性)
  - [5.4 `pmem config init` - 交互式初始化配置](#54-pmem-config-init---交互式初始化配置)
- [六、统计信息](#六统计信息)
  - [6.1 `pmem stats` - 显示记忆统计](#61-pmem-stats---显示记忆统计)
- [七、管理命令](#七管理命令)
  - [7.1 `pmem manage backup` - 备份记忆到 JSON 文件](#71-pmem-manage-backup---备份记忆到-json-文件)
  - [7.2 `pmem manage restore` - 从备份恢复记忆](#72-pmem-manage-restore---从备份恢复记忆)
  - [7.3 `pmem manage cleanup` - 基于遗忘曲线清理记忆](#73-pmem-manage-cleanup---基于遗忘曲线清理记忆)
  - [7.4 `pmem manage migrate` - 在存储之间迁移数据](#74-pmem-manage-migrate---在存储之间迁移数据)
- [八、交互式 Shell](#八交互式-shell)
  - [8.1 启动与常用命令](#81-启动与常用命令)
  - [8.2 示例会话](#82-示例会话)
- [九、Shell 自动补全](#九shell-自动补全)
  - [9.1 安装补全脚本](#91-安装补全脚本)
- [十、作为 OpenClaw 记忆外脑的实践方案](#十作为-openclaw-记忆外脑的实践方案)
  - [10.1 为什么需要外部记忆](#101-为什么需要外部记忆)
  - [10.2 推荐工作流](#102-推荐工作流)
  - [10.3 实用示例](#103-实用示例)
- [十一、总结与最佳实践](#十一总结与最佳实践)

---

## 一、安装与基本调用

PowerMem 安装后，CLI 工具有两个入口：

- `pmem` - 主入口（推荐，安装为控制台脚本后默认可用）
- `powermem-cli` - 替代入口

安装非常简单，使用 pip 即可：

```bash
# 安装 PowerMem
pip install powermem

# 验证安装，查看版本和帮助信息
pmem --version
pmem --help
```

如果你没有输入任何子命令，CLI 会输出 "Missing command." 并显示主帮助信息。

**安装验证示例：**
```bash
$ pmem --version
PowerMem 1.0.0
```

## 二、全局选项详解

全局选项属于根命令，**必须放在子命令名称之前**，这是 Click 框架的标准规则，很多人容易在这里搞错。

### 2.1 全局选项列表

| 选项 | 短写 | 描述 |
|------|------|------|
| `--env-file PATH` | `-f` | `.env` 配置文件路径，覆盖默认位置 |
| `--json` | `-j` | 以 JSON 格式输出结果 |
| `--verbose` | `-v` | 启用详细输出，出错时显示堆栈跟踪 |
| `--install-completion SHELL` | - | 为指定 Shell 安装自动补全（bash/zsh/fish/powershell） |
| `--version` | - | 显示 CLI 版本 |
| `--help` | `-h` | 显示帮助信息 |

### 2.2 环境文件路径规则

关于 `--env-file`/`-f` 的使用，需要特别注意：

1. **位置要求**：必须放在子命令之前，例如：
   - ✅ 正确：`pmem -f ./.env.staging memory list`
   - ❌ 错误：`pmem memory list -f ./.env.staging`

2. **作用范围**：对于本次调用，所有的 memory、config、stats、manage、shell 命令都会使用这个环境文件，和设置 `POWERMEM_ENV_FILE` 环境变量效果一样。

3. **特殊情况**：
   - `config validate` 和 `config init` 也接受子命令级别的 `--env-file`/`-f`
   - `memory search` 中，`-f` 表示 `--filters`（JSON 过滤器），**不是**环境文件。如果要指定环境文件，必须放在 `memory` 之前。

### 2.3 使用示例

```bash
# 使用生产环境配置列出所有记忆
pmem -f .env.production memory list

# 使用生产环境配置显示配置
pmem --env-file .env.production config show

# JSON 格式输出统计信息
pmem --json stats

# 详细模式添加一条记忆
pmem -v memory add "User prefers dark mode" --user-id user123

# 为 bash 安装补全
pmem --install-completion bash
```

## 三、命令总览

PowerMem CLI 将所有操作分为五个命令组，结构清晰：

| 命令组 | 子命令 | 功能描述 |
|--------|--------|----------|
| `memory` | add, search, get, update, delete, list, delete-all | 记忆的增删改查和搜索 |
| `config` | show, validate, test, init | 配置查看、验证、测试和初始化 |
| `stats` | (无) | 显示记忆统计信息 |
| `manage` | backup, restore, cleanup, migrate | 备份、恢复、清理、数据迁移 |
| `shell` | (无) | 启动交互式 REPL 模式 |

接下来我们逐个详细介绍每个命令。

## 四、记忆操作命令

所有记忆命令都在 `memory` 分组下，和 Python SDK 使用相同的后端和存储，配置也共用。如果要使用非默认的 `.env` 文件，记得在 `memory` 之前加上全局 `--env-file`/`-f`。

### 4.1 `pmem memory add CONTENT` - 添加新记忆

添加一条新记忆，内容可以是单个事实或简短描述。默认启用推理，系统可能会去重或与已有记忆合并。

**参数：**
- `CONTENT` (必需)：记忆内容，通常是一个句子或短段落。

**选项：**

| 选项 | 短写 | 描述 |
|------|------|------|
| `--user-id USER_ID` | `-u` | 为记忆指定用户 ID |
| `--agent-id AGENT_ID` | `-a` | 为记忆指定代理 ID |
| `--run-id RUN_ID` | `-r` | 指定运行/会话 ID |
| `--metadata JSON` | `-m` | JSON 格式的元数据，例如 `'{"key": "value"}'` |
| `--scope SCOPE` | - | 作用域：private, agent_group, user_group, public |
| `--memory-type TYPE` | - | 记忆类型：working, short_term, long_term |
| `--no-infer` | - | 禁用智能推理（不去重/合并） |
| `--json` | `-j` | JSON 格式输出 |

**使用示例：**

```bash
# 添加一条用户偏好记忆
pmem memory add "User prefers dark mode" --user-id user123

# 添加带分类元数据的安全相关记忆
pmem memory add "API key is stored in vault" -m '{"category": "security"}'

# 添加会议提醒，不启用推理去重
pmem memory add "Meeting at 3pm Friday" -u user1 -a agent1 --no-infer
```

### 4.2 `pmem memory search QUERY` - 语义搜索记忆

根据查询文本的语义相似度搜索记忆，这是 PowerMem 最核心的功能，它基于向量嵌入实现语义检索。

**参数：**
- `QUERY` (必需)：搜索查询文本。

**选项：**

| 选项 | 短写 | 描述 |
|------|------|------|
| `--user-id USER_ID` | `-u` | 按用户 ID 过滤 |
| `--agent-id AGENT_ID` | `-a` | 按代理 ID 过滤 |
| `--run-id RUN_ID` | `-r` | 按运行/会话 ID 过滤 |
| `--limit N` | `-l` | 最大返回结果数（默认 10） |
| `--threshold T` | `-t` | 最小相似度分数（例如 0.3） |
| `--filters JSON` | `-f` | JSON 格式的额外过滤条件 |
| `--json` | `-j` | JSON 格式输出 |

> ⚠️ 注意：在这个子命令中，`-f` 是 `--filters`，不是全局的环境文件选项。如果需要指定环境文件，一定要把 `-f /path/to/.env` 放在 `memory` 之前。

**使用示例：**

```bash
# 搜索用户的偏好相关记忆
pmem memory search "user preferences" --user-id user123

# 搜索关于 dark mode 的内容，最多返回 5 条，JSON 输出
pmem memory search "dark mode" -l 5 -j

# 使用相似度阈值 0.3 过滤
pmem memory search "123" -t 0.3

# 使用生产环境配置搜索用户偏好
pmem -f .env.production memory search "preferences" --user-id user123
```

### 4.3 `pmem memory get MEMORY_ID` - 通过 ID 获取记忆

通过全局 ID 获取单条记忆，可以通过 `--user-id`/`--agent-id` 实施访问控制（只返回属于该用户/代理的记忆）。

**参数：**
- `MEMORY_ID` (必需)：数字类型的记忆 ID。

**选项：**

| 选项 | 短写 | 描述 |
|------|------|------|
| `--user-id USER_ID` | `-u` | 访问控制：用户 ID |
| `--agent-id AGENT_ID` | `-a` | 访问控制：代理 ID |
| `--json` | `-j` | JSON 格式输出 |

**使用示例：**

```bash
# 获取 ID 为 123456789 的记忆
pmem memory get 123456789

# 带用户访问控制获取
pmem memory get 123456789 --user-id user123
```

### 4.4 `pmem memory update MEMORY_ID CONTENT` - 更新已有记忆

更新已有记忆的内容，也可以选择更新元数据。

**参数：**
- `MEMORY_ID` (必需)：数字类型的记忆 ID。
- `CONTENT` (必需)：新的内容。

**选项：**

| 选项 | 短写 | 描述 |
|------|------|------|
| `--user-id USER_ID` | `-u` | 访问控制：用户 ID |
| `--agent-id AGENT_ID` | `-a` | 访问控制：代理 ID |
| `--metadata JSON` | `-m` | 新的 JSON 格式元数据 |
| `--json` | `-j` | JSON 格式输出 |

**使用示例：**

```bash
# 更新记忆内容
pmem memory update 123456789 "Updated content"

# 更新内容同时更新元数据
pmem memory update 123456789 "New content" -m '{"updated": true}'
```

### 4.5 `pmem memory delete MEMORY_ID` - 删除记忆

通过 ID 删除记忆，除非使用 `--yes`，否则会要求确认。

**参数：**
- `MEMORY_ID` (必需)：数字类型的记忆 ID。

**选项：**

| 选项 | 短写 | 描述 |
|------|------|------|
| `--user-id USER_ID` | `-u` | 访问控制：用户 ID |
| `--agent-id AGENT_ID` | `-a` | 访问控制：代理 ID |
| `--yes` | `-y` | 跳过确认步骤 |

**使用示例：**

```bash
# 删除记忆，需要确认
pmem memory delete 123456789

# 直接删除，不需要确认
pmem memory delete 123456789 --yes
```

### 4.6 `pmem memory list` - 列出记忆

列出记忆，支持可选过滤、分页和排序。

**选项：**

| 选项 | 短写 | 描述 |
|------|------|------|
| `--user-id USER_ID` | `-u` | 按用户 ID 过滤 |
| `--agent-id AGENT_ID` | `-a` | 按代理 ID 过滤 |
| `--run-id RUN_ID` | `-r` | 按运行 ID 过滤 |
| `--limit N` | `-l` | 最大结果数（默认 50） |
| `--offset N` | `-o` | 分页偏移（默认 0） |
| `--sort-by FIELD` | `-s` | 排序字段：created_at, updated_at, id（默认 created_at） |
| `--order ORDER` | - | 排序方向：asc 或 desc（默认 desc） |
| `--filters JSON` | `-f` | JSON 格式的额外过滤条件 |
| `--json` | `-j` | JSON 格式输出 |

**使用示例：**

```bash
# 列出某个用户的所有记忆
pmem memory list --user-id user123

# 分页列出，每页 20 条，从第 0 条开始
pmem memory list -l 20 -o 0

# 按创建时间倒序排列
pmem memory list --sort-by created_at --order desc
```

### 4.7 `pmem memory delete-all` - 批量删除记忆

删除符合给定过滤条件的所有记忆，这个操作**不可逆**，需要 `--confirm` 参数和交互式确认。

**选项：**

| 选项 | 短写 | 描述 |
|------|------|------|
| `--user-id USER_ID` | `-u` | 按用户 ID 过滤 |
| `--agent-id AGENT_ID` | `-a` | 按代理 ID 过滤 |
| `--run-id RUN_ID` | `-r` | 按运行 ID 过滤 |
| `--confirm` | - |必需，确认批量删除 |

**使用示例：**

```bash
# 删除某个用户的所有记忆，需要确认
pmem memory delete-all --user-id user123 --confirm

# 删除某个会话的所有记忆，需要确认
pmem memory delete-all --run-id session1 --confirm
```

> ⚠️ 警告：这个操作不可逆，执行前请务必备份！

## 五、配置管理命令

配置命令和 SDK 一样使用 `.env` 文件管理配置。如果要使用非默认环境文件，在 `config` 前面加上全局 `--env-file`/`-f`，或者对于 `config validate` 和 `config init`，也可以在子命令级别使用 `--env-file`/`-f`。

### 5.1 `pmem config show` - 查看当前配置

显示当前配置（从所选 `.env` 文件读取），敏感值（API 密钥、密码）默认会被 masking，除非使用 `--show-secrets`。

**选项：**

| 选项 | 短写 | 描述 |
|------|------|------|
| `--section SECTION` | `-s` | 显示指定部分：llm, embedder, vector_store, graph_store, intelligent_memory, agent_memory, reranker, 或 all（默认） |
| `--show-secrets` | - | 显示 API 密钥和密码（请谨慎使用） |
| `--json` | `-j` | JSON 格式输出 |

**使用示例：**

```bash
# 显示所有配置
pmem config show

# 只显示 llm 部分配置
pmem config show --section llm

# JSON 格式输出
pmem config show -j

# 使用生产环境配置文件显示
pmem -f .env.production config show
```

### 5.2 `pmem config validate` - 验证配置文件

验证配置文件，报告错误和可选警告，使用 `--strict` 会启用更多检查。

**选项：**

| 选项 | 短写 | 描述 |
|------|------|------|
| `--env-file PATH` | `-f` | 要验证的 `.env` 文件路径 |
| `--strict` | - | 启用严格验证 |
| `--json` | `-j` | JSON 格式输出 |

**使用示例：**

```bash
# 验证默认配置
pmem config validate

# 验证生产环境配置
pmem config validate -f .env.production

# 严格模式验证
pmem config validate --strict
```

### 5.3 `pmem config test` - 测试连接性

使用当前配置测试数据库、LLM 和嵌入模型的连接性。

**选项：**

| 选项 | 短写 | 描述 |
|------|------|------|
| `--component COMPONENT` | `-c` | 测试指定组件：database, llm, embedder, all（默认） |
| `--json` | `-j` | JSON 格式输出 |

**使用示例：**

```bash
# 测试所有组件
pmem config test

# 只测试数据库连接
pmem config test -c database

# 只测试 LLM 连接
pmem config test -c llm
```

### 5.4 `pmem config init` - 交互式初始化配置

运行交互式配置向导，创建或更新 `.env` 文件，支持快速启动（最少提示）或自定义（完整模式）。

**选项：**

| 选项 | 短写 | 描述 |
|------|------|------|
| `--env-file PATH` | `-f` | 目标 `.env` 文件（默认自动检测或 `./.env`） |
| `--dry-run` | - | 显示计划更改，不写入文件 |
| `--test` / `--no-test` | - | 写入后运行验证和连接测试（默认不测试） |
| `--component COMPONENT` | `-c` | `--test` 启用时，指定测试哪个组件 |

**使用示例：**

```bash
# 交互式初始化
pmem config init

# 初始化到指定文件
pmem config init -f .env

# 写入后测试数据库连接
pmem config init --test --component database
```

## 六、统计信息

### 6.1 `pmem stats` - 显示记忆统计

显示记忆统计信息，包括总条数、按类型、年龄等分布，支持和其他命令一样的过滤。

**选项：**

| 选项 | 短写 | 描述 |
|------|------|------|
| `--user-id USER_ID` | `-u` | 按用户 ID 过滤 |
| `--agent-id AGENT_ID` | `-a` | 按代理 ID 过滤 |
| `--detailed` | `-d` | 显示更详细的统计 |
| `--json` | `-j` | JSON 格式输出 |

**使用示例：**

```bash
# 显示全局统计
pmem stats

# 显示某个用户的统计
pmem stats -u user123

# JSON 格式输出某个代理的统计
pmem stats --agent-id agent1 -j

# 显示详细统计
pmem stats --detailed
```

## 七、管理命令

### 7.1 `pmem manage backup` - 备份记忆到 JSON 文件

将记忆导出到 JSON 文件，可以通过过滤和限制控制导出哪些记忆。

**选项：**

| 选项 | 短写 | 描述 |
|------|------|------|
| `--output PATH` | `-o` | 输出文件（默认：`powermem_backup_<timestamp>.json`） |
| `--user-id USER_ID` | `-u` | 按用户 ID 过滤 |
| `--agent-id AGENT_ID` | `-a` | 按代理 ID 过滤 |
| `--run-id RUN_ID` | `-r` | 按运行 ID 过滤 |
| `--limit N` | `-l` | 最大导出记忆数（默认 10000） |
| `--include-metadata` | - | 包含元数据（默认 true） |
| `--json` | `-j` | JSON 格式输出状态 |

**使用示例：**

```bash
# 备份到默认文件名
pmem manage backup -o backup.json

# 备份某个用户的记忆到指定文件
pmem manage backup --user-id user123 -o user_backup.json

# 最多备份 1000 条
pmem manage backup -l 1000
```

### 7.2 `pmem manage restore` - 从备份恢复记忆

从 `pmem manage backup` 生成的 JSON 备份文件导入记忆，可以覆盖用户/代理 ID，跳过重复。

**选项：**

| 选项 | 短写 | 描述 |
|------|------|------|
| `--input PATH` | `-i` |必需，输入备份文件 |
| `--user-id USER_ID` | `-u` | 为所有恢复的记忆覆盖用户 ID |
| `--agent-id AGENT_ID` | `-a` | 为所有恢复的记忆覆盖代理 ID |
| `--dry-run` | - | 预览恢复，不实际写入 |
| `--skip-duplicates` | - | 跳过已存在的记忆（默认 true） |
| `--json` | `-j` | JSON 格式输出 |

**使用示例：**

```bash
# 从备份文件恢复
pmem manage restore -i backup.json

# 干跑预览恢复
pmem manage restore -i backup.json --dry-run

# 恢复并覆盖用户 ID
pmem manage restore -i backup.json -u new_user
```

### 7.3 `pmem manage cleanup` - 基于遗忘曲线清理记忆

移除或归档保留分数较低的记忆（基于艾宾浩斯遗忘曲线），使用 `--dry-run` 可以预览。

**选项：**

| 选项 | 短写 | 描述 |
|------|------|------|
| `--threshold T` | `-t` | 删除保留分数低于此值的记忆（默认 0.1） |
| `--archive-threshold T` | - | 归档保留分数低于此值的记忆（默认 0.3） |
| `--user-id USER_ID` | `-u` | 按用户 ID 过滤 |
| `--agent-id AGENT_ID` | `-a` | 按代理 ID 过滤 |
| `--dry-run` | - | 只预览，不修改 |
| `--force` | `-f` | 跳过确认 |
| `--json` | `-j` | JSON 格式输出 |

**使用示例：**

```bash
# 预览清理
pmem manage cleanup --dry-run

# 使用 0.2 阈值删除
pmem manage cleanup --threshold 0.2

# 强制清理某个用户的低保留记忆
pmem manage cleanup -u user123 --force
```

这是一个非常实用的功能，可以让你的记忆库自动保持精简，只保留重要的内容。

### 7.4 `pmem manage migrate` - 在存储之间迁移数据

在不同存储之间迁移数据（例如主存储和子存储），可用性取决于存储后端。

**选项：**

| 选项 | 短写 | 描述 |
|------|------|------|
| `--target-store INDEX` | `-t` |必需，目标子存储索引 |
| `--source-store INDEX` | `-s` | 源子存储索引（默认 main） |
| `--delete-source` | - | 迁移后从源存储删除 |
| `--dry-run` | - | 只预览，不修改 |
| `--json` | `-j` | JSON 格式输出 |

**使用示例：**

```bash
# 预览迁移到存储 0
pmem manage migrate -t 0 --dry-run

# 迁移到存储 1，迁移后删除源数据
pmem manage migrate -t 1 --delete-source
```

## 八、交互式 Shell

### 8.1 启动与常用命令

`pmem shell` 启动交互式 REPL（读取-求值-打印循环），你可以直接运行记忆和统计命令，不需要每次都输入 `pmem memory` 或 `pmem stats`，还可以为会话设置默认 `user_id` / `agent_id`，非常适合日常交互使用。

Shell 内可用命令：

| 命令 | 描述 |
|------|------|
| `add <content> [--user-id id] [--agent-id id]` | 添加一条记忆 |
| `search <query> [--user-id id] [--limit n] [--threshold t]` | 搜索记忆 |
| `get <memory_id> [--user-id id]` | 通过 ID 获取记忆 |
| `update <memory_id> <content> [--user-id id]` | 更新记忆 |
| `delete <memory_id> [--user-id id]` | 删除记忆 |
| `list [--user-id id] [--limit n]` | 列出记忆 |
| `stats [--user-id id]` | 显示统计 |
| `set user <user_id>` | 设置默认用户 ID |
| `set agent <agent_id>` | 设置默认代理 ID |
| `set json on|off` | 启用/禁用 JSON 输出 |
| `show settings` | 显示当前会话设置 |
| `clear` | 清屏 |
| `help` | 显示帮助 |
| `exit`, `quit`, `q` | 退出 Shell |

### 8.2 示例会话

```bash
$ pmem shell

==================================================
 PowerMem Interactive Mode
==================================================
Type 'help' for available commands, 'exit' to quit

powermem> set user user123
powermem> add "User prefers dark mode"
powermem> search "preferences"
powermem> list --limit 10
powermem> exit
```

交互式 Shell 非常适合日常管理记忆，省去重复输入前缀的麻烦，效率更高。

## 九、Shell 自动补全

你可以为 `pmem`（和 `powermem-cli`）安装 Tab 补全，这样在输入命令和选项时，按 Tab 就会自动提示，非常方便。

### 9.1 安装补全脚本

```bash
# Bash
pmem --install-completion bash
# 然后 source ~/.bashrc 或者打开新终端

# Zsh
pmem --install-completion zsh

# Fish
pmem --install-completion fish

# PowerShell
pmem --install-completion powershell
# 然后将打印出的脚本添加到你的 $PROFILE 使其持久化
```

补全脚本会写入 `~/.config/powermem/` 目录，如果你确认，会自动添加 source 行到你的 `~/.bashrc` 或 `~/.zshrc`。Fish 补全安装在 `~/.config/fish/completions/pmem.fish`，PowerShell 会打印安装说明让你手动添加到配置文件。

## 十、作为 OpenClaw 记忆外脑的实践方案

### 10.1 为什么需要外部记忆

OpenClaw 本身有上下文窗口限制，对于长期积累的知识，不可能全部放在当前上下文中。使用 PowerMem 作为外部记忆外脑，可以：

1. **持久化存储**：所有记忆存储在独立的向量数据库中，不受会话重启影响
2. **语义检索**：根据问题语义自动找到相关记忆，不需要精确关键词匹配
3. **分层管理**：支持工作记忆、短期记忆、长期记忆分类，还可以基于遗忘曲线自动清理
4. **多用户/多代理隔离**：可以为不同用户、不同代理维护独立的记忆空间

### 10.2 推荐工作流

对于 OpenClaw 来说，推荐这样使用 PowerMem CLI 作为记忆外脑：

```
1. 遇到需要记住的知识点、决策、结论 → 使用 pmem memory add 保存
2. 回答问题前 → 使用 pmem memory search 搜索相关记忆
3. 定期（每周） → 使用 pmem stats 查看统计，pmem manage cleanup 清理低价值记忆
4. 重要节点 → 使用 pmem manage backup 备份整个记忆库
```

### 10.3 实用示例

**示例 1：记住用户偏好**

```bash
pmem memory add "用户燃烧3906 偏好中文回复，要求操作步骤详细回显" --user-id burning3906 --memory-type long_term
```

**示例 2：记住部署问题和解决方案**

```bash
pmem memory add "部署 PowerMem 时遇到权限问题，无法创建 /root 目录，解决方案是改用 /home/tangzhiang 目录" -m '{"category": "deployment", "problem": "permission denied"}' --memory-type long_term
```

**示例 3：回答问题前检索相关记忆**

```bash
pmem memory search "PowerMem 部署权限问题" --user-id burning3906 --limit 5
```

**示例 4：定期备份**

```bash
# 每周日备份一次
pmem manage backup -o ./backups/powermem-weekly-$(date +%Y%m%d).json
```

## 十一、总结与最佳实践

PowerMem CLI 提供了非常完整的记忆管理能力，总结一下最佳实践：

1. **始终使用正确的选项顺序**：全局选项（特别是 `-f`）放在子命令前面
2. **善用元数据分类**：给记忆添加分类标签，方便后续过滤检索
3. **区分记忆类型**：临时会话内容用 working，短期信息用 short_term，重要知识用 long_term
4. **定期备份**：重要记忆库定期备份到 JSON 文件，防止数据丢失
5. **自动清理**：定期运行 `pmem manage cleanup`，利用遗忘曲线自动清理低价值内容
6. **使用交互式 Shell**：日常管理用 `pmem shell` 更高效，记得安装 Tab 补全
7. **作为外部记忆外脑**：把长期知识存储在 PowerMem 中，每次需要时语义检索，解决上下文窗口限制问题

通过这种方式，PowerMem 可以成为 OpenClaw 非常强大的外部记忆扩展，让 AI 助手真正拥有持续学习和积累知识的能力。

---

**文档信息**
- 来源：https://www.powermem.ai/docs/guides/cli_usage
- 整理：星期五 (ClawOps SRE)
- 日期：2026-05-18
- 位置：`/home/tangzhiang/.openclaw/workspaces/ai_agent_self_upgrade/powermem-cli-usage-guide.md`