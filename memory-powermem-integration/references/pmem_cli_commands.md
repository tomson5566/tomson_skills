# PowerMem CLI 命令参考

> 来源：https://www.powermem.ai/docs/guides/cli_usage/  
> 本地路径：`/root/miniconda3/bin/pmem`

---

## 全局选项（Global Options）

| 选项 | 简写 | 说明 |
|------|------|------|
| `--env-file PATH` | `-f` | 指定 .env 配置文件路径 |
| `--json` | `-j` | 输出 JSON 格式 |
| `--verbose` | `-v` | 显示详细日志（含错误堆栈） |
| `--install-completion SHELL` | — | 安装 shell 补全（bash/zsh/fish/powershell） |
| `--version` | `-h` | 显示版本 |

**注意**：全局选项必须放在子命令之前，如：
```bash
pmem -f .env.production memory list    ✓ 正确
pmem memory list -f .env.production    ✗ 无效
```

---

## 命令总览

| 命令组 | 子命令 | 说明 |
|--------|--------|------|
| `memory` | add, search, get, update, delete, list, delete-all | 记忆的增删改查 |
| `config` | show, validate, test, init | 配置管理 |
| `stats` | (无) | 显示统计信息 |
| `manage` | backup, restore, cleanup, migrate | 备份/恢复/清理/迁移 |

---

## Memory Commands（记忆命令）

### pmem memory add CONTENT

添加新记忆。

**语法**：
```bash
pmem memory add "记忆内容" [OPTIONS]
```

**参数**：
| 参数 | 说明 |
|------|------|
| `CONTENT` | 记忆内容（必填） |

**选项**：
| 选项 | 简写 | 说明 |
|------|------|------|
| `--user-id USER_ID` | `-u` | 用户 ID |
| `--agent-id AGENT_ID` | `-a` | Agent ID |
| `--run-id RUN_ID` | `-r` | Run/Session ID |
| `--metadata JSON` | `-m` | 元数据 JSON，如 `'{"tag1":"value"}'` |
| `--no-infer` | — | 跳过 LLM 推理，加速写入（实测 3~6s） |

**示例**：
```bash
# 基础添加
pmem memory add "用户偏好深色模式"

# 带元数据
pmem memory add "API key 存储在 vault 中" -m '{"category": "security"}'

# 带用户/Agent/Run ID
pmem memory add "周五下午3点会议" -u user1 -a agent1 --no-infer
```

---

### pmem memory search QUERY

语义搜索记忆。

**语法**：
```bash
pmem memory search "查询内容" [OPTIONS]
```

**参数**：
| 参数 | 说明 |
|------|------|
| `QUERY` | 查询关键词（必填） |

**选项**：
| 选项 | 简写 | 说明 |
|------|------|------|
| `--user-id USER_ID` | `-u` | 按用户 ID 筛选 |
| `--agent-id AGENT_ID` | `-a` | 按 Agent ID 筛选 |
| `--run-id RUN_ID` | `-r` | 按 Run/Session ID 筛选 |
| `--limit N` | `-l` | 返回结果数量（默认 10） |
| `--threshold T` | `-t` | 最小相似度分数（如 0.3） |
| `--filters JSON` | `-f` | 附加过滤条件 JSON |
| `--json` | `-j` | 输出 JSON 格式 |

**示例**：
```bash
# 基础搜索
pmem memory search "用户偏好"

# 限制返回5条，JSON输出
pmem memory search "深色模式" -l 5 -j

# 相似度阈值
pmem memory search "123" -t 0.3

# 指定用户搜索
pmem -f .env.production memory search "偏好" --user-id user123
```

**注意**：在 `search` 子命令中 `-f` 是 `--filters`（不是全局的 `--env-file`）。

---

### pmem memory get MEMORY_ID

获取单条记忆详情。

**语法**：
```bash
pmem memory get MEMORY_ID [OPTIONS]
```

**参数**：
| 参数 | 说明 |
|------|------|
| `MEMORY_ID` | 记忆 ID（必填） |

