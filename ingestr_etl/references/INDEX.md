# ingestr 完整指南 — 分类索引（v3）

> **v3 = 源码视角（v1-v2） + 官方文档视角（v3 新增）**，形成"理论 + 实战"双闭环。
> 本文件是 ingestr_etl skill 的"目录"。按使用场景分类，方便快速找到该看的文档。

---

## 0. 视角选择（v3 新增）

ingestr 的学习有**两个视角**，互为补充：

| 视角 | 解决什么 | 在哪 |
|---|---|---|
| **源码视角**（理论） | "为什么这么设计" | `internals.md` / `strategy_guide.md` / `schema_management.md` |
| **官方文档视角**（实战） | "实际怎么用 + 70 源长啥样" | `migrations.md` / `uri_catalog.md` / `recipes.md` |

**建议读法**：先 quickstart 跑通 → 选一个 recipe 复制粘贴 → 遇到"为什么"翻源码视角 → 遇到"具体哪个 source 怎么调"翻文档视角。

---

## 1. 入门（5 分钟跑通）

| 文档 | 何时读 |
|------|--------|
| [`quickstart.md`](./quickstart.md) | 第一次跑，5 分钟 SQLite→DuckDB |
| [`recipes.md`](./recipes.md) | **v3 新增** — 5 个典型场景的复制粘贴模板（Stripe→BQ、PG→PG、S3→DuckDB、脱敏、自定义 SQL） |

跑通 quickstart + 选个 recipe 就能干活。

## 2. 理论（读懂源码再用工具）

ingestr 是"看起来简单"但"内部设计讲究"的工具。强烈建议读完 quickstart 后再看：

| 文档 | 何时读 |
|------|--------|
| [`internals.md`](./internals.md) | **第一次**接触 ingestr（理解为什么这么设计）|
| [`strategy_guide.md`](./strategy_guide.md) | 7 个策略详解 + 决策树 + 翻车场景 |
| [`schema_management.md`](./schema_management.md) | 4 契约 + 命名约定 + 演进 + 推断 |
| [`data_handling.md`](./data_handling.md) | 脱敏 / 自定义 SQL / 列排除 |

读完 `internals.md`，CLI 的所有行为都能反推到源码。

## 3. 文档视角实战（v3 新增）

| 文档 | 何时读 |
|------|--------|
| [`uri_catalog.md`](./uri_catalog.md) | **v3 新增** — 70 源按 12 类盘点（DB/NoSQL/对象存储/财务/CRM/客服/协作/营销/分析/AI/长尾）+ URI 模板 |
| [`migrations.md`](./migrations.md) | **v3 新增** — v0→v1 8 大必读变化 + per-source 变更清单 + HubSpot 详细审查 |
| [`recipes.md`](./recipes.md) | 5 个典型场景的复制粘贴模板（含完整命令 + 为什么 + 踩坑） |

## 4. 参考手册（按需查）

| 文档 | 内容 |
|------|------|
| [`uri_formats.md`](./uri_formats.md) | 30+ 源/目标的 URI 模板 + 归一化规则（精简版） |
| [`flag_reference.md`](./flag_reference.md) | 37 个 flag 完整参考 + 环境变量 |
| [`uri_catalog.md`](./uri_catalog.md) | **v3 新增** — 70 源按 12 类全盘点（详细版） |

## 5. 操作指南（按任务分类）

| 任务 | 看 |
|------|----|
| 选对增量策略 | [`strategy_guide.md`](./strategy_guide.md) |
| 写 URI | [`uri_formats.md`](./uri_formats.md)（精简）或 [`uri_catalog.md`](./uri_catalog.md)（详细） |
| 处理 schema 漂移 / 命名约定 / 推断 | [`schema_management.md`](./schema_management.md) |
| 脱敏 / 自定义 SQL / 列排除 | [`data_handling.md`](./data_handling.md) |
| 性能调优（page-size、并行、分片）| [`performance.md`](./performance.md) |
| CDC（变更数据捕获）| [`cdc.md`](./cdc.md) |
| 跑 Web UI server | [`server.md`](./server.md) |
| **v1 迁移** | [`migrations.md`](./migrations.md) |
| **复制粘贴一个常见场景** | [`recipes.md`](./recipes.md) |

