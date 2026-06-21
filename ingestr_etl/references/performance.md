# 性能调优

> ingestr 默认参数对中小表够用。大表（亿级）才需要调优。

## 1. 关键 flag

| Flag | 默认 | 何时调 |
|------|------|--------|
| `--extract-parallelism` | 4 | 源端 IO 受限，调高（8-16）|
| `--page-size` | 取决于 source | 调高（5000-50000）减少 round-trip |
| `--loader-file-size` | 取决于 dest | BigQuery 走 Storage Write API 时调大 |
| `--loader-file-format` | 取决于 dest | 通常 parquet 比 csv 快 |
| `--progress` | interactive | CI/agent 改 `log` |
| `--debug` | false | 排查时开 |

## 2. 调优方向

**瓶颈可能在哪**：

```
[Source] ──读──→ [Arrow] ──传──→ [Dest Write]
   ↑                ↑                ↑
源端 IO         网络/内存        目标端吞吐
```

### 源端：拉得快

- **Postgres**：调高 `--page-size`（默认 1000，可调到 10000+）
- **ADBC 数据库**（BigQuery/Snowflake/DuckDB）：调高 `--page-size`
- **SaaS API**（Stripe/HubSpot）：有内置分页，增大 `--page-size` 让单次拉更多
- **多表并行**：用 `--extract-parallelism` 调高

```bash
# PG → BigQuery 大表
ingestr ingest \
  --source-uri "postgres://..." \
  --source-table "events" \
  --dest-uri "bigquery://..." \
  --dest-table "events" \
  --page-size 10000 \
  --extract-parallelism 8 \
  --yes
```

### 传输：内存稳

Arrow RecordBatch 是流式的，正常不会爆内存。

**危险信号**：

- 源端没有分页（一次性返回全表）→ 加 `--sql-limit` 验证，必要时用 `query:` 加 LIMIT
- 目标端 WAL 暴增（merge/delete+insert）→ 调小 batch（间接）
- staging 表过大 → 用 `merge` 替代 `delete+insert`（按 PK 删/插而非按时间）

### 目标端：写得快

- **BigQuery**：用 Storage Write API（默认走），调 `--loader-file-size` 增大文件
- **Snowflake**：用 internal stage，调 `--loader-file-size`
- **Postgres/MySQL**：调 `--extract-parallelism` 间接影响（`WriteParallel`）
- **DuckDB**：本地文件型，速度极快，瓶颈在源

```bash
# BigQuery 大表
--loader-file-size 50000000   # 50MB 一个文件
--loader-file-format parquet
```

## 3. 实际测量

**开 debug 看瓶颈**：

```bash
ingestr ingest ... --debug --progress log --yes 2>&1 | tee /tmp/ingestr.log
# 看每个 batch 的耗时
```

**关键日志**：

- `[STRATEGY] ...` — 策略相关时间
- `[SOURCE] batch read in Xms` — 源端耗时
- `[DEST] batch written in Yms` — 目标耗时
- `[DEST] total rows: N` — 进度

## 4. 大表分片（backfill / 节省内存）

按时间分片跑：

```bash
# 1月份
ingestr ingest ... --incremental-key event_time \
  --interval-start "2026-01-01T00:00:00Z" \
  --interval-end "2026-02-01T00:00:00Z" --yes

# 2月份
ingestr ingest ... --incremental-key event_time \
  --interval-start "2026-02-01T00:00:00Z" \
  --interval-end "2026-03-01T00:00:00Z" --yes
```

**适用**：

- 源表没 incremental-key 又不能改 SQL
- 内存不够一次性读
- 想分批跑（每批 1 亿行，1 月跑 1 批）

## 5. 并行 vs 串行

| 模式 | 适用 |
|------|------|
| 单 ingest 命令 | 一个源表到一个目标表（默认）|
| `--extract-parallelism N` | 单命令内并行读 N 个批次 |
| 多进程 shell 并行 | 不同源表 / 不同目标表，用 `&` 并行跑 |
| Airflow/Dagster 并行 | 生产环境，跨节点 |

**`xargs -P` 模式**：

```bash
echo "users orders products" | xargs -n1 -P3 -I{} \
  ingestr ingest --source-table {} --dest-table {} ... --yes
# 3 张表并行跑
```

## 6. 进度模式

| 模式 | 何时用 |
|------|--------|
| `interactive` (默认) | 人工跑（漂亮进度条）|
| `log` | CI / agent（行式日志，可重定向）|

```bash
# CI 必备
ingestr ingest ... --progress log --yes
```

## 7. 实战调优表

| 表大小 | 推荐参数 |
|--------|---------|
| < 100 万行 | 默认就够 |
| 100 万 - 1 亿 | `--page-size 10000 --extract-parallelism 4` |
| 1 亿 - 10 亿 | `--page-size 50000 --extract-parallelism 8` + 考虑分片 |
| > 10 亿 | 必须分片 + 加 dbt 做下游聚合 |

## 8. 何时不用调

- 数据量小（< 100 万行）→ 默认就够
- 跑得慢但不是 IO 瓶颈（CPU 100%）→ 换更强机器
- 源端限流（API 限速）→ 加 sleep 而不是提并发

## 9. 监控

**实时看进度**：

```bash
ingestr ingest ... --progress log --yes 2>&1 | grep -E "batch|rows"
```

**`--debug` 输出示例**（简化）：

```
[15:04:05.123] [STRATEGY] Using staging table: ingestr_staging_merge_orders_2026
[15:04:05.234] [SOURCE] Connected to postgres
[15:04:05.345] [SOURCE] Schema: 5 columns, PK=[id]
[15:04:05.456] [DEST] Connected to bigquery
[15:04:05.567] [DEST] Staging table created
[15:04:06.123] [SOURCE] Read batch: 10000 rows in 234ms
[15:04:06.345] [DEST] Wrote batch: 10000 rows in 178ms
...
[15:05:30.123] [DEST] Total: 1000000 rows in 85s (12k rows/s)
```

## 10. 调优检查清单

- [ ] 加 `--progress log`（不卡 CI）
- [ ] 大表加 `--page-size 10000+`
- [ ] IO 瓶颈时加 `--extract-parallelism`
- [ ] BigQuery 走 Storage Write API，调 `--loader-file-size`
- [ ] 超大表用 `--interval-start/end` 分片
- [ ] 跑完用 `--debug` 输出估算下次耗时
