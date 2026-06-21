# ingestr 策略选择指南

> ingestr v1.0.21 内置 7 个策略：`replace`, `truncate+insert`, `append`, `delete+insert`, `merge`, `scd2`, `none`
> 通过 `--incremental-strategy` 切换，默认 `replace`。

## 决策树

```
你的目标表需要保留历史变更吗？
├── 不需要，要的是"最新快照"
│   └── 想频繁跑（每次全量）？
│       ├── 数据不大（< 1 亿行）→ replace（默认，最简单最对）
│       └── 数据大，但只要清空再写 → truncate+insert（比 replace 快，省 DDL）
│
└── 需要保留历史
    ├── 表有"业务主键"（user_id, order_id）
    │   ├── 想保留所有版本（审计/回溯）→ append
    │   └── 只想保留最新版本 → merge
    │       └── ⚠️ merge 会更新现有行，小心 warehouse 更新费用
    │
    ├── 表有"业务主键" + "有效时间区间"
    │   └── 想做 SCD Type 2 → scd2
    │
    └── 表没有"业务主键"（日志/事件流）
        └── 按"事件时间"切片重写 → delete+insert
            └── ⚠️ delete+insert 会删掉目标表里源表不存在的行
```

## 策略细节

### replace（默认）

- **行为**：删目标表 → 重建 → 全量写
- **适用**：小到中表、需要确定性的"全量快照"
- **不适用**：大表（有数据真空期、慢）
- **需要的 flag**：无（默认）
- **风险**：⚠️ 删整表

```bash
ingestr ingest \
  --source-uri "..." --source-table "..." \
  --dest-uri "..." --dest-table "..." \
  --incremental-strategy replace \
  --yes
```

### truncate+insert

- **行为**：`TRUNCATE` 表 → 全量写（比 replace 省 DROP/CREATE DDL）
- **适用**：表结构不变、只换数据的中到大型表
- **不适用**：表结构经常变
- **需要的 flag**：无

### append

- **行为**：把源表新行追加到目标末尾（不删、不重写）
- **关键 flag**：`--incremental-key`（label）+ `--interval-start` / `--interval-end`（**必填**窗口）
- **行为细节**：
  - ingestr **不**自动从 dest 算 `max(incremental_key)`
  - 你必须显式传 interval；不传 = 全表扫描 + 全量写（很危险，会重复）
  - 第一次跑：传覆盖全数据的窗口（如 `1970-01-01` ~ `2099-01-01`）= 全量
  - 后续跑：传要拉的时间窗
  - 写时直接 `INSERT`，无 staging（也不去重）
- **适用**：事件流、审计/回溯、构建 SCD Type 2 的源数据
- **风险**：
  - ⚠️ 不去重，相同 PK 会有多行
  - ⚠️ 写时不带 staging，写失败会留下半成品
- **不适用**：需要"最新一版"视图的场景

```bash
ingestr ingest \
  --incremental-strategy append \
  --incremental-key updated_at \
  --interval-start "2026-02-01T00:00:00Z" \
  --interval-end "2026-03-01T00:00:00Z" \
  --yes
```

### merge

- **行为**：按 PK 合并，新行插入、已存在行更新
- **关键 flag**：`--primary-key`（必填）、`--incremental-key` + `--interval-start/end`（强烈推荐）
- **行为细节**：
  - 用 staging 表：`_bruin_staging.<table>_merge_<ts>`
  - 跑完 staging 表保留 24h 后清理（可 `--keep-staging` 永久）
- **适用**：需要"最新一版"视图 + 表有自然主键（user_id, order_id 等）
- **不适用**：源表无 PK、目标表无 PK
- **风险**：
  - ⚠️ merge 会 UPDATE 现有行
  - ⚠️ BigQuery / Snowflake 的 UPDATE 收费贵

```bash
ingestr ingest \
  --incremental-strategy merge \
  --incremental-key updated_at \
  --interval-start "2026-02-01T00:00:00Z" \
  --interval-end "2026-03-01T00:00:00Z" \
  --primary-key id \
  --yes
```

### delete+insert