**选项**：
| 选项 | 简写 | 说明 |
|------|------|------|
| `--user-id USER_ID` | `-u` | 访问控制：用户 ID |
| `--agent-id AGENT_ID` | `-a` | 访问控制：Agent ID |
| `--json` | `-j` | 输出 JSON 格式 |

**示例**：
```bash
pmem memory get 123456789
pmem memory get 123456789 --user-id user123
```

---

### pmem memory update MEMORY_ID CONTENT

更新记忆内容和元数据。

**语法**：
```bash
pmem memory update MEMORY_ID "新内容" [OPTIONS]
```

**参数**：
| 参数 | 说明 |
|------|------|
| `MEMORY_ID` | 记忆 ID（必填） |
| `CONTENT` | 新内容（必填） |

**选项**：
| 选项 | 简写 | 说明 |
|------|------|------|
| `--user-id USER_ID` | `-u` | 访问控制：用户 ID |
| `--agent-id AGENT_ID` | `-a` | 访问控制：Agent ID |
| `--metadata JSON` | `-m` | 新元数据 JSON |
| `--json` | `-j` | 输出 JSON 格式 |

**示例**：
```bash
pmem memory update 123456789 "更新后的内容"
pmem memory update 123456789 "新内容" -m '{"updated": true}'
```

---

### pmem memory delete MEMORY_ID

删除单条记忆。

**语法**：
```bash
pmem memory delete MEMORY_ID [OPTIONS]
```

**参数**：
| 参数 | 说明 |
|------|------|
| `MEMORY_ID` | 记忆 ID（必填） |

**选项**：
| 选项 | 简写 | 说明 |
|------|------|------|
| `--user-id USER_ID` | `-u` | 访问控制：用户 ID |
| `--agent-id AGENT_ID` | `-a` | 访问控制：Agent ID |
| `--yes` | `-y` | 跳过确认提示 |

**示例**：
```bash
pmem memory delete 123456789
pmem memory delete 123456789 --yes
```

---

### pmem memory list

列出记忆（支持筛选、分页、排序）。

**语法**：
```bash
pmem memory list [OPTIONS]
```

**选项**：
| 选项 | 简写 | 说明 |
|------|------|------|
| `--user-id USER_ID` | `-u` | 按用户 ID 筛选 |
| `--agent-id AGENT_ID` | `-a` | 按 Agent ID 筛选 |
| `--run-id RUN_ID` | `-r` | 按 Run ID 筛选 |
| `--limit N` | `-l` | 最大返回数量（默认 50） |
| `--offset N` | `-o` | 分页偏移（默认 0） |
| `--sort-by FIELD` | `-s` | 排序字段：created_at, updated_at, id（默认 created_at） |
| `--order [asc\|desc]` | — | 排序方向（默认 desc） |
| `--json` | `-j` | 输出 JSON 格式 |

**示例**：
```bash
pmem memory list --user-id user123
pmem memory list -l 20 -o 0
pmem memory list --sort-by created_at --order desc
```

---

### pmem memory delete-all

批量删除记忆（不可逆）。

**语法**：
```bash
pmem memory delete-all [OPTIONS]
```

**选项**：
| 选项 | 简写 | 说明 |
|------|------|------|
| `--user-id USER_ID` | `-u` | 按用户 ID 筛选 |
| `--agent-id AGENT_ID` | `-a` | 按 Agent ID 筛选 |
| `--run-id RUN_ID` | `-r` | 按 Run ID 筛选 |
| `--confirm` | — | 确认删除（必须） |

**示例**：
```bash
pmem memory delete-all --user-id user123 --confirm
pmem memory delete-all --run-id session1 --confirm
```

---

## Config Commands（配置命令）

### pmem config show

显示当前配置。

```bash
pmem config show [OPTIONS]
```

| 选项 | 简写 | 说明 |
|------|------|------|
| `--section SECTION` | `-s` | 显示某一项：llm, embedder, vector_store, graph_store, intelligent_memory, agent_memory, reranker, all（默认 all） |
| `--show-secrets` | — | 显示 API Key（慎用） |
| `--json` | `-j` | JSON 输出 |

---

### pmem config validate

验证配置文件。

```bash
pmem config validate [OPTIONS]
```