## 6. 实战模式

| 文档 | 内容 |
|------|------|
| [`patterns.md`](./patterns.md) | 17 个常见场景的复制粘贴模板（首次全量+增量、backfill、多表批量、生产到 dev、SaaS→Warehouse、MongoDB→SQL、Airflow 集成、Makefile 集成 等）|
| [`best_practices.md`](./best_practices.md) | 起步、策略选择、schema、性能、安全、错误处理、迁移、反模式的全套"什么时候做/不做"清单 |

## 7. 排错

| 文档 | 内容 |
|------|------|
| [`troubleshooting.md`](./troubleshooting.md) | 按"症状→原因→解决"分类，覆盖连接、schema、权限、性能、增量、URI、安装、调试；末尾 `datasource CLI 排错` 节（`datasource add` 静默输出、shell `---` 误解析、密码从 .env 传参模板） |

## 8. 快速定位

**"我要……" → 看哪篇**

| 我要 | 看 |
|------|----|
| 跑通第一次 | `quickstart.md` |
| 懂 ingestr 为什么这么设计 | `internals.md` |
| 把 X 表搬到 Y（找 URI 模板） | `uri_catalog.md`（70 源详细）或 `uri_formats.md`（精简） |
| 复制粘贴一个常见场景 | `recipes.md`（5 大典型）|
| 选对增量策略 | `strategy_guide.md` |
| 调通脱敏 / 选列 / 过滤 | `data_handling.md` |
| 解决 schema 漂移 | `schema_management.md` |
| 跑得更快 | `performance.md` |
| 跑 CDC 实时同步 | `cdc.md` |
| 给非工程师用（Web UI）| `server.md` |
| v0→v1 迁移 | `migrations.md` |
| 知道"什么时候不该用 ingestr" | `best_practices.md`（反模式章节）|
| 报错了 | `troubleshooting.md` |
| 查某个 flag | `flag_reference.md` |
| 看其他 17 个场景 | `patterns.md` |
| 用已注册的数据源（先查这里） | [`data_sources.md`](./data_sources.md)（用户预登记的源 + 连接信息 +坑） |
cat
-A
/tmp/new_row1.md
| 用已注册的数据源（先查这里） | [`data_sources.md`](./data_sources.md)（用户预登记的源 + 连接信息 +坑） |
cat
-A
/tmp/new_row1.md
| 用已注册的数据源（先查这里） | [`data_sources.md`](./data_sources.md)（用户预登记的源 + 连接信息 +坑） |
cat
-A
/tmp/new_row1.md

## 9. 阅读路径（建议）

### 路径 A：快用型（5-15 分钟）
1. `quickstart.md` — 5 分钟跑通
2. `recipes.md` — 选最像你场景的那个，复制粘贴
3. 遇到问题翻 `troubleshooting.md`

### 路径 B：理解型（30-60 分钟）
1. `internals.md` — 理解架构
2. `strategy_guide.md` — 理解策略
3. `schema_management.md` + `data_handling.md` — 理解数据处理
4. `performance.md` — 理解性能
5. `uri_catalog.md` — 浏览 70 源全景
6. `migrations.md` — 如果是从 v0 升级

### 路径 C：文档精读型（1-2 小时）— v3 新增
1. `quickstart.md` + `recipes.md` — 跑通 + 复制粘贴
2. `uri_catalog.md` — 浏览 70 源全景（**这是文档视角的最大价值**）
3. `migrations.md` — v1 行为变化清单
4. 跟 `internals.md` 交叉对照（"源码怎么做" vs "文档怎么写"）

### 路径 D：源码贡献型（2-3 小时）
1. `internals.md` — 概念地图
2. 读 `pkg/source/csv/` — 最小 source 示例
3. 读 `pkg/destination/sqlite/` — 最小 dest 示例
4. 读 `pkg/strategy/replace.go` — 最小 strategy 示例
5. 读 `internal/registry/registry.go` — 核心 registry
6. 读 `pkg/pipeline/pipeline.go::Run()` — 编排
7. 跟着 `internals.md` 的"看源码的路线"扩展

## 10. 速查（命令模板）

