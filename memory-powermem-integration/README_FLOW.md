# PowerMem 记忆写入完整流程

> 涵盖：AI 如何分析内容 → 提取标签 → 调用 pmem → pmem 内部处理 → 最终写入数据库

---

## 一、整体流程图

```
Cron Job 触发 (每周五 9:00)
        │
        ▼
┌─────────────────────────────┐
│  1. 检查文件修改时间         │
│  Python os.path.getmtime()  │
└────────────┬────────────────┘
             │ 有新修改
             ▼
┌─────────────────────────────┐
│  2. AI 读取文件内容          │
│  /root/.hermes/memories/    │
│     ├── MEMORY.md           │
│     └── USER.md             │
└────────────┬────────────────┘
             │
             ▼
┌─────────────────────────────┐
│  3. AI 分析内容              │
│  提取 10 个标签              │
│  (时间/主题/关键词/项目/动作/  │
│   状态/优先级)               │
└────────────┬────────────────┘
             │
             ▼
┌─────────────────────────────┐
│  4. 调用 pmem memory add     │
│  pmem memory add "[摘要]"    │
│    --metadata '[10标签JSON]' │
│    --no-infer               │
└────────────┬────────────────┘
             │
             ▼
┌─────────────────────────────┐
│  5. pmem 内部处理            │
│  (见下方「二、pmem 内部流程」) │
└────────────┬────────────────┘
             │
             ▼
┌─────────────────────────────┐
│  6. 写入数据库               │
│  PostgreSQL (PowerMem DB)   │
└────────────┬────────────────┘
             │
             ▼
┌─────────────────────────────┐
│  7. 返回写入结果             │
│  通过 weixin 渠道汇报         │
└─────────────────────────────┘
```

---

## 二、pmem 内部处理流程（重点）

当你执行：
```bash
pmem memory add "192.168.3.230 服务器配置: qwenpaw用户环境变量已设置" \
  --metadata '{"tag1_time":"2026-05-24","tag2_topicA":"服务器",...}' \
  --no-infer
```

pmem 内部执行以下步骤：

### Step 1：CLI 接收参数
```
pmem CLI 解析参数
  ├── 内容: "192.168.3.230 服务器配置: qwenpaw用户环境变量已设置"
  ├── metadata: '{"tag1_time":"...","tag2_topicA":"..."}'
  └── --no-infer: 跳过 LLM 推理
```

### Step 2：内容语义拆分（关键机制）

pmem 默认会对输入内容做**语义拆分**，即使你只传入一条摘要，它也可能自动拆成多条记忆。

**实测示例**（无 `--no-infer` 时）：
```
输入: "192.168.3.230 服务器配置: qwenpaw用户环境变量已设置，ollama模型已配置"
输出: 可能生成 2~4 条独立记忆
  ├── 记忆1: 192.168.3.230 服务器配置
  ├── 记忆2: qwenpaw用户环境变量
  ├── 记忆3: ollama模型配置
  └── 记忆4: 服务器整体环境
```

**加了 `--no-infer`**：不拆分，只写入你传入的完整内容。

### Step 3：标签注入

每条生成的记忆都会**继承完整的 metadata**（10个标签）：
```json
{
  "tag1_time": "2026-05-24",
  "tag2_topicA": "服务器",
  "tag3_topicB": "配置",
  "tag4_keywordA": "Tomson",
  "tag5_keywordB": "qwenpaw",
  "tag6_keywordC": "ollama",
  "tag7_project": "192.168.3.230",
  "tag8_action": "配置",
  "tag9_status": "成功",
  "tag10_priority": "P1"
}
```

### Step 4：写入 PostgreSQL 数据库

```
POST /api/memory/add
Content-Type: application/json

{
  "content": "192.168.3.230 服务器配置: qwenpaw用户环境变量已设置",
  "metadata": {...},
  "user_id": <从配置读取>,
  "project_id": <可选>
}
```

数据库字段：
| 字段 | 说明 |
|------|------|
| `id` | 自动生成（int64） |
| `content` | 记忆内容摘要 |
| `metadata` | JSON（10个标签） |
| `user_id` | 用户 ID（可为空） |
| `embedding` | 向量（用于语义搜索） |
| `created_at` | 创建时间 |
| `updated_at` | 更新时间 |

### Step 5：自动生成向量（Embedder）

PowerMem 会调用配置的 embedder（默认 `minimax_embedder`）将内容转为 768 维向量，用于后续语义搜索。

### Step 6：返回写入结果

**正常输出**（无 `--json`，纯文本）：
```
[SUCCESS] Memory added successfully
```