| 选项 | 简写 | 说明 |
|------|------|------|
| `--env-file PATH` | `-f` | 要验证的 .env 文件路径 |
| `--strict` | — | 严格模式（更多检查） |
| `--json` | `-j` | JSON 输出 |

---

### pmem config test

测试数据库、LLM、Embedder 连接。

```bash
pmem config test [OPTIONS]
```

| 选项 | 简写 | 说明 |
|------|------|------|
| `--component COMPONENT` | `-c` | 测试组件：database, llm, embedder, all（默认 all） |
| `--json` | `-j` | JSON 输出 |

---

## Stats（统计）

### pmem stats

```bash
pmem stats [OPTIONS]
```

| 选项 | 简写 | 说明 |
|------|------|------|
| `--user-id USER_ID` | `-u` | 按用户 ID 筛选 |
| `--agent-id AGENT_ID` | `-a` | 按 Agent ID 筛选 |
| `--detailed` | `-d` | 显示更详细的统计 |
| `--json` | `-j` | JSON 输出 |

---

## Manage（管理命令）

### pmem manage backup

导出记忆到 JSON 文件。

```bash
pmem manage backup [OPTIONS]
```

| 选项 | 简写 | 说明 |
|------|------|------|
| `--output PATH` | `-o` | 输出文件路径（默认 powermem_backup_<timestamp>.json） |
| `--user-id USER_ID` | `-u` | 按用户 ID 筛选 |
| `--agent-id AGENT_ID` | `-a` | 按 Agent ID 筛选 |
| `--limit N` | `-l` | 限制导出数量 |

---

### pmem manage restore

从 JSON 备份恢复。

```bash
pmem manage restore -i backup.json [OPTIONS]
```

| 选项 | 简写 | 说明 |
|------|------|------|
| `--input PATH` | `-i` | 备份文件路径（必填） |
| `--dry-run` | — | 预览恢复计划，不实际写入 |
| `--user-id USER_ID` | `-u` | 恢复到指定用户 |

---

### pmem manage cleanup

清理低质量记忆。

```bash
pmem manage cleanup [OPTIONS]
```

| 选项 | 简写 | 说明 |
|------|------|------|
| `--threshold N` | — | 质量阈值（默认 0.2） |
| `--user-id USER_ID` | `-u` | 按用户 ID 筛选 |
| `--dry-run` | — | 预览清理计划 |
| `--force` | — | 强制执行 |

---

### pmem manage migrate

迁移记忆。

```bash
pmem manage migrate [OPTIONS]
```

| 选项 | 简写 | 说明 |
|------|------|------|
| `--threshold N` | `-t` | 迁移阈值 |
| `--delete-source` | — | 迁移后删除源 |
| `--dry-run` | — | 预览迁移计划 |

---

## Shell（交互式模式）

```bash
pmem shell
```

进入交互式 Shell，可输入：
```
powermem> set user user123
powermem> add "用户偏好深色模式"
powermem> search "偏好"
powermem> list --limit 10
powermem> exit
```

---

## Shell Completion（命令补全）

```bash
# Bash
pmem --install-completion bash
# 然后 source ~/.bashrc 或重新打开终端

# Zsh
pmem --install-completion zsh

# Fish
pmem --install-completion fish

# PowerShell
pmem --install-completion powershell
```

---

## 本地实测发现（补充）

以下为在树莓派实测发现，文档可能有出入：

| 发现项 | 说明 |
|--------|------|
| `--no-infer` | 实测有效，跳过 LLM 推理，耗时从 35~90s 降至 3~6s。文档未列出 |
| `--json` 解析卡住 | 部分环境下 JSON 输出会卡住，建议不带 `--json` |
| `--scope` / `--memory-type` | 文档列出，但实测报错 "No such option"，可能是版本差异 |

---

## Skill 中使用的命令速查

| 场景 | 推荐命令 |
|------|----------|
| 添加记忆（快速） | `pmem memory add "[内容]" -m '[10标签JSON]' --no-infer` |
| 搜索记忆 | `pmem memory search "[关键词]" -l 10` |
| 查看单条记忆 | `pmem memory get [ID]` |
| 列出所有记忆 | `pmem memory list -l 50` |
| 测试配置连接 | `pmem config test` |