**首次全量**：
```bash
ingestr ingest --source-uri "..." --source-table "..." \
  --dest-uri "..." --dest-table "..." --yes
```

**增量 append**（必须配 interval）：
```bash
ingestr ingest --source-uri "..." --source-table "..." \
  --dest-uri "..." --dest-table "..." \
  --incremental-strategy append --incremental-key updated_at \
  --interval-start "2026-02-01T00:00:00Z" --interval-end "2026-03-01T00:00:00Z" --yes
```

**增量 merge**（必须配 interval）：
```bash
ingestr ingest --source-uri "..." --source-table "..." \
  --dest-uri "..." --dest-table "..." \
  --incremental-strategy merge --primary-key id --incremental-key updated_at \
  --interval-start "2026-02-01T00:00:00Z" --interval-end "2026-03-01T00:00:00Z" --yes
```

**带脱敏**（见 `recipes.md` Recipe 5）：
```bash
ingestr ingest ... --mask "email:hash" --mask "ssn:partial:4" --yes
```

**自定义 SQL**（见 `recipes.md` Recipe 3）：
```bash
ingestr ingest --source-uri "..." \
  --source-table "query:SELECT id, name FROM users WHERE active" \
  --dest-uri "..." --dest-table "..." --yes
```

**MongoDB → SQL**：
```bash
ingestr ingest ... --columns "id:string,name:string,created_at:timestamp" \
  --no-inference --yes
```

**试跑**：
```bash
ingestr ingest ... --sql-limit 100 --debug --progress log --yes
```

## 11. 文件清单（v3，共 17 篇）

```
references/
├── INDEX.md               # 本文件（分类导航，v3）
├── internals.md           # 架构（源码理论）
├── quickstart.md          # 5 分钟上手
├── ─── 文档视角（v3 新增） ───
├── migrations.md          # v0→v1 8 大必读 + per-source 变更
├── uri_catalog.md         # 70 源按 12 类全盘点
├── recipes.md             # 5 大典型场景
├── ─── 源码视角（v1-v2） ───
├── uri_formats.md         # URI 模板速查（精简）
├── flag_reference.md      # 37 flag 参考
├── strategy_guide.md      # 7 策略详解 + 决策树
├── schema_management.md   # Schema 契约/命名/演进/推断
├── data_handling.md       # 脱敏/自定义SQL/列排除
├── performance.md         # 性能调优
├── cdc.md                 # CDC（变更数据捕获）
├── server.md              # Web UI server
├── patterns.md            # 17 个实战模式
├── best_practices.md      # 最佳实践 + 反模式
└── troubleshooting.md     # 排错
```

## 12. 资源（v3 双源）

### Skill 本身
- **本 skill**：`/home/tangzhiang/.copaw/workspaces/data_etl_agent/skills/ingestr_etl/`
- **SKILL.md**（机器入口）/ **README.md**（人类入口）

### 源码视角材料
- **蒸馏过程稿**（3 篇 dot-skill 6 维度原笔记 + 早期合并稿）：`../dot-skill/skills/colleague/ingestr/knowledge/research/`
- **源码**：`docs/ingestr-1.0.21.zip`
- **源码解压**：`workspace/ingestr_src/ingestr-1.0.21/`
- **二进制**：`/home/tangzhiang/.local/bin/ingestr`（已装 v1.0.21）
- **上游**：https://github.com/bruin-data/ingestr

### 文档视角材料（v3 新增）
- **官方文档抓取产物**（78 HTML + 79 MD + 6 脚本 + 1 SUMMARY）：`../dot-skill/skills/colleague/ingestr/knowledge/documentation_study/`
- **官方文档站点**：https://bruin-data.github.io/ingestr/
- **合并摘要**（`merged_documentation.md`）：`../dot-skill/skills/colleague/ingestr/knowledge/research/merged/merged_documentation.md`
- **抓取脚本**（可重用，抓其他 VuePress 2 站点）：`../dot-skill/skills/colleague/ingestr/knowledge/documentation_study/{scrape,parse,cleanup}.py`

### 元信息
- **dot-skill meta.json**（含全部知识源 + 蒸馏元信息）：`../dot-skill/skills/colleague/ingestr/meta.json`
