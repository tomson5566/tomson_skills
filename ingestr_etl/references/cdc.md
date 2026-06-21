# CDC（变更数据捕获）

> **CDC = Change Data Capture**：源表变了，目标表跟着变，只拉变更（不是全表）。
> ingestr 的 CDC 是**微批**而非实时流（毫秒级延迟用 Kafka/Flink）。

## 1. CDC 怎么工作（理论）

ingestr 的 CDC 走数据库的 logical replication 机制：

**Postgres**：

1. 在源库创建 logical replication slot（`pgoutput` 插件）
2. 源表 PUBLICATION（要 CDC 的表）
3. ingestr 订阅 slot，读 WAL 变更
4. 变更写到目标表（delete/insert/update）
5. 记录 LSN，下次从 LSN 继续（断点续传）

**其他数据库**：ingestr 也在加 Snowflake CDC、Biquery CDC 等（看版本更新）。

## 2. 前置条件（Postgres CDC）

源端要准备好：

```sql
-- 1. 改 postgresql.conf
wal_level = logical
max_replication_slots = 4
max_wal_senders = 4

-- 2. 重启 PG
-- 3. 创建 publication
CREATE PUBLICATION ingestr_pub FOR TABLE users, orders;
```

**不需要**：源端建 replication slot（ingestr 自动建，dest-aware 后缀避免冲突）。

## 3. 用法

```bash
ingestr ingest \
  --source-uri "postgres://u:p@host:5432/db" \
  --source-table "users" \
  --dest-uri "bigquery://proj?credentials_path=/path/sa.json" \
  --dest-table "users_cdc" \
  --yes
```

ingestr 会自动检测这是 CDC 源（看 source 是否支持），派生 dest-aware slot 名（避免同一源对多个目标时 slot 冲突），从目标表推断 resume LSN。

## 4. CDC 模式 vs 增量模式

| 模式 | 检测粒度 | 延迟 | 资源消耗 | 适用 |
|------|---------|------|---------|------|
| `append` (with incremental-key) | 按 `updated_at` 拉 | 取决于跑频率 | 取决于增量量 | 大多数场景 |
| `delete+insert` (with incremental-key) | 按 `updated_at` 删+插 | 同上 | 同上 | 目标表能丢"源不存在的行" |
| CDC | 真正的 row-level 变更 | 秒级（连续跑）/ 实时（长跑）| 持续 WAL 读取 | 实时性要求高 |

**何时用 CDC**：

- 需要秒级延迟
- 不能用 `updated_at`（没这列 / 列不准）
- 表有 DELETE 事件，普通增量会漏

**何时不用 CDC**：

- 延迟分钟级够用 → 用 `append` + 频繁跑
- 表太大 / WAL 太长 → 用 `append` + incremental-key
- 不想配 logical replication → 用 `append`

## 5. 源端 slot 管理

ingestr 自动建 slot（带 dest-aware 后缀）。**slot 不释放会一直占 WAL**：

```sql
-- 查 slot
SELECT slot_name, active, restart_lsn FROM pg_replication_slots;

-- 手动删（如果 ingestr 没自动清理）
SELECT pg_drop_replication_slot('ingestr_<dest_suffix>');
```

## 6. CDC 第一次跑

**snapshot 阶段**（首次跑）：

- ingestr 触发全表 snapshot
- 之后切到 streaming

**resume LSN 自动推断**：

- 目标表有 ingestr 元列（`_ingestr_*`）→ 读 LSN
- 目标表没有 → 强制全量

## 7. 多目标 CDC

同一源对多个目标时，ingestr 自动派生不同 slot 后缀：

```
目标 A: ingestr_<hash_A>
目标 B: ingestr_<hash_B>
```

不会冲突。`pipeline.isCDCSource` 计算 suffix。

## 8. CDC 失败恢复

ingestr 自己重试有限（不内置）。**生产环境强烈建议**：

```python
# Airflow 示例
@task(retries=3, retry_delay=timedelta(minutes=1))
def ingest_cdc():
    subprocess.run([
        "ingestr", "ingest",
        "--source-uri", SRC_URI,
        "--source-table", "users",
        "--dest-uri", DEST_URI,
        "--dest-table", "users_cdc",
        "--yes",
    ], check=True)
```

## 9. CDC 检查清单

- [ ] 源端 `wal_level = logical`
- [ ] 已建 PUBLICATION
- [ ] 测试 slot 自动创建成功
- [ ] 监控 `pg_replication_slots`（不要让 inactive slot 堆 WAL）
- [ ] 跑频率 vs 延迟要求（CDC 是连续跑，比 `append` 频繁）

## 10. 不支持的场景

- ❌ MySQL CDC（ingestr 当前版本可能未支持，看 `--help` 和 release notes）
- ❌ SQL Server CDC
- ❌ Oracle CDC

需要的话用 Debezium + Kafka 转一道。

## 11. 监控指标

```sql
-- PG 端
SELECT slot_name, active, restart_lsn, confirmed_flush_lsn
FROM pg_replication_slots;

-- 看 WAL 堆积
SELECT pg_wal_lsn_diff(pg_current_wal_lsn(), restart_lsn) AS lag_bytes
FROM pg_replication_slots;
```

## 12. 进一步阅读

- 源码：`pkg/pipeline/pipeline.go::isCDCSource`
- 源码：`pkg/source/postgres/` 的 CDC 相关
- 官方：https://bruin-data.github.io/ingestr/getting-started/cdc.html（看实际版本是否更新）
