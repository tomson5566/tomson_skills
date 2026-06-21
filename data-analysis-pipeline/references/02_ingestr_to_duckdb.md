# ingestr → DuckDB 实战

> 详细 ingestr 文档查 `ingestr_etl` skill。本 reference 只讲"如何把数据落到 DuckDB"。

## 1. 装包

```bash
# ingestr 本身(Go 二进制 + Python 包装)
uv tool install ingestr
# 或
pipx install ingestr

# DuckDB
uv add duckdb
```

验证:
```bash
ingestr --version
python -c "import duckdb; print(duckdb.__version__)"
```

## 2. URI 模板(DuckDB 当目标)

```bash
duckdb:///<path>.duckdb          # 文件型(默认)
duckdb:///:memory:              # 内存型(测试用)
duckdb:///<path>.duckdb#<table>  # 显式指定目标表
```

**路径约定**:
- 相对路径:相对当前 cwd,跟 `.env` 配置一致
- 绝对路径:`/opt/data/analytics.duckdb` — 推荐生产用
- 共享存储:`/mnt/shared/team.duckdb` — 多机用同一个 DB

## 3. 5 大常见源 → DuckDB

### 3.1 CSV 文件(最常见)

```bash
# 单文件
ingestr ingest \
  --source-uri "csv://./data/orders.csv" \
  --dest-uri "duckdb:///./analytics.duckdb#orders"

# 多文件(glob 模式)
ingestr ingest \
  --source-uri "csv://./data/orders_*.csv" \
  --dest-uri "duckdb:///./analytics.duckdb#orders"

# 带分隔符
ingestr ingest \
  --source-uri "csv://./data/orders.tsv?sep=\t" \
  --dest-uri "duckdb:///./analytics.duckdb#orders"
```

**增量**:
```bash
ingestr ingest \
  --source-uri "csv://./daily/*.csv" \
  --dest-uri "duckdb:///./analytics.duckdb#orders" \
  --incremental-key=order_date
```

### 3.2 Parquet(列式,大数据推荐)

```bash
ingestr ingest \
  --source-uri "parquet://./data/orders.parquet" \
  --dest-uri "duckdb:///./analytics.duckdb#orders"

# 多文件
ingestr ingest \
  --source-uri "parquet://./data/year=*/month=*/*.parquet" \
  --dest-uri "duckdb:///./analytics.duckdb#orders"
```

**为啥 Parquet 优于 CSV**:列式压缩(~10x 小)、自带 schema、读列比读整行快。

### 3.3 Postgres / MySQL / MSSQL

```bash
# 全表
ingestr ingest \
  --source-uri "postgres://user:pass@host:5432/dbname" \
  --source-table "public.orders" \
  --dest-uri "duckdb:///./analytics.duckdb#orders"

# 自定义 SQL
ingestr ingest \
  --source-uri "postgres://user:pass@host:5432/dbname" \
  --source-query "SELECT * FROM orders WHERE created_at > '2026-01-01'" \
  --dest-uri "duckdb:///./analytics.duckdb#orders_recent"
```

**增量**(基于时间戳):
```bash
ingestr ingest \
  --source-uri "postgres://user:pass@host/dbname" \
  --source-table "public.orders" \
  --dest-uri "duckdb:///./analytics.duckdb#orders" \
  --incremental-key=updated_at \
  --strategy=merge
```

### 3.4 SaaS API(Stripe / HubSpot / Notion / Salesforce)

```bash
# Notion database
ingestr ingest \
  --source-uri "notion://?token=secret_xxx" \
  --source-table "abc123-database-id" \
  --dest-uri "duckdb:///./analytics.duckdb#notion_tasks"

# Stripe
ingestr ingest \
  --source-uri "stripe://?api_key=sk_xxx" \
  --source-table "charges" \
  --dest-uri "duckdb:///./analytics.duckdb#stripe_charges"

# HubSpot
ingestr ingest \
  --source-uri "hubspot://?access_token=xxx" \
  --source-table "contacts" \
  --dest-uri "duckdb:///./analytics.duckdb#hubspot_contacts"
```

**完整 URI 清单**:`ingestr_etl` skill 的 `references/uri_catalog.md`(70+ 源)

### 3.5 对象存储(S3 / GCS / ADLS)

```bash
# S3
ingestr ingest \
  --source-uri "s3://my-bucket/data/*.parquet?region=us-east-1" \
  --dest-uri "duckdb:///./analytics.duckdb#s3_data"

# 带凭证
ingestr ingest \
  --source-uri "s3://my-bucket/data/?aws_access_key_id=xxx&aws_secret_access_key=yyy" \
  --dest-uri "duckdb:///./analytics.duckdb#s3_data"
```

## 4. 6 种增量策略(给老数据二次取用)

| 策略 | 行为 | 用在 |
|---|---|---|
| `replace`(默认) | 全量删了重写 | 第一次跑 / 数据小 |
| `append` | 永远加,不删旧的 | 时序数据(无唯一键) |
| `merge` | 按主键 upsert | 业务表(订单/用户) |
| `delete+insert` | 按 incremental-key 窗口删后插 | 时序 + 修正可能 |
| `truncate+insert` | 截断后插 | 全量更新型(可重建) |
| `scd2` | 缓慢变化维度(保留历史) | 维度表(用户画像演化) |
| `none` | 啥也不做,源表不动 | 调试 |

