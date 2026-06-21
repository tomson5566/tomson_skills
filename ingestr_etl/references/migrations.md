# Ingestr v1 迁移必读（来自官方文档）

> **本文件是 v3 新增**。基于官方 `migration-to-v1.html` 精炼。
> 完整材料：`skills/dot-skill/skills/colleague/ingestr/knowledge/documentation_study/parsed/getting-started_migration-to-v1.html.md`

## TL;DR

> **好消息**：`ingest` 命令、所有 flag、所有 URI 都不变，多数 pipeline 直接可用。
> **坏消息**：数据 schema 有 8 大变化 + 多个 source 行为变化，下游 SQL 可能断。

## 8 大必读变化

### 1. 新增 2 个策略
- `truncate+insert` — 清空目标表后一次插入
- `scd2` — SCD Type 2（带 `valid_from` / `valid_to` 行的行级历史）
- `replace` 改用双缓冲（减少大事务时长）

### 2. 嵌套 JSON 不再拍平 ⚠️
- **v0**：`{assignee: {id, name}}` → `assignee_id` + `assignee_name` 两个列
- **v1**：`{assignee: {id, name}}` → 单列 `assignee` JSON
- **影响**：下游所有用 `assignee_id` / `assignee_name` 的查询都要改

### 3. 默认策略变更
- 对无内部增量能力的源（S3 / GCS / Azure Blob 等），无 `--incremental-strategy` 时 v1 默认 `replace`
- **v0**：这些源根据各自实现有不同默认（不可预测）
- **影响**：之前依赖隐式默认的 pipeline 必加显式策略

### 4. BigQuery 权限 ⚠️
- service account 需新增 `roles/bigquery.readSessionUser`
- v1 走 Storage Read API，权限模型更严
- 没加的话：读失败

### 5. Stripe 默认行为变更 ⚠️（最大坑）
- **v0**：一次拉全量历史
- **v1**：默认 events-based，只拉过去 30 天
- **首次迁移**必须加 `--full-refresh`，否则没全量历史
- **回填 30 天前**：设 `--interval-start` 早于 30 天，v1 自动 fall back 到全量 API
- **受影响表**：`account / application_fee / charge / checkout_session / coupon / credit_note / customer / dispute / invoice / invoice_item / payment_intent / payment_link / payment_method / payout / plan / price / product / promotion_code / quote / refund / review / setup_intent / subscription / subscription_schedule / tax_rate / top_up / transfer`
- **不受影响**：`balance_transaction / event / shipping_rate / apple_pay_domain / setup_attempt / subscription_item / tax_code / tax_id / webhook_endpoint`

### 6. HubSpot 大改 ⚠️
详见下文"Per-Source 变更"。

### 7. Notion
- 新增 `--source-table '*'`：拉所有 accessible database
- 仍可指定具体 database ID

### 8. HubSpot 时间窗口过滤
- **v0** 忽略 `--interval-start`
- **v1** 尊重 `interval-start`（通过 Search API 过滤）
- 19 个 CRM 对象都受影响（`contacts / companies / deals / tickets / products / quotes / calls / emails / feedback_submissions / line_items / meetings / notes / tasks / carts / discounts / fees / invoices / commerce_payments / taxes` + custom objects）
- **不受影响**：`owners` / `schemas` 始终走 List API 全量

## Per-Source 变更清单