- **行为**：
  1. 把源新行写到 staging
  2. 删目标表里 `incremental-key` 命中的行
  3. 从 staging 把新行插回目标
- **关键 flag**：`--incremental-key` + `--interval-start/end`
- **适用**：可以接受"目标里只保留源里有且在增量区间的行"、需要 backfill
- **风险**：
  - ⚠️ 目标里源表不存在的行会被删
  - ⚠️ 不保证行序
  - ⚠️ 不去重

```bash
ingestr ingest \
  --incremental-strategy delete+insert \
  --incremental-key updated_at \
  --interval-start "2026-02-01T00:00:00Z" \
  --interval-end "2026-03-01T00:00:00Z" \
  --yes
```

### scd2

- **行为**：SCD Type 2（Slowly Changing Dimension）
  - 加两列 `_scd_valid_from`, `_scd_valid_to`
  - 新版本写入，旧版本 `_scd_valid_to` 设为新版本的时间戳
- **关键 flag**：`--primary-key`（必填）、`--incremental-key` + `--interval-start/end`
- **适用**：数据仓库建模、要追溯维度变化历史
- **输出列**：除原列外，追加 `_ingestr_extracted_at`, `_scd_valid_from`, `_scd_valid_to`

### none

- **行为**：跳过 ingestion，仅做"预热"（连接验证、schema 打印）
- **适用**：dry-run / 健康检查

## 增量区间控制

按时间分区跑：

```bash
ingestr ingest \
  --source-uri "..." --source-table "events" \
  --dest-uri "..." --dest-table "events" \
  --incremental-strategy append \
  --incremental-key event_time \
  --interval-start "2026-01-01T00:00:00Z" \
  --interval-end "2026-01-02T00:00:00Z" \
  --yes
```

Pipeline 把它翻译成 `WHERE event_time >= '...' AND event_time < '...'`。

## Schema 契约（4 模式）

源表 schema 跟目标不匹配时怎么办？

| 模式 | 行为 | 适用 |
|------|------|------|
| `evolve` (默认) | 自动演进：加列、改类型都接受 | 灵活 / schema 在变 |
| `freeze` | 拒绝任何漂移，抛错停 | 严格数据契约 |
| `discard_row` | 漂移字段所在行整行丢弃 | 宁可丢数据也不污染 |
| `discard_value` | 漂移字段填 NULL，行保留 | 保行不保字段 |

```bash
--schema-contract freeze   # 严格模式
--schema-contract discard_row
```

## 命名约定（3 模式）

新表/新列的命名方式：

| 模式 | 行为 |
|------|------|
| `direct` (默认) | 保留原列名 |
| `snake_case` | 强制 snake_case（兼容老 ingestr Python 版） |
| `auto` | 根据目标表历史判断 |

```bash
--schema-naming snake_case
```

## 性能调优

| Flag | 默认 | 建议 |
|------|------|------|
| `--extract-parallelism` | 4 | 源端 IO 受限时调高（8-16） |
| `--page-size` | 取决于 source | 大表调到 10000+ 减少 round-trip |
| `--loader-file-size` | 取决于 dest | BigQuery 走 Storage Write API 时调大 |
| `--progress` | interactive | 自动化时改 `log` |

## CDC（变更数据捕获）

需要源端支持 logical replication（Postgres + wal2json / pgoutput）：

- Pipeline 派生 dest-aware slot 后缀
- Resume LSN 自动从目标表状态推断
- 用 `--full-refresh` 强制全量重置

## 选错策略的"翻车"场景

| 错选 | 后果 | 信号 |
|------|------|------|
| 大表用 replace | 慢、有数据真空期、目标表短时间不可读 | 跑超时 / 用户查不到数据 |
| 误用 merge 替代 append | 丢失历史版本、warehouse 费用暴涨 | 目标表行数不增反减 / 账单爆 |
| 误用 delete+insert | 目标表里源表不存在的行被删 | 行数减少、关键记录消失 |
| 没设 incremental-key 就跑 append | 每次都全量，append 退化成 replace | 行数爆炸 |
| 不设 primary-key 就跑 merge | 启动失败：明确报错 | "merge strategy requires at least one primary_key" |
