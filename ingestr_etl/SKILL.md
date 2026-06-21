---
name: ingestr_etl
description: "Use this skill whenever the user wants to copy, ingest, sync, mirror, replicate, backfill, or move data between databases, SaaS APIs (Stripe, HubSpot, Salesforce, Notion, etc.), file formats (CSV/Parquet/JSON/Avro), or object storage (S3/GCS/ADLS) using ingestr. Triggers include: mentions of 'ingestr', 'ingest data', 'ETL', 'data pipeline', 'sync database to warehouse', 'incremental load', 'append/merge/delete+insert/replace/scd2 strategy', URI patterns like 'postgres://' / 'bigquery://' / 'mongodb://' / 'snowflake://', or specific flag names like '--source-uri' / '--dest-uri' / '--incremental-key'. Use this skill to: (1) translate a data-movement request into an ingestr command, (2) pick the right strategy, (3) construct correct URIs, (4) validate the command before running, (5) troubleshoot errors. Do NOT use for: building dbt models, scheduling/orchestration (use Airflow/Dagster around ingestr), real-time streaming (use Kafka/Flink), or reverse ETL to SaaS that ingestr doesn't support as destination."
license: Functional Source License 1.1 (matches upstream ingestr)
metadata:
  builtin_skill_version: "3.0"
  upstream_version: "ingestr v1.0.21 (bruin-data/ingestr)"
  source: "github.com/bruin-data/ingestr (Go reimplementation codename 'gong')"
  structure: "双视角（源码 + 官方文档）→ 4 层架构（理论/实战/速查/帮助）→ 17 references + 4 scripts"
  perspectives:
    source_code: "v1-v2 沉淀（interview 架构 + 6 维度蒸馏）"
    official_docs: "v3 新增（70 源 + 迁移指南 + 5 recipe）"
---

# ingestr 速览

ingestr 是 bruin-data 出的单命令 ETL CLI：Go 实现、70+ 源、15+ 目标、Apache Arrow + ADBC 内核。
默认策略 `replace`；增量模式 6 种（`append`/`merge`/`delete+insert`/`scd2`/`truncate+insert`/`none`）。

> **设计哲学**：一个命令（`ingestr ingest`）+ 一对 URI（`--source-uri` / `--dest-uri`）+ 一组 flag（37 个）。所有复杂 ETL 都折叠成 1 行 shell。

---

# v3 升级：双视角（源码 + 官方文档）

v3 在 v1-v2 的源码视角基础上，**新增了官方文档视角**，形成"理论 + 实战"双闭环：

| 视角 | 解决什么 | 主要 references |
|---|---|---|
| **源码视角**（理论） | "为什么会这样设计" | `internals.md` / `strategy_guide.md` / `schema_management.md` |
| **文档视角**（实战） | "实际怎么用 + 70 源长啥样" | `migrations.md` / `uri_catalog.md` / `recipes.md` |

**何时查哪个视角？**
- 选型 / 架构 / 改源码 → 源码视角
- 找某个 source 的 URI / 复制粘贴命令 / 看 v1 行为变化 → 文档视角
- 完整 navigation：[`references/INDEX.md`](./references/INDEX.md)

---

# 这份 skill 的 4 层结构

| 层 | 问的是 | 看什么 |
|---|--------|--------|
| **理论** | "ingestr 为什么会这样设计" | `references/internals.md`（架构 + 源码导读）|
| **实战** | "我要搬 X 到 Y，怎么跑" | `references/quickstart.md` + `references/uri_formats.md` + `references/uri_catalog.md` + `references/strategy_guide.md` + `references/patterns.md` + `references/recipes.md` |
| **速查** | "哪个 flag 控制什么" | `references/flag_reference.md` + `references/INDEX.md` |
| **帮助** | "报错了 / 性能差 / 怎么调 / 怎么迁" | `references/troubleshooting.md` + `references/performance.md` + `references/best_practices.md` + `references/migrations.md` |

