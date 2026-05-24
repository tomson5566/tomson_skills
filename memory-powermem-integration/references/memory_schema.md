# PowerMem Memory Schema

## 记忆结构

```
id              : int64          # 主键
content         : string         # 记忆内容（原始文本）
metadata        : JSON           # 元数据（含10个标签）
user_id         : string|null    # 用户ID
agent_id        : string|null    # 代理ID
run_id          : string|null    # 会话ID
scope           : enum           # private|agent_group|user_group|public
memory_type     : enum           # working|short_term|long_term
created_at      : timestamp       # 创建时间
updated_at      : timestamp       # 更新时间
last_searched_at: timestamp|null # 上次搜索时间
search_count    : int            # 搜索次数
```

## metadata 结构 (10个标签)

```json
{
  "tag1_time": "2025-05-24",
  "tag2_topicA": "服务器",
  "tag3_topicB": "AI",
  "tag4_keywordA": "Tomson",
  "tag5_keywordB": "ollama",
  "tag6_keywordC": "hermes",
  "tag7_project": "192.168.3.230",
  "tag8_action": "部署",
  "tag9_status": "成功",
  "tag10_priority": "P1",
  "fulltext_content": "...",
  "last_searched_at": "...",
  "search_count": 0
}
```

## PowerMem CLI 命令

### 添加记忆（推荐格式）

```bash
# 快速写入（跳过推理，3~6s）
pmem memory add "content" \
  --metadata '{"tag1_time":"...","tag2_topicA":"...",...}' \
  --no-infer

# 启用推理模式（35~90s，仅在需要 AI 自动打标签时用）
pmem memory add "content" \
  --metadata '{"tag1_time":"...","tag2_topicA":"...",...}'
```

> ⚠️ `--scope` 和 `--memory-type` 参数**不存在**，会报错。

### 搜索记忆
```bash
pmem memory search "关键词" --limit 10 --json
```

### 获取单条记忆
```bash
pmem memory get [id] --json
```

### 列出所有记忆
```bash
pmem memory list --limit 50 --json
```

### 删除记忆
```bash
pmem memory delete [id]
```