**实战**:
```bash
# 订单表(主键 id,时间字段 updated_at)
ingestr ingest \
  --source-uri "postgres://..." --source-table orders \
  --dest-uri "duckdb:///./analytics.duckdb#orders" \
  --incremental-key=updated_at \
  --strategy=merge \
  --primary-key=id
```

## 5. 多个源到一个 DuckDB(经典 ETL 模式)

```bash
#!/bin/bash
set -e
DB="duckdb:///./analytics.duckdb"

# 1. 用户(来自 MySQL)
ingestr ingest --source-uri "mysql://..." --source-table users \
  --dest-uri "$DB#users"

# 2. 订单(来自 Postgres)
ingestr ingest --source-uri "postgres://..." --source-table orders \
  --dest-uri "$DB#orders"

# 3. 行为日志(来自 S3 Parquet)
ingestr ingest --source-uri "s3://logs/2026/*.parquet" \
  --dest-uri "$DB#events"

# 4. Stripe 支付
ingestr ingest --source-uri "stripe://?api_key=sk_xxx" --source-table charges \
  --dest-uri "$DB#charges"

# 5. 一次性小表(Notion 维护的配置)
ingestr ingest --source-uri "notion://?token=..." --source-table config_db_id \
  --dest-uri "$DB#config"

echo "Done. Now query:"
echo "  python -c \"import duckdb; print(duckdb.sql('SHOW TABLES').df())\""
```

**核心思想**:DB 放一个地方(`./analytics.duckdb`),多个源灌进不同表,**SQL 层统一 JOIN**。

## 6. 实战踩坑

### 坑 1: DuckDB 文件被占用

**症状**:`IO Error: Could not set lock on file`

**原因**:DuckDB 文件同时只能被 1 个进程写。读可以并发。

**修法**:
- 写 → 跑完立即关
- 读 → 多进程可并发,但别跟写同时

### 坑 2: 时区错乱

**症状**:timestamp 差了 8 小时

**修法**:DuckDB 0.10+ 加 `--source-timezone=UTC` 或在 SQL 里 `AT TIME ZONE 'Asia/Shanghai'`。

### 坑 3: CSV 编码

**症状**:`utf-8` 解码失败

**修法**:
```bash
ingestr ingest \
  --source-uri "csv://./data/orders.csv?encoding=gbk" \
  --dest-uri "duckdb:///..."
```

### 坑 4: 大表内存爆

**症状**:10GB CSV 灌 32GB 内存机炸了

**修法**:
- ingestr 默认流式读,理论不会爆
- 确认 DuckDB 写盘模式:`SET memory_limit='8GB'`
- 或先转 Parquet(列式压缩好)

### 坑 5: 自增主键

**症状**:CSV 没主键,merge 时 upsert 失败

**修法**:
```bash
ingestr ingest \
  --source-uri "csv://./data/orders.csv" \
  --dest-uri "duckdb:///./...#orders" \
  --primary-key=order_id \
  --incremental-key=updated_at
```

## 7. 验证数据落库

```bash
# 行数
ingestr inspect --table orders --source-uri "duckdb:///./analytics.duckdb"

# 或直接 DuckDB
python -c "
import duckdb
print(duckdb.sql(\"SELECT count(*) FROM 'analytics.duckdb'.orders\").df())
print(duckdb.sql(\"DESCRIBE 'analytics.duckdb'.orders\").df())
print(duckdb.sql(\"SELECT * FROM 'analytics.duckdb'.orders LIMIT 5\").df())
"
```

## 8. 调度(简单版:cron + bash)

```bash
# /etc/cron.d/etl-daily
0 2 * * *  deploy  bash /opt/etl/daily.sh >> /var/log/etl.log 2>&1
```

`daily.sh`:
```bash
#!/bin/bash
set -e
cd /opt/etl
ingestr ingest --source-uri "postgres://..." --source-table orders \
  --dest-uri "duckdb:///./analytics.duckdb#orders" \
  --incremental-key=updated_at --strategy=merge --primary-key=id
ingestr ingest --source-uri "s3://..." \
  --dest-uri "duckdb:///./analytics.duckdb#events" \
  --incremental-key=event_time --strategy=append
```

**企业级调度**(DAG / 依赖):用 Airflow / Dagster / Prefect 调 ingestr。`ingestr_etl` skill 的 `cdc.md` 讲了 CDC 增量模式。

## 9. 跟 DuckDB 直读的边界

| 场景 | 用 ingestr | 用 DuckDB 直读 |
|---|---|---|
| 单 CSV 一次性分析 | ❌ overhead | ✅ `duckdb.read_csv()` |
| 单 Parquet 摸底 | ❌ | ✅ `duckdb.read_parquet()` |
| 5+ 源灌同 DB | ✅ | ❌ |
| 增量 + 调度 | ✅(内置) | ❌(自己写) |
| SaaS API | ✅(唯一选项) | ❌ |
| 跨数据库 JOIN | 中间步骤 | ✅ DuckDB `ATTACH` |