**完整目录**：[`references/INDEX.md`](./references/INDEX.md)（17 篇 references + 4 scripts）

---

# 何时使用

触发（任一即用）：
- 提到 `ingestr` / 跨库搬数据 / ETL / 数据管道 / 同步到数仓 / 反向 ETL
- 需要选增量策略（`replace`/`append`/`merge`/`delete+insert`/`scd2`）
- 给 URI（`postgres://`, `bigquery://`, `mongodb://` 等）
- 数据迁移/同步/backfill/CDC
- 报 ingestr 错误
- v0 → v1 迁移
- **新增/查询/删除数据源**（连 db_source 表）→ `datasource` 子命令（见下文）

**不**触发：
- 纯 SQL 转换/建模 → dbt
- 调度/依赖/重试 → Airflow/Dagster 包 ingestr
- 实时流（毫秒级） → Kafka/Materialize/Flink
- 需要 GUI → Airbyte/Fivetran

---

# 数据源管理（v3.1 新增）

## 背景

ingestr 跑 ETL 之前需要知道「数据源在哪」。本 skill 通过 **本机 MySQL 的 `datahub.db_source` 表**集中管理所有数据源连接信息，避免每个脚本、每个 URI 写死密码和地址。

> 数据库源清单 = source of truth；`data_sources.md` 只是人类可读的快照。

## CLI：`datasource`（Python）

| 子命令 | 用途 | 示例 |
|--------|------|------|
| `list` | 列出数据源 | `datasource list --type mysql --status active` |
| `show` | 查看详情（密码默认隐藏） | `datasource show MSSQL_HR_133_14 --show-password` |
| `add` | 新增数据源 | `datasource add --code X --name Y --type mysql --host ... --port ...` |
| `update` | 改字段 | `datasource update X --password newpwd --status inactive` |
| `delete` | 软删除（status=archived） | `datasource delete X` |
| `delete --force` | 硬删除 | `datasource delete X --force` |
| `search` | 关键字搜索 | `datasource search hr` |
| `count` | 统计 | `datasource count --type sqlserver` |
| `status` | 改状态 | `datasource status X active` |

## 默认连接

工具默认连**本机 MySQL** `datahub.db_source`：

| 配置 | 默认 | 覆盖方式 |
|------|------|----------|
| 连接方式 | **Unix socket** `/var/lib/mysql/mysql.sock` | `DATAHUB_SOCKET` 环境变量 |
| Host | 空（socket）| `--db-host 1.2.3.4` 或 `DATAHUB_HOST` |
| Port | 3306 | `--db-port 3306` 或 `DATAHUB_PORT` |
| User | root | `--db-user root` 或 `DATAHUB_USER` |
| Password | 空 | `DATAHUB_PASSWORD` 环境变量（**不入 git**）|
| Database | datahub | `DATAHUB_DB` |
| Table | db_source | `DATAHUB_TABLE` |

> ⚠️ 本机 MySQL 8.4 默认禁 TCP（`@@port=0`），所以工具默认走 socket；ingestr 的 MySQL driver 不支持 socket（`pkg/source/mysql/mysql.go`），所以 ingestr 走数据时仍要 TCP，必要时 `socat` 转发或启用 TCP。

## 典型工作流

```bash
# 1) 看看现在注册了哪些源
datasource list

# 2) 拿到某源的连接信息，喂给 ingestr
URI="mysql://$(datasource show MYSQL_188_HUB --show-password | awk '/username/{u=$2} /password/{p=$2} END{print u":"p"@"$1}')"
# （生产建议用 jq + --json 提取）

# 3) 跑 ETL
ingestr ingest \
  --source-uri "$URI" \
  --source-table "orders" \
  --dest-uri "duckdb:///tmp/out.db" \
  --dest-table "orders" --yes
```

## 注册新源（举例）

