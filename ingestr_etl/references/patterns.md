# 实战模式 / 配方

> 常见场景的"开箱即用"模板。每个都能直接复制粘贴改 URI 就跑。

## 1. 首次全量 + 之后增量

```bash
# 第一次：全量跑
ingestr ingest \
  --source-uri "$SRC" --source-table "users" \
  --dest-uri "$DEST" --dest-table "users" \
  --yes

# 之后：增量（append，必须配 interval）
ingestr ingest \
  --source-uri "$SRC" --source-table "users" \
  --dest-uri "$DEST" --dest-table "users" \
  --incremental-strategy append \
  --incremental-key updated_at \
  --interval-start "2026-02-01T00:00:00Z" \
  --interval-end "2026-03-01T00:00:00Z" \
  --yes
```

## 2. Backfill 某段时间

```bash
# 跑 1 月份
ingestr ingest ... \
  --incremental-strategy append \
  --incremental-key created_at \
  --interval-start "2026-01-01T00:00:00Z" \
  --interval-end "2026-02-01T00:00:00Z" \
  --yes

# 跑 2 月份
ingestr ingest ... \
  --incremental-strategy append \
  --incremental-key created_at \
  --interval-start "2026-02-01T00:00:00Z" \
  --interval-end "2026-03-01T00:00:00Z" \
  --yes
```

## 3. 多表批量跑

```bash
#!/bin/bash
# 串行
for table in users orders products events; do
  ingestr ingest \
    --source-uri "$SRC" --source-table "$table" \
    --dest-uri "$DEST" --dest-table "$table" \
    --incremental-strategy append \
    --incremental-key updated_at \
    --interval-start "$START" --interval-end "$END" \
    --yes
done
```

```bash
# 并行（4 个并发）
TABLES="users orders products events"
echo "$TABLES" | xargs -n1 -P4 -I{} \
  ingestr ingest \
    --source-uri "$SRC" --source-table "{}" \
    --dest-uri "$DEST" --dest-table "{}" \
    --yes
```

## 4. 生产到 dev（带脱敏）

```bash
ingestr ingest \
  --source-uri "postgres://u:p@prod.db/internal" \
  --source-table "users" \
  --dest-uri "duckdb:///dev.db" \
  --dest-table "users" \
  --mask "email:hash" \
  --mask "ssn:partial:4" \
  --mask "phone:nullify" \
  --mask "salary:round:1000" \
  --yes
```

## 5. SaaS → Warehouse

```bash
# Stripe → BigQuery
ingestr ingest \
  --source-uri "stripe://sk_test_xxx@api.stripe.com/v1" \
  --source-table "charges" \
  --dest-uri "bigquery://proj?credentials_path=/sa.json" \
  --dest-table "stripe.charges" \
  --incremental-strategy append \
  --incremental-key created \
  --interval-start "2026-01-01T00:00:00Z" \
  --interval-end "2026-02-01T00:00:00Z" \
  --yes
```

```bash
# HubSpot → Snowflake
ingestr ingest \
  --source-uri "hubspot://pat-na1-xxx@api.hubapi.com" \
  --source-table "contacts" \
  --dest-uri "snowflake://u:p@a/db/schema?warehouse=WH&role=R" \
  --dest-table "hubspot.contacts" \
  --incremental-strategy merge \
  --incremental-key updatedat \
  --interval-start "2026-01-01T00:00:00Z" \
  --interval-end "2026-02-01T00:00:00Z" \
  --primary-key id \
  --yes
```

## 6. 多源汇聚到一个目标

```bash
# 源 A: PG
ingestr ingest --source-uri "postgres://..." --source-table "events_pg" --dest-uri "bigquery://..." --dest-table "events" --yes

# 源 B: Stripe
ingestr ingest --source-uri "stripe://..." --source-table "events_stripe" --dest-uri "bigquery://..." --dest-table "events" --yes

# 源 C: HubSpot
ingestr ingest --source-uri "hubspot://..." --source-table "events_hubspot" --dest-uri "bigquery://..." --dest-table "events" --yes
```

**注意**：同目标表会互相覆盖。解决：分目标表（`events_pg`, `events_stripe`），下游用 `UNION ALL`。

## 7. 自定义 SQL 走 query:

```bash
# 只拉活跃用户
ingestr ingest \
  --source-uri "postgres://..." \
  --source-table "query:SELECT id, name, email FROM users WHERE active = true AND created_at > '2026-01-01'" \
  --dest-uri "..." \
  --dest-table "active_users" \
  --yes

# 聚合（注意下游要再处理）
ingestr ingest \
  --source-uri "postgres://..." \
  --source-table "query:SELECT DATE_TRUNC('day', created_at) AS day, COUNT(*) AS cnt FROM events GROUP BY 1" \
  --dest-uri "..." \
  --dest-table "events_daily" \
  --strategy replace \
  --yes
```

## 8. MongoDB → SQL