| Source | v1 变更 | 动作 |
|---|---|---|
| **BigQuery** | 需 `roles/bigquery.readSessionUser` | 加 IAM 角色 |
| **Chess.com** | 表名去掉 `players_` 前缀；删 `players_online_status` | 改 `--source-table`，更新 join |
| **Docebo** | `polls` 合并到 `survey_answers`（多 `poll_id` + `poll_title` 列） | 停止 ingest `polls` |
| **Facebook Ads** | `ad_creatives` 确定性排序；`facebook_insights` 多列；`leads` 只取 leads-related | 期望行数差异 |
| **FundraiseUp** | 全表支持增量；命名 `_incremental` → `:incremental` | 改表名 |
| **Google Sheets** | 重复列名加 `_2` / `_3` 后缀；空 header 变 `column_<idx>` | 检查下游 |
| **HubSpot** | 见下节（最复杂） | 详细审查 |
| **Intercom** | 删 `tickets` 表 | 停止 ingest |
| **Jira** | 新增 3 表（`issue_fields` / `issue_custom_field_contexts` / `issue_custom_field_options`） | 可选启用 |
| **MongoDB** | 大集合内存占用增加 | 调 `--page-size` 或拆日期窗口 |
| **Notion** | `*` 拉所有 database | 用 `*` 或具体 ID |
| **RevenueCat** | 删 `customer_ids` 表（信息合并到 `customers`） | 改 query |
| **Shopify** | 删 `price_rules`（已废弃，用 `discounts`） | 改表名 |
| **Stripe** | 默认 30 天 events-based | 首跑加 `--full-refresh` |
| **Zendesk** | `calls`（全量 replace）和 `calls_incremental`（merge by `id` with `updated_at`）分开 | 改表名 |
| **Zoom** | `users` 默认 `replace` 而非 `merge`；`participants` 全量 upsert by `id`（无 inc key） | 改策略 |

## HubSpot 详细变更（最复杂）

### 新增表
- `pipelines` — 所有 CRM 对象的 sales/service pipeline
- `pipeline_stages` — 每条 pipeline 的 stage
- `property_history:<object>` — 每对象属性变更历史（contacts / deals / companies 等 19 个对象）
- `property_history:custom:<objectType>` — custom object 的属性历史

### 所有 CRM 对象新增 `_archived_at` 列
- `NULL` = 活跃记录
- 填充 = 已归档（soft-deleted）
- **下游影响**：之前 v0 静默丢弃的归档记录现在会出现
- **修复**：下游模型加 `WHERE _archived_at IS NULL`

### `property_history` 可限定列
```bash
--source-table='property_history:contacts:firstname,lastname,email'
```
不指定后缀 = 拉所有属性的历史（数据量大）

### 关联对象可覆盖
```bash
--source-table='contacts:companies,deals'   # 只取这两个关联
--source-table='contacts:'                   # 不取任何关联
```
默认每张表拉一组固定关联（contacts → companies/deals/products/tickets/quotes）

### Custom object 尊重 `--interval-start`
- v0 忽略时间范围
- v1 走 Search API 过滤

### 增量加载方式
- 有 `--interval-start`：走 CRM Search API（按 incremental key 过滤）
- 无 `--interval-start` 或加 `--full-refresh`：走 CRM List API（全量）

## 迁移 checklist

1. **大表先试跑**（在 dev 环境）：
   ```bash
   ingestr ingest --source-uri '...' --source-table 'big_table' --dest-uri '...' --full-refresh
   ```
2. **下游 SQL 审计**：
   - 任何 `assignee_id` / `assignee_name` 风格的扁平列
   - 任何假设"目标表行数 = 源活跃行数"的查询（HubSpot 多了 `_archived_at`）
   - 任何引用 `players_` 前缀的 query（Chess.com）
3. **IAM 检查**（BigQuery 必加角色）
4. **Stripe 首跑**必须 `--full-refresh`
5. **HubSpot** 单独审查（4 个新表 + 1 个新列 + 关联定制）
6. **回退方案**：保留 v0 二进制在 `~/.local/bin/ingestr.v0`，万一 v1 出问题可临时切回
7. **监控**：前 24 小时盯 `delete+insert` 策略的 row count 变化

## 不变的部分（保护你）
- `ingest` 命令名
- 全部 `--source-uri` / `--dest-uri` 格式
- 全部 `--source-table` 引用（除非上面 per-source 表里列了）
- 大部分 flag 名
- 全部增量策略（除了新增的 2 个）

## 求助渠道
- **快**：Bruin Slack `#ingestr` 频道（migration 问题当天答）
- **可跟踪**：https://github.com/bruin-data/ingestr/issues
- 维护者明确说"small questions are welcome"

## 相关 references
- `internals.md` — v1 源码层面的 7 策略实现
- `strategy_guide.md` — 4 策略选型决策树
- `uri_catalog.md` — 受影响 source 的 URI 模板
- `recipes.md` — 迁移场景的 recipe 模板
