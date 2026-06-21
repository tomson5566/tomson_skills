# Ingestr 70+ 源 URI 目录（来自官方文档）

> **本文件是 v3 新增**。基于官方 70 个 `supported-sources/*.html` 精炼。
> 完整材料：`skills/dot-skill/skills/colleague/ingestr/knowledge/documentation_study/parsed/supported-sources_*.md`
> 配套：`uri_formats.md`（v1 旧版，更精简）

## 类别速查

| 类别 | 数量 | 跳转 |
|---|---|---|
| 关系型 DB | 15 | [§ 1](#1-关系型数据库-15) |
| NoSQL / 专用 | 5 | [§ 2](#2-nosql--专用数据库-5) |
| 对象存储 & 文件 & 流 | 5 | [§ 3](#3-对象存储--文件--流-5) |
| 财务 & 支付 | 5 | [§ 4](#4-财务--支付-5) |
| CRM & 销售 | 5 | [§ 5](#5-crm--销售-5) |
| 客服 & 工单 | 3 | [§ 6](#6-客服--工单-3) |
| 协作 & 文档 | 3 | [§ 7](#7-协作--文档-3) |
| 营销 & 广告归因 | 8 | [§ 8](#8-营销--广告归因-8) |
| 产品分析 & 用户反馈 | 6 | [§ 9](#9-产品分析--用户反馈-6) |
| AI & 会议 | 3 | [§ 10](#10-ai--会议-3) |
| 其他长尾 | 10+ | [§ 11](#11-其他长尾-10) |
| 自定义 SQL | 1 | [§ 12](#12-自定义-sql-查询-1) |

---

## § 1. 关系型数据库（15）

| 源 | URI 模板 | 关键参数 / 备注 |
|---|---|---|
| **Postgres** | `postgresql://user:pass@host:5432/db?sslmode=...` | 文档最详细；SSL 模式在 URI |
| **MySQL** | `mysql://user:pass@host:3306/db` | |
| **MSSQL** | `mssql://user:pass@host:1433/db` | |
| **Oracle** | `oracle://user:pass@host:1521/service` | |
| **DB2** | `db2://user:pass@host:50000/db` | |
| **Snowflake** | `snowflake://user:pass@account/db?warehouse=COMPUTE_WH&role=my_role` | warehouse + role 都在 URI |
| **BigQuery** | `bigquery://project?credentials_path=/svc.json&location=EU` | v1 需 `roles/bigquery.readSessionUser` |
| **Redshift** | `redshift://user:pass@host:5439/db` | |
| **Databricks** | `databricks://token:...@host:443/sql/...` | |
| **ClickHouse** | `clickhouse://user:pass@host:9000/db` | |
| **Athena** | `athena://...` | |
| **OneLake** (Fabric) | `onelake://...` | MS Fabric |
| **Spanner** | `spanner://...` | GCP |
| **DuckDB** | `duckdb:///path/to.db` | **默认目标**，零配置；本地首选 |
| **SQLite** | `sqlite:///path/to.db` | 最小本地目标；demo 首选 |

## § 2. NoSQL / 专用数据库（5）

| 源 | URI 模板 | 备注 |
|---|---|---|
| **MongoDB** | `mongodb://user:pass@host:27017/db` | 大集合注意 OOM；调 `--page-size` |
| **Cassandra** | `cassandra://user:pass@host:9042/keyspace` | |
| **Elasticsearch** | `elasticsearch://user:pass@host:9200` | |
| **InfluxDB** | `influxdb://...` | 时序 |
| **DuckDB** | （见 § 1） | 也是目的地 |

## § 3. 对象存储 & 文件 & 流（5）

| 源 | URI 模板 | 关键能力 |
|---|---|---|
| **S3** | `s3://?access_key_id=...&secret_access_key=...&region=us-east-1` | glob 模式 / `.gz` 自动解压 / `#format` / `#encoding` hint / Athena Inventory 大桶加速 / `_ingestr_source_file_modified_at` 时间戳增量 / S3 兼容（Minio/R2/Spaces via `endpoint_url`） |
| **ADLS** (Azure) | `adls://...` | |
| **SFTP** | `sftp://user:pass@host:22/path` | |
| **Kafka** | `kafka://broker:9092/topic` | 流式 |
| **Kinesis** | `kinesis://...` | 流式 |

**S3 `--source-table` 格式**：
```bash
<bucket>/<file-glob-pattern>           # 例：my_bucket/logs/**/*.jsonl
<bucket>/file.csv#jsonl                # 文件类型 hint
<bucket>/file.csv#encoding=windows-1252  # 编码 hint
<bucket>/file.dat#csv,encoding=windows-1252  # 多个 hint 逗号分隔
```

**S3 增量（按对象时间戳）**：
```bash
--incremental-key _ingestr_source_file_modified_at
--interval-start '2026-01-01T00:00:00Z'
```
- 半开区间：`start` 包含，`end` 不包含
- 大桶用 `file_discovery=athena_inventory` 加速
- 新增列：`_ingestr_source_file_modified_at` / `_ingestr_source_file_created_at` / `_ingestr_source_file_path`

## § 4. 财务 & 支付（5）

| 源 | URI 模板 | 备注 |
|---|---|---|
| **Stripe** | `stripe://?api_key=sk_live_xxx` | 30+ 表；v1 默认 30 天事件回看；支持后缀 `:sync` / `:sync:incremental` |
| **QuickBooks** | `quickbooks://?access_token=...&realm_id=...` | |
| **Wise** | `wise://?api_key=...` | |
| **Solidgate** | `solidgate://?api_key=...` | |
| **RevenueCat** | `revenuecat://?api_key=...` | v1 删 `customer_ids` 表 |

**Stripe 表名后缀**：
```bash
charges                       # 标准 async（默认）
charges:sync                  # 全量 sync
charges:sync:incremental      # 增量（必须配 --interval-start/end）
```

## § 5. CRM & 销售（5）

| 源 | URI 模板 | 备注 |
|---|---|---|
| **HubSpot** | `hubspot://?access_token=...` | **v1 改动最大**：新增 3 表 + `_archived_at` 列（详见 `migrations.md`） |
| **Pipedrive** | `pipedrive://?api_token=...` | |
| **Attio** | `attio://?api_key=...` | |
| **Fluxx** | `fluxx://?api_key=...` | |
| **JobTread** | `jobtread://?api_token=...` | |

## § 6. 客服 & 工单（3）

| 源 | URI 模板 | 备注 |
|---|---|---|
| **Intercom** | `intercom://?access_token=...` | v1 删 `tickets` 表 |
| **Jira** | `jira://...` 或 `atlassian://?domain=...&email=...&token=...` | v1 新增 3 个 metadata 表 |
| **ClickUp** | `clickup://?api_token=...` | |

## § 7. 协作 & 文档（3）

| 源 | URI 模板 | 备注 |
|---|---|---|
| **Notion** | `notion://?integration_token=...` | v1 支持 `--source-table '*'` 拉所有 database |
| **Google Sheets** | `gsheets://?credentials_path=...` 或 `gsheets://?credentials=...` | v1 改善重复 header 处理 |
| **Smartsheets** | `smartsheets://?access_token=...` | |

## § 8. 营销 & 广告归因（8）

| 源 | URI 模板 | 用途 |
|---|---|---|
| **Airtable** | `airtable://?access_token=...&base_id=...` | |
| **Mailchimp** | `mailchimp://?api_key=...&server_prefix=...` | |
| **Klaviyo** | `klaviyo://?api_key=...` | |
| **Mixpanel** | `mixpanel://?api_secret=...&project_id=...` | |
| **AppLovin** | `applovin://?api_key=...` | |
| **AppLovin MAX** | `applovin-max://?api_key=...` | |
| **AppsFlyer** | `appsflyer://?api_token=...` | |
| **TikTok Ads** | `tiktok-ads://?access_token=...` | |
| **Reddit Ads** | `reddit-ads://?client_id=...&client_secret=...&refresh_token=...` | |
| **PlusVibe AI** | `plusvibeai://?api_key=...` | |

## § 9. 产品分析 & 用户反馈（6）

| 源 | URI 模板 | 用途 |
|---|---|---|
| **Google Analytics** | `google-analytics://?credentials_path=...&property_id=...` | |
| **SurveyMonkey** | `surveymonkey://?access_token=...` | |
| **Trustpilot** | `trustpilot://?api_key=...&api_secret=...` | |
| **G2** | `g2://?api_key=...` | |
| **Indeed** | `indeed://?api_key=...` | |
| **Phantombuster** | `phantombuster://?api_key=...` | |

## § 10. AI & 会议（3）

| 源 | URI 模板 | 备注 |
|---|---|---|
| **Anthropic** | `anthropic://?api_key=sk-ant-admin-...` | **9 张表**：claude_code_usage / usage_report / cost_report / organization / workspaces / api_keys / invites / users / workspace_members；需 **Admin API key**（不是普通 API key） |
| **Fireflies** | `fireflies://?api_key=...` | 会议记录 AI |
| **Granola** | `granola://?api_key=...` | 会议记录 AI |

## § 11. 其他长尾（10+）

| 源 | URI 模板 | 备注 |
|---|---|---|
| **Chess.com** | `chess://?players=user1,user2` | **免认证**，quickstart 演示用 |
| **Dune** | `dune://?api_key=...` | 链上数据 |
| **Polymarket** | `polymarket://?api_key=...` | 预测市场 |
| **Socrata** | `socrata://?app_token=...&domain=...` | 政府开放数据（SODA） |
| **Frankfurter** | `frankfurter://` | 汇率，**免认证** |
| **Docebo** | `docebo://?client_id=...&client_secret=...&subdomain=...` | LMS |
| **FundraiseUp** | `fundraiseup://?api_key=...` | v1 全表支持增量 |
| **Linear** | `linear://?api_key=...` | |
| **Cursor** | `cursor://?api_key=...` | |
| **Hostaway** | `hostaway://?api_key=...` | |
| **Zoom** | `zoom://?client_id=...&client_secret=...&account_id=...` | v1: users 用 replace；participants 全量 upsert |
| **Bruin** | `bruin://...` | Bruin 平台自身 |

## § 12. 自定义 SQL 查询（1）

**适用于所有 SQL 源**（Postgres / MySQL / Snowflake / BigQuery / ClickHouse / DuckDB / SQLite / Oracle / MSSQL / Redshift / Athena / Databricks / Spanner / Onelake）。

```bash
--source-table "query:select oi.*, o.updated_at
                from order_items oi
                join orders o on oi.order_id = o.id
                where o.updated_at > :interval_start"
```

**支持占位符**：
- `:interval_start` — 自动绑 `--interval-start` 值
- `:interval_end` — 自动绑 `--interval-end` 值

**增量支持**：
- 必须有 `incremental-key` 列
- 必须是 datetime/timestamp
- 必须在 SQL 里自己过滤（用 `:interval_start` 占位符）
- ⚠️ **标记为 experimental**

## 选择决策树

```
你的源是？
├── 数据库 → § 1 / § 2（找对应 DB）
├── 文件/对象 → § 3（S3 最强）
├── SaaS API
│   ├── 支付/财务 → § 4
│   ├── CRM/销售 → § 5
│   ├── 客服/工单 → § 6
│   ├── 协作/文档 → § 7
│   ├── 营销/广告 → § 8
│   ├── 分析/反馈 → § 9
│   └── AI/会议 → § 10
├── 链上/政府/汇率 → § 11
├── 想跑 SQL 拼接 → § 12
└── 找不到 → 70 源之外，自己造 connector（不推荐）
```

## 关于"目的地的 URI"

ingestr 目的地的 URI 是源的**子集**：
- **强支持**（写入性能好）：BigQuery / Snowflake / Redshift / Postgres / Databricks / ClickHouse / DuckDB / SQLite
- **支持**：MSSQL / MySQL / Oracle
- **S3 写出**（以 Parquet + dlt metadata 落盘）
- **Webhook / API**：基本不支持

**经验法则**：源是 70，目的地是 ~15 数仓/数据库，强制你把数据落到真正的数仓。

## 链接

- `uri_formats.md` — v1 旧版（更精简，每类一个示例）
- `migrations.md` — v0→v1 源级变更清单
- `recipes.md` — 5 个典型调用模板
- 完整材料：`skills/dot-skill/skills/colleague/ingestr/knowledge/documentation_study/parsed/`