**JSON 输出**（加了 `--json`，注意：会卡住，不推荐）：
```json
{
  "event": "ADD",
  "results": [
    {"id": 713685783025811456, "content": "...", "metadata": {...}},
    {"id": 713685783025811457, "content": "...", "metadata": {...}}
  ]
}
```

---

## 三、10 个标签提取规则（AI 侧）

### 提取位置

Cron Job 中 AI 读取 `/root/.hermes/memories/MEMORY.md` 和 `USER.md` 后，分析内容提取。

### 标签定义与提取示例

| 标签 | 说明 | 提取逻辑 | 示例 |
|------|------|----------|------|
| `tag1_time` | 时间/日期 | 从内容找日期或「周五」等关键词 | `2026-05-24` |
| `tag2_topicA` | 主主题 | 文章主要内容是什么 | `服务器`, `AI`, `运维` |
| `tag3_topicB` | 次主题 | 关联的技术领域 | `部署`, `安全`, `模型` |
| `tag4_keywordA` | 高频词 | 反复出现的名称 | `Tomson`, `qwenpaw` |
| `tag5_keywordB` | 技术栈 | 工具/框架/服务名 | `ollama`, `minimax` |
| `tag6_keywordC` | 工具/服务 | 其他辅助工具 | `hermes`, `openclaw` |
| `tag7_project` | 相关项目 | IP/项目名/服务名 | `192.168.3.230`, `Halo` |
| `tag8_action` | 动作类型 | 做的什么操作 | `安装`, `配置`, `排查` |
| `tag9_status` | 状态 | 操作结果 | `成功`, `失败`, `待处理` |
| `tag10_priority` | 优先级 | 重要程度 | `P0`, `P1`, `P2` |

### 提取示例

**原始内容**（MEMORY.md）：
```
2026-05-23
今天在 192.168.3.230 上配置了 qwenpaw AI 框架。
安装了 ollama 模型服务，配置了环境变量。
Tomson 要求后续每周五自动沉淀记忆到 PowerMem。
```

**提取结果**：
```json
{
  "tag1_time": "2026-05-23",
  "tag2_topicA": "AI框架",
  "tag3_topicB": "配置",
  "tag4_keywordA": "Tomson",
  "tag5_keywordB": "ollama",
  "tag6_keywordC": "hermes",
  "tag7_project": "192.168.3.230",
  "tag8_action": "配置",
  "tag9_status": "成功",
  "tag10_priority": "P1"
}
```

---

## 四、完整调用示例

### 手动测试写入

```bash
# 快速写入（--no-infer，3~6秒）
/root/miniconda3/bin/pmem memory add \
  "192.168.3.230 服务器 qwenpaw 环境变量配置完成" \
  --metadata '{"tag1_time":"2026-05-24","tag2_topicA":"服务器","tag3_topicB":"配置","tag4_keywordA":"qwenpaw","tag5_keywordB":"环境变量","tag6_keywordC":"hermes","tag7_project":"192.168.3.230","tag8_action":"配置","tag9_status":"成功","tag10_priority":"P1"}' \
  --no-infer

# 查看写入结果
/root/miniconda3/bin/pmem memory list

# 查看单条记忆
/root/miniconda3/bin/pmem memory get <id>
```

### 幂等检查（写入前）

```bash
# 搜索相似内容
/root/miniconda3/bin/pmem memory search "192.168.3.230 服务器配置"

# 若返回结果 score > 0.8 且内容高度相似 → 跳过写入
```

---

## 五、文件结构

```
memory-powermem-integration/
├── SKILL.md                          ← 主技能定义
├── README_FLOW.md                    ← 本文件（流程详解）
├── scripts/
│   ├── tag_extractor.py              ← AI 标签提取脚本（参考用）
│   ├── content_hash.py               ← 废弃（幂等由 pmem 内部处理）
│   └── memory_sync.py                ← 沉淀脚本（Cron Job 调用）
├── config/
│   └── tag_config.yaml               ← 标签定义配置
└── references/
    ├── pmem_add_behavior.md          ← pmem add 实测行为记录
    └── memory_schema.md              ← PowerMem 记忆数据模型
```

---

## 六、常见问题

### Q: `--json` 模式会卡住怎么办？
**A**: 不要加 `--json` 参数，直接用纯文本输出模式。

### Q: 单次 add 生成了多条记忆，正常吗？
**A**: 正常，这是 pmem 的语义拆分机制。加 `--no-infer` 可禁用拆分。

### Q: 写入很慢怎么办？
**A**: 加 `--no-infer` 跳过 LLM 推理，耗时从 35~90s 降至 3~6s。

### Q: 如何确保不重复写入？
**A**: pmem 内部有智能去重，写入前可用 `pmem memory search` 检查相似内容。