```bash
datasource add \
  --code MSSQL_HR_133_14 \
  --name "HR 系统主库" \
  --type sqlserver \
  --host 192.168.133.14 \
  --port 1433 \
  --database HR \
  --username sa \
  --password 'rootkit_99852' \
  --charset utf8 \
  --environment prod \
  --status active \
  --description "公司 HR 业务系统，SQL Server 2012" \
  --owner "HR Team"
```

> 密码是明文保存（参考前面对话：用户授权）。生产环境建议转 HashiCorp Vault 或系统 keyring。

## 和 `data_sources.md` 关系

- **`datahub.db_source`**：source of truth（机器读）
- **`references/data_sources.md`**：人类可读的快照（git 跟踪）

新增/修改源后，建议同步更新 `data_sources.md`，或在未来的 `datasource sync-md` 子命令里自动同步。

---

# 已注册的数据源（先查这里）

在拼 URI之前，**先查** [`references/data_sources.md`](./references/data_sources.md) 看用户有没有预登记的数据源。
已注册的源会直接给出 uri_template + transport + auth +已知坑，能省掉从零拼 URI +排查的步骤。

添加新源：直接编辑 `references/data_sources.md`，每个源一段（H2标题 + YAML frontmatter + 正文）。约定见该文件开头。

**当前已注册1 个**：`local-mysql`（本机 MySQL，🟡 degraded — TCP 未启用，需先开端口或做转发）。

---

# 决策流程（30 秒回答"该用哪个策略"）

```
"把 X 搬到 Y"
│
├─ Y 是 ingestr 支持的 destination？查 references/uri_formats.md（精简）或 uri_catalog.md（70 源详细）
│   └─ 不支持 → 改 dlt / Airbyte / 自写
│
├─ X 是哪种源？查 references/uri_catalog.md 看具体 URI 模板
│
├─ 要"最新快照"还是"保留历史"？
│   ├─ 最新快照
│   │   ├─ 数据 < 1 亿行 → replace（默认）
│   │   └─ 数据大 → truncate+insert
│   └─ 保留历史
│       ├─ 有业务 PK → 全部版本？append / 最新？merge
│       ├─ 无业务 PK（事件流）→ delete+insert
│       └─ SCD Type 2 → scd2
│
└─ 显式设 --interval-start / --interval-end（必须！）
   └─ ingestr 不会自动从 dest 算 max(incremental_key)
```

**需要复制粘贴命令**？跳 [`references/recipes.md`](./references/recipes.md)（5 大典型场景）。

---

# 标准工作流（7 步）

## 1. 解析请求
抽：源/目标/增量语义/凭证/特殊需求（脱敏/分区/聚簇/schema 契约）

## 2. 拼 URI
- 找对应源 → [`references/uri_catalog.md`](./references/uri_catalog.md)（70 源按 12 类）
- 常用坑：Postgres 默认 SSL 要加 `?sslmode=disable`、BigQuery 要 SA JSON、文件型必须三斜杠

## 3. 校验 → `scripts/validate_uri.py`
```bash
scripts/validate_uri.py "postgres://u:p@host:5432/db?sslmode=disable"
# OK    postgres://u:p@host:5432/db?sslmode=disable
```

## 4. 生成命令 → `scripts/plan_ingest.py`
```bash
scripts/plan_ingest.py \
  --source-uri "postgres://u:p@host/db" \
  --source-table "users" \
  --dest-uri "bigquery://proj?credentials_path=/sa.json" \
  --dest-table "raw.users" \
  --strategy merge --primary-key id --incremental-key updated_at \
  --interval-start "2026-01-01T00:00:00Z" --interval-end "2026-02-01T00:00:00Z" \
  --no-yes
```

## 5. 试跑（必须）
```bash
ingestr ingest ... --sql-limit 100 --debug --progress log --yes
```

## 6. 正式跑
去掉 `--sql-limit`、加 `--progress log`（CI/agent 必备）

## 7. 排错 → `references/troubleshooting.md`

---

# 命令模板速查