```bash
# 1. 先看 schema（用 --columns 试错）
ingestr ingest \
  --source-uri "mongodb://u:p@host:27017/db" \
  --source-table "events" \
  --dest-uri "duckdb:///out.db" \
  --dest-table "events" \
  --columns "id:string,event_type:string,timestamp:timestamp,payload:json" \
  --no-inference \
  --yes

# 2. 验证类型对后，去掉 --no-inference 让 ingestr 推断
ingestr ingest \
  --source-uri "mongodb://u:p@host:27017/db" \
  --source-table "events" \
  --dest-uri "bigquery://..." \
  --dest-table "events" \
  --columns "id:string,event_type:string,timestamp:timestamp,payload:json" \
  --no-inference \
  --yes
```

## 9. 文件型 → Warehouse

```bash
# CSV → BigQuery
ingestr ingest \
  --source-uri "csv:///data/users.csv" \
  --source-table "users" \
  --dest-uri "bigquery://proj?credentials_path=/sa.json" \
  --dest-table "raw.users" \
  --yes

# Parquet → Snowflake（保留类型）
ingestr ingest \
  --source-uri "parquet:///data/events.parquet" \
  --source-table "events" \
  --dest-uri "snowflake://..." \
  --dest-table "events" \
  --yes

# 多文件（S3 路径）
ingestr ingest \
  --source-uri "s3://bucket/data/*.parquet?region=us-east-1&access_key=...&secret_key=..." \
  --source-table "events" \
  --dest-uri "..." \
  --dest-table "events" \
  --yes
```

## 10. BigQuery 分区表

```bash
ingestr ingest \
  --source-uri "postgres://..." \
  --source-table "events" \
  --dest-uri "bigquery://proj?credentials_path=/sa.json" \
  --dest-table "events" \
  --partition-by event_date \
  --cluster-by user_id,event_type \
  --yes
```

## 11. 失败重试

```bash
#!/bin/bash
# retry.sh
for i in 1 2 3; do
  if ingestr ingest ... --yes; then
    exit 0
  fi
  echo "attempt $i failed, retry in 30s"
  sleep 30
done
exit 1
```

## 12. Airflow BashOperator

```python
from airflow.operators.bash import BashOperator

ingest_task = BashOperator(
    task_id="ingest_users",
    bash_command=(
        "ingestr ingest "
        "--source-uri '{{ var.value.src_uri }}' "
        "--source-table users "
        "--dest-uri '{{ var.value.dest_uri }}' "
        "--dest-table users "
        "--incremental-strategy append "
        "--incremental-key updated_at "
        "--interval-start '{{ ds }}' "
        "--interval-end '{{ next_ds }}' "
        "--yes"
    ),
    retries=3,
    retry_delay=timedelta(minutes=1),
)
```

## 13. Makefile

```makefile
INGEST_FLAGS = --source-uri "$(SRC_URI)" \
               --source-table "$(TABLE)" \
               --dest-uri "$(DEST_URI)" \
               --dest-table "$(TABLE)" \
               --incremental-strategy append \
               --incremental-key updated_at \
               --interval-start "$(START)" \
               --interval-end "$(END)" \
               --yes

ingest:
	ingestr ingest $(INGEST_FLAGS)

ingest-debug:
	ingestr ingest $(INGEST_FLAGS) --debug --progress log

test-100:
	ingestr ingest $(INGEST_FLAGS) --sql-limit 100
```

## 14. 用 plan_ingest.py 模板化

```python
import json
from plan_ingest import from_json, Plan

plan = from_json({
    "source_uri": "postgres://...",
    "source_table": "users",
    "dest_uri": "bigquery://...",
    "dest_table": "users",
    "primary_key": ["id"],
    "strategy": "merge",
    "incremental_key": "updated_at",
})

# 打印命令
print(plan.to_shell())

# 校验
errs = plan.validate()
if errs:
    raise ValueError(errs)
```

## 15. 跨平台环境变量

```bash
# .envrc（用 direnv）
export INGESTR_SOURCE_URI="postgres://u:p@host/db"
export INGESTR_DEST_URI="bigquery://proj?credentials_path=/sa.json"
export INGESTR_INCREMENTAL_STRATEGY="merge"
export INGESTR_INCREMENTAL_KEY="updated_at"
export INGESTR_PRIMARY_KEY="id"

# 跑
ingestr ingest   # 不带 flag，全从环境变量读
```

## 16. 加新 source（开发模式）

```bash
# 1. 写代码 pkg/source/your_source/{your_source.go, register.go, mapper.go}
# 2. 在 register.go 加 init() 注册
# 3. make build
# 4. 跑
ingestr ingest --source-uri "yourscheme://..." --dest-uri "..." --yes
```

源码参考 `pkg/source/csv/source.go`（最简单）+ `pkg/source/postgres/`（复杂示例）。

## 17. 集成测试模式

```bash
# 1. 试跑
ingestr ingest ... --sql-limit 100 --yes

# 2. 对比
python3 -c "
src_count = ...
dest_count = ...
assert src_count == dest_count
"

# 3. 正式跑
ingestr ingest ... --yes
```
