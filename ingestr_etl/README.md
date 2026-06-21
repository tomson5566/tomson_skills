# ingestr_etl

> **一份给"想学 ingestr 的人"的入门 + 进阶材料（v3）**
> 双视角蒸馏：源码（v1-v2 沉淀） + 官方文档（v3 新增）→ 17 references + 4 scripts
> 配套已经装好的二进制 + 校验/生成/演示脚本。

---

## 这是什么

**ingestr** 是 [bruin-data](https://github.com/bruin-data/ingestr) 出品的单命令 ETL CLI：70+ 数据源、15+ 数据目标，一个 `ingestr ingest` 命令搬完数据。Go 实现、Apache Arrow + ADBC 内核、FSL 1.1（两年后转 Apache 2.0）。

**ingestr_etl** 是把 ingestr 蒸馏成"理论 + 实战 + 速查 + 帮助"4 层 + **双视角**（源码 + 官方文档）的可复用 skill。

### v3 新增：双视角

| 视角 | 解决什么 | 主要 references |
|---|---|---|
| **源码视角** | "为什么会这样设计" | `internals.md` / `strategy_guide.md` / `schema_management.md` |
| **官方文档视角** | "实际怎么用 + 70 源长啥样" | `migrations.md` / `uri_catalog.md` / `recipes.md` |

| 你想 | 看哪一层 / 哪视角 |
|------|---------|
| "ingestr 为什么会这样设计" | 📖 理论层（internals.md） |
| "我要把 X 搬到 Y"（找 URI） | 📖 文档视角（uri_catalog.md） |
| "我要把 X 搬到 Y"（复制粘贴命令） | 🛠 文档视角（recipes.md） |
| "选对增量策略" | 🛠 实战层（strategy_guide.md） |
| "哪个 flag 控制什么" | ⚡ 速查层（flag_reference + INDEX） |
| "v0→v1 迁移会破坏什么" | 🆘 帮助层（migrations.md） |
| "报错了/跑得慢" | 🆘 帮助层（troubleshooting + performance） |

---

## 🚀 30 秒跑通

```bash
# 0. 确认 ingestr 装了
ingestr --version
# ingestr version v1.0.21

# 1. 5 分钟端到端 demo（SQLite ↔ SQLite，不依赖 ADBC CDN）
bash scripts/first_run.sh

# 2. 一行命令：CSV → DuckDB
ingestr ingest \
  --source-uri 'csv://input.csv' \
  --source-table 'sample' \
  --dest-uri 'duckdb://output.duckdb' --yes
```

完成这三步你已经会 ingestr 了。剩下的 17 篇 references 是**遇到问题或想深入**时再翻。

---

## 5 分钟理解 ingestr（核心模型）

### 三个核心抽象

```
URI（协议前缀） ─── 决定"接哪个源/目标"
  ↓
表（--source-table）── 决定"取什么"
  ↓
策略（--incremental-strategy）── 决定"怎么写"
```

### 6 种增量策略（默认 `replace`）

| 策略 | 一句话 | 用它当 |
|---|---|---|
| `replace` | 整表覆盖 | 表小 / 想要 100% 镜像 |
| `append` | 只追加 | 想保留历史（SCD Type 2） |
| `merge` | 按 PK upsert | 有自然主键 + 只要最新 |
| `delete+insert` | 按 inc_key 删后插 | 干净目标 + 回填 |
| `truncate+insert` | v1 新增：清空后插 | 大表一次性插入 |
| `scd2` | v1 新增：行级历史 | 完整 SCD2 实现 |

### 一个关键认知

> **`ingestr 不会自动从 dest 算 max(incremental_key)`**。你必须显式给 `--interval-start` / `--interval-end`。
> 这是最常见的"为什么我全表扫了"的根因（参见 [`references/strategy_guide.md`](./references/strategy_guide.md) 和 [`references/recipes.md`](./references/recipes.md)）。

### v0→v1 三个最大坑

1. **Stripe 默认 30 天窗口** — 首次迁移必须加 `--full-refresh`
2. **HubSpot 加 `_archived_at` 列** — 下游模型要加 `WHERE _archived_at IS NULL`
3. **嵌套 JSON 不再拍平** — `assignee_id` / `assignee_name` 合并为单列 `assignee` JSON

详见 [`references/migrations.md`](./references/migrations.md)。

---

## 📂 完整结构

```
ingestr_etl/
├── README.md           ← 你正在读的（人类入口）
├── SKILL.md            ← agent 入口（双视角 + 4 层结构）
├── references/         ← 17 篇精修 references
│   ├── INDEX.md        ← 总目录（含 4 条学习路径）
│   │
│   ├── ─── 理论（源码视角） ───
│   ├── internals.md        ← 架构（3 核心接口 + 7 策略 + Arrow/ADBC）
│   ├── strategy_guide.md   ← 7 策略详解 + 决策树 + 翻车表
│   ├── schema_management.md← 4 契约 + 命名 + 演进 + 推断
│   ├── data_handling.md    ← 脱敏 + 自定义 SQL + 列排除
│   │
│   ├── ─── 实战（文档视角） ───
│   ├── quickstart.md       ← 5 分钟 SQLite→DuckDB
│   ├── recipes.md          ← 5 大典型场景（v3 新增）
│   ├── uri_catalog.md      ← 70 源按 12 类全盘点（v3 新增）
│   ├── migrations.md       ← v1 迁移 8 大必读（v3 新增）
│   ├── uri_formats.md      ← URI 模板（精简）
│   ├── patterns.md         ← 17 个实战模式
│   │
│   ├── ─── 速查 ───
│   ├── flag_reference.md   ← 37 flag + 环境变量
│   ├── performance.md      ← 调优 flag + 4 步瓶颈定位
│   │
│   └── ─── 帮助 ───
│   ├── troubleshooting.md  ← 症状→原因→解决
│   ├── best_practices.md   ← 11 章节 + 反模式清单
│   ├── cdc.md              ← Postgres logical replication
│   └── server.md           ← Web UI + creds.json
│
└── scripts/            ← 4 个可执行
    ├── first_run.sh        ← 5 分钟端到端 demo
    ├── ingestr.sh          ← 二进制 wrapper（找/装/执行）
    ├── plan_ingest.py      ← JSON/CLI → ingestr 命令生成器
    └── validate_uri.py     ← URI 语法/白名单校验
```

---

## 🎯 3 条学习路径

### 路径 A：快用型（5-15 分钟）
**你只想"搬个数据"**：
1. `scripts/first_run.sh` 跑通（5 分钟）
2. [`references/recipes.md`](./references/recipes.md) 选最像你场景的 recipe，复制粘贴
3. 遇到问题翻 [`references/troubleshooting.md`](./references/troubleshooting.md)

### 路径 B：理解型（30-60 分钟）
**你想懂 ingestr 怎么工作**：
1. [`references/internals.md`](./references/internals.md) — 架构（3 核心接口 + 7 策略 + Arrow/ADBC）
2. [`references/strategy_guide.md`](./references/strategy_guide.md) — 7 策略详解 + 决策树
3. [`references/schema_management.md`](./references/schema_management.md) + [`references/data_handling.md`](./references/data_handling.md)
4. [`references/uri_catalog.md`](./references/uri_catalog.md) — 浏览 70 源全景（文档视角）
5. [`references/migrations.md`](./references/migrations.md) — 如果从 v0 升级

### 路径 C：文档精读型（1-2 小时）— v3 新增
**你想做选型评估 / 看 ingestr 完整能力**：
1. `scripts/first_run.sh` + [`references/recipes.md`](./references/recipes.md) — 跑通 + 复制粘贴
2. [`references/uri_catalog.md`](./references/uri_catalog.md) — 浏览 70 源全景（**这是文档视角的最大价值**）
3. [`references/migrations.md`](./references/migrations.md) — v1 行为变化清单
4. 跟 [`references/internals.md`](./references/internals.md) 交叉对照

### 路径 D：源码贡献型（2-3 小时）
**你想改 ingestr / 加 connector**：
1. [`references/internals.md`](./references/internals.md) — 概念地图
2. 读 `pkg/source/csv/` — 最小 source 示例
3. 读 `pkg/destination/sqlite/` — 最小 dest 示例
4. 读 `pkg/strategy/replace.go` — 最小 strategy 示例
5. 读 `internal/registry/registry.go` — 核心 registry
6. 读 `pkg/pipeline/pipeline.go::Run()` — 编排
7. 跟着 `internals.md` 的"看源码的路线"扩展

---

## 🛠 实战 5 场景（节选自 recipes.md）

### 场景 1：Stripe 增量同步到 BigQuery
```bash
ingestr ingest \
  --source-uri 'stripe://?api_key=sk_live_xxx' \
  --source-table 'customer' \
  --dest-uri 'bigquery://my-proj?credentials_path=/svc.json&location=EU' \
  --dest-table 'raw.stripe_customers' \
  --incremental-key 'created' --incremental-strategy 'merge' \
  --primary-key 'id' --full-refresh   # ⚠️ v1 首次必须 full-refresh
```

### 场景 2：Postgres → Postgres 按天窗口同步
```bash
ingestr ingest \
  --source-uri 'postgresql://u:p@host/db' \
  --source-table 'public.orders' \
  --dest-uri 'postgresql://u:p@warehouse/db' \
  --dest-table 'warehouse.orders' \
  --incremental-key 'updated_at' --incremental-strategy 'delete+insert' \
  --interval-start "$(date -d 'yesterday' +%F)" \
  --interval-end "$(date +%F)"
```

### 场景 3：自定义 SQL 增量（join 出来增量键）
```bash
ingestr ingest \
  --source-uri 'postgresql://...' \
  --source-table "query:select oi.*, o.updated_at
                  from order_items oi
                  join orders o on oi.order_id = o.id
                  where o.updated_at > :interval_start" \
  --dest-uri 'bigquery://...' --dest-table 'raw.order_items' \
  --incremental-key 'updated_at' --incremental-strategy 'merge' --primary-key 'id'
```

### 场景 4：S3 文件一次性落 DuckDB（探索）
```bash
ingestr ingest \
  --source-uri 's3://?access_key_id=...&secret_access_key=...&region=us-east-1' \
  --source-table 'my-bucket/data/**/*.parquet' \
  --dest-uri 'duckdb:///local.duckdb' --dest-table 'raw.data'
```

### 场景 5：列脱敏（合规）
```bash
ingestr ingest \
  --source-uri 'postgresql://...' \
  --source-table 'customer_data' \
  --dest-uri 'duckdb:///masked.db' --dest-table 'masked_customers' \
  --mask 'email:hash' --mask 'phone:partial:3' \
  --mask 'ssn:redact' --mask 'salary:round:5000'
```

**更多 recipe**：见 [`references/recipes.md`](./references/recipes.md)

---

## 🔧 工具脚本说明

| 脚本 | 用途 | 何时用 |
|---|---|---|
| `scripts/first_run.sh` | 5 分钟端到端 demo（SQLite↔SQLite，不依赖 ADBC CDN） | 第一次跑、给别人演示 |
| `scripts/ingestr.sh` | 二进制 wrapper（找/装/执行） | 跨机器、CI |
| `scripts/plan_ingest.py` | JSON/CLI → ingestr 命令生成器 | 动态生成命令、配置化 ETL |
| `scripts/validate_uri.py` | URI 语法/白名单校验 | 写完 URI 不知道对不对 |

`first_run.sh` 是默认安全的（SQLite↔SQLite 走原生驱动，不下 ADBC CDN）。要跑 DuckDB↔外部源，第一次会从 `dbc-cdn.columnar.tech` 下载 ADBC 驱动，确保网络通。

---

## ❓ 常见问题（FAQ）

### ingestr 装在哪？怎么装？
- 本机已装：`/home/tangzhiang/.local/bin/ingestr`（v1.0.21）
- `scripts/ingestr.sh` 自动找本机 → 找不到则提示安装（不自动安装）
- 三种安装方式（用户级 / 系统级 / opt）详见 `MEMORY.md` "本机已装的 CLI 工具"小节

### 跑命令报 `UNIQUE constraint failed` 怎么办？
大概率是 `--incremental-strategy append` 没配 `--interval-start/end`，导致重复追加。详见 [`references/strategy_guide.md`](./references/strategy_guide.md) 的"interval 必填"小节。

### DuckDB 第一次跑报 CDN 超时？
换 SQLite↔SQLite 测（`first_run.sh` 默认就是这个），或者确保 `dbc-cdn.columnar.tech` 可达。详见 [`references/cdc.md`](./references/cdc.md) 的 ADBC 章节。

### ingestr Python 版（v0）跟 Go 版（v1）能直接迁移吗？
多数能（命令/flag/URI 都不变），但要注意 [`references/migrations.md`](./references/migrations.md) 的 8 大变化。

### ingestr 能做 CDC（变更数据捕获）吗？
能，但不是 ingestr 的核心定位。详见 [`references/cdc.md`](./references/cdc.md)（基于 Postgres logical replication）。

### 怎么调度 ingestr？
ingestr 不做调度。常见组合：cron / Airflow / Dagster / Prefect 包 ingestr 命令。详见 [`references/patterns.md`](./references/patterns.md) 的"Airflow 集成"小节。

---

## 🤔 30 秒决定要不要用 ingestr

### ✅ 用 ingestr 的信号
- 源在 70 个支持列表里（见 [`references/uri_catalog.md`](./references/uri_catalog.md)）
- 目标是一个数仓/数据库（不是 webhook）
- 不需要复杂转换（仅搬运 + 简单增量）
- 想要"cron + 一个命令"的极简部署
- 团队不熟悉 dbt/Airflow，但需要快速搭建管道

### ❌ 别用 ingestr 的信号
- 源不在列表里且没人愿意贡献 connector
- 需要复杂 ETL 转换（ingestr 不做 transformation，只搬运）
- 需要 lineage、data tests、orchestration（DAG）→ 用 dbt + Airflow + Bruin
- 需要 CDC（binlog/CDC 实时同步）→ 用 Debezium/Striim
- 数据量超大（亿级）且要求秒级延迟

**ingestr 在 Bruin 生态中的位置**：
> Bruin（编排） + ingestr（搬运） + SQL 转换 = 完整 ETL 流水线

---

## 📚 资源 & 协议

- **官方文档**：https://bruin-data.github.io/ingestr/
- **仓库**：https://github.com/bruin-data/ingestr

### License
- **ingestr**：Functional Source License 1.1（2 年后转 Apache 2.0）
- **ingestr_etl skill**：与上游同 license