## 首次全量
```bash
ingestr ingest \
  --source-uri "postgres://u:p@host:5432/db" \
  --source-table "users" \
  --dest-uri "bigquery://proj?credentials_path=/sa.json" \
  --dest-table "raw.users" --yes
```

## 增量 append
```bash
ingestr ingest \
  --source-uri "..." --source-table "orders" \
  --dest-uri "..." --dest-table "orders" \
  --incremental-strategy append --incremental-key updated_at \
  --interval-start "2026-02-01T00:00:00Z" --interval-end "2026-03-01T00:00:00Z" --yes
```

## 增量 merge（按主键 upsert）
```bash
ingestr ingest ... \
  --incremental-strategy merge --primary-key id --incremental-key updated_at \
  --interval-start "..." --interval-end "..." --yes
```

## 自定义 SQL
```bash
--source-table "query:SELECT id, name FROM users WHERE active"
```

## 数据脱敏
```bash
--mask "email:hash" --mask "ssn:partial:4" --mask "salary:round:1000"
```

## BigQuery 分区 + 聚簇
```bash
--partition-by event_date --cluster-by user_id,event_type
```

## 严格 schema 契约
```bash
--schema-contract freeze  # 漂移直接失败
```

## 干跑（不写数据）
```bash
--incremental-strategy none
```

## Web UI
```bash
ingestr server --port 8080  # 浏览器开 localhost:8080
```

更多模式看 [`references/patterns.md`](./references/patterns.md)（17 个常见场景）。

---

# 关键提醒

## 给 agent 自己的（自动化时）
- **必加 `--yes`**（否则交互确认卡死）
- **CI/agent 加 `--progress log`**（避免 interactive 进度条卡输出）
- **PII 数据永远加 `--mask`**
- **大表先 `--sql-limit 100` 试跑**
- **merge/delete+insert 时用 `--keep-staging`**（留底好排查）
- **幂等性**：merge ✅ / replace ✅（慢） / append ❌（每次追加）

## 给人类用户的（被问及时提醒）
- ⚠️ `replace` 会**删整表**重建
- ⚠️ `merge` 会 UPDATE（BigQuery/Snowflake 的 UPDATE 收费）
- ⚠️ `delete+insert` 会**删目标表里源表不存在的行**
- ⚠️ **必须**配 `--interval-start/end`，否则 append/merge 会全表扫
- ⚠️ FSL 1.1 协议：不能用 ingestr 整出"竞品"商业 ingestion 服务
- ⚠️ **v1 行为变更**：Stripe 默认 30 天窗口、HubSpot 加 `_archived_at` 列、BigQuery 需额外 IAM 角色 → 详见 [`references/migrations.md`](./references/migrations.md)

---

# 何时不靠我

| 场景 | 替代 |
|------|------|
| "用 dbt 建模" | dbt skill（ingestr 喂数，dbt 建模）|
| "Airflow 调度" | Airflow skill |
| "我看不懂输出" | 先 `--sql-limit 100 --debug --progress log --yes` |
| "ingestr 不支持的源/目标" | 反馈 https://github.com/bruin-data/ingestr/issues，或换 dlt / Airbyte |
| "实时流（毫秒级）" | Kafka/Materialize/Flink |
| "v0 → v1 迁移细节" | 先 [`references/migrations.md`](./references/migrations.md) |
| "我用的 source 不在 70 源里" | 先 [`references/uri_catalog.md`](./references/uri_catalog.md) 确认 |

---

# 资源

- **官方文档**：https://bruin-data.github.io/ingestr/
- **仓库**：https://github.com/bruin-data/ingestr
- **数据源管理 CLI**：`scripts/datasource.py`（v3.1+）
  - 帮助：`datasource --help`
  - 默认连本机 MySQL `datahub.db_source`（Unix socket）
- **本机二进制**：`/home/tangzhiang/.local/bin/ingestr`（v1.0.21）
- **本机 wrapper**：`scripts/ingestr.sh`（自动找/装二进制）

