# 最佳实践

> ingestr 用多了之后沉淀下来的"什么时候该/不该"清单。

## 1. 起步

### ✅ 默认参数先跑

- 默认 `replace` 策略最简单
- 默认 `--progress interactive` 最直观
- 默认 `evolve` schema 契约最灵活

跑通了再调优。

### ✅ 第一次跑用 `--sql-limit 100`

```bash
ingestr ingest ... --sql-limit 100 --yes
```

验证：连通性、schema 推断、类型映射。跑通再去掉。

### ✅ 用 `query:` 自定义 SQL 选行/列

不一定要拉整张表。

## 2. 策略选择

### ✅ 默认 `replace`，有需要再换

```bash
# 第一次 / 一次性
ingestr ingest ... --yes  # 默认 replace

# 之后增量（必须配 interval）
ingestr ingest ... --incremental-strategy append --incremental-key updated_at \
  --interval-start "$START" --interval-end "$END" --yes
```

### ✅ 表有自然 PK → `merge`

```bash
ingestr ingest ... --strategy merge --primary-key id --incremental-key updated_at \
  --interval-start "$START" --interval-end "$END" --yes
```

### ✅ 事件流（无 PK）→ `append`

```bash
ingestr ingest ... --strategy append --incremental-key event_time \
  --interval-start "$START" --interval-end "$END" --yes
```

### ❌ 大表不要用 `replace`

- 慢
- 数据真空期
- 目标表短时间不可读

### ❌ `merge` 会 UPDATE，小心 warehouse 费用

BigQuery / Snowflake 的 UPDATE 比 INSERT 贵得多。

### ❌ `delete+insert` 会**删目标里源不存在的行**

确认业务能接受再用。

## 3. Schema

### ✅ 生产用 `--schema-contract freeze`

```bash
ingestr ingest ... --schema-contract freeze --yes
```

任何漂移直接失败，逼你主动决定。

### ✅ MongoDB / JSON 用 `--columns --no-inference`

推断的 schema 不准时显式指定。

### ✅ 跨老 ingestr 加 `--schema-naming snake_case`

```bash
ingestr ingest ... --schema-naming snake_case --yes
```

### ❌ 别在生产用 `evolve` + `auto`

`evolve` 默默改 DDL，`auto` 默默改命名。生产不可控。

## 4. 性能

### ✅ 自动化时加 `--yes` + `--progress log`

```bash
ingestr ingest ... --yes --progress log
```

`--yes` 跳过交互确认，`--progress log` 用行式日志。

### ✅ 大表调 `--page-size`

```bash
ingestr ingest ... --page-size 10000 --yes
```

默认 1000，调到 10000+ 减少 round-trip。

### ✅ 超大表用 `--interval-start/end` 分片

```bash
ingestr ingest ... --interval-start "2026-01-01" --interval-end "2026-02-01" --yes
```

内存友好、监控友好。

### ❌ 别用 `replace` 跑超 1 亿行

用 `truncate+insert` 或 `append`。

### ❌ 别无脑加 `--extract-parallelism`

源端 API 有限流（Stripe 100 req/s），并发高反而被 ban。

## 5. 安全

### ✅ PII 字段加 `--mask`

```bash
ingestr ingest ... \
  --mask "email:hash" \
  --mask "ssn:partial:4" \
  --mask "salary:round:1000" \
  --yes
```

### ✅ 凭证走环境变量，不在命令行

```bash
# 好
export INGESTR_SOURCE_URI="postgres://..."
ingestr ingest

# 不好（会留在 shell history）
ingestr ingest --source-uri "postgres://u:p@host/db" ...
```

### ✅ `creds.json` 加 `.gitignore`

### ❌ 别把 `creds.json` 提交到 git

### ❌ 别在公网暴露 `ingestr server`

默认监听 0.0.0.0，没认证。

## 6. 错误处理

### ✅ 用 `--debug` 排查

```bash
ingestr ingest ... --debug --progress log --yes 2>&1 | tee /tmp/ingestr.log
```

### ✅ 失败时看 `PrintFailedQuery` 输出

main.go 里 ingest 失败会打印最近 SQL。

### ✅ `merge`/`delete+insert` 时用 `--keep-staging`

```bash
ingestr ingest ... --keep-staging --yes
# 跑完看 staging 表内容
```

### ✅ 外层调度器做重试

ingestr 本身不重试。Airflow / Dagster 调它，加 `retries=3`。

## 7. 监控

### ✅ 看 ingestr 的时间戳日志

```
[15:04:05.123] [STRATEGY] ...
[15:04:05.234] [SOURCE] ...
[15:04:05.345] [DEST] ...
```

### ✅ 用 progress 模式统计行数

```bash
ingestr ingest ... --progress log --yes 2>&1 | grep -E "Total|rows"
```

### ✅ 长时间跑用 `nohup` + log

```bash
nohup ingestr ingest ... --progress log --yes > /var/log/ingestr.log 2>&1 &
```

## 8. 迁移

### ✅ 从 replace 升级到 merge 的步骤

```bash
# 1. 第一次：用 --full-refresh 强制重建（带 PK）
ingestr ingest ... --strategy merge --primary-key id --full-refresh --yes

# 2. 之后：常规 merge
ingestr ingest ... --strategy merge --primary-key id --incremental-key updated_at --yes
```

### ✅ 改了 `--schema-naming` 要 `--full-refresh`

命名约定变了，老的表列名不对应。

### ✅ 改主键要 `--full-refresh`

```bash
ingestr ingest ... --strategy merge --primary-key new_id --full-refresh --yes
```

## 9. 集成

### ✅ 跟 dbt 配合

ingestr 喂原始数据（`raw` schema），dbt 做建模（`marts` schema）：

```bash
# ingestr 跑
ingestr ingest --source-uri stripe://... --source-table charges --dest-uri bigquery://... --dest-table raw.charges --yes

# dbt 跑
cd dbt_project && dbt run --select charges
```

### ✅ 跟 Airflow 配合

ingestr 在 Airflow task 里，retries=3。

### ✅ 跟 Bruin 配合

ingestr 是 Bruin 的 ETL 引擎。Bruin 加调度/lineage/UI。

## 10. 反模式

### ❌ 用 ingestr 做 SQL 转换

ingestr 不做 `SELECT a + b AS c`。用 dbt。

### ❌ 用 ingestr 做调度

ingestr 不内置调度。用 Airflow/Dagster。

### ❌ 用 ingestr 做实时流

ingestr 是批/微批。要毫秒级用 Kafka/Flink。

### ❌ 用 ingestr 做 lineage

ingestr 不知道"这表从哪来"。用 Bruin/DataHub。

### ❌ 把 ingestr 当数据库迁移工具

ingestr 适合"定期同步"，不是"一次性 schema 迁移"。

## 11. 总结清单

| 阶段 | 必做 |
|------|------|
| 第一次跑 | `--sql-limit 100 --yes` |
| 验证后正式跑 | 去掉 `--sql-limit`，加 `--progress log` |
| 生产 cron / Airflow | `--yes --progress log` |
| PII 同步 | 加 `--mask` |
| MongoDB / JSON | `--columns --no-inference` |
| 大表（亿级） | `--page-size 10000` + 分片 |
| 改主键 / 命名 | `--full-refresh` |
| 严格 schema 契约 | `--schema-contract freeze` |
| 失败排查 | `--debug --progress log` |
| merge / delete+insert 排查 | `--keep-staging` |
| 安全 | 凭证走环境变量、creds.json 不入 git |
