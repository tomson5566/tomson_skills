# Schema 管理

> ingestr 在 4 个维度上管理 schema：**契约**（漂移时怎么办）、**命名**（列名怎么写）、**演进**（DDL 怎么应用）、**推断**（schema-less 源怎么定 schema）。

## 1. Schema 契约（`--schema-contract`）

源表 schema 跟目标表对不上时怎么办？

| 模式 | 行为 | 适用 |
|------|------|------|
| `evolve` (默认) | 自动演进：加列、改类型都接受 | 灵活 / schema 在变 |
| `freeze` | 拒绝任何漂移，抛错停 | 严格数据契约 |
| `discard_row` | 漂移字段所在行整行丢弃 | 宁可丢数据也不污染 |
| `discard_value` | 漂移字段填 NULL，行保留 | 保行不保字段 |

**判断"漂移"**：

- 新增列（源有，目标没有）→ 演进
- 删除列（源没有，目标有）→ 演进（目标表 DROP COLUMN）
- 类型变化（int → bigint）→ 演进（CAST）
- 类型不兼容（string → int）→ **漂移**，按契约处理

```bash
# 严格模式：任何漂移直接失败
ingestr ingest ... --schema-contract freeze --yes

# 保守：丢行
ingestr ingest ... --schema-contract discard_row --yes

# 保守：保行丢字段
ingestr ingest ... --schema-contract discard_value --yes
```

**理论**：`pkg/schemaevolution/` 的 `SchemaComparison` + `EvolutionPlan`。

## 2. Schema 命名（`--schema-naming`）

新表/新列的命名方式：

| 模式 | 行为 |
|------|------|
| `direct` (默认) | 保留原列名（`firstName` 留 `firstName`）|
| `snake_case` | 强制 snake_case（`firstName` → `first_name`，兼容老 ingestr Python 版）|
| `auto` | 目标表已存在则继承；否则用 `direct` |

```bash
ingestr ingest ... --schema-naming snake_case --yes
```

**适用场景**：

- 新建表：默认 `direct` 就好
- 跟老的 ingestr Python 版数据对齐：用 `snake_case`
- 跨工具迁移（dbt 期望 snake_case）：用 `snake_case`

**理论**：`pkg/naming/` + `pkg/transformer/ColumnRenamer`。

## 3. Schema 演进（DDL 自动应用）

**演进 ≠ 契约**。演进是"怎么改"，契约是"改不改"。

流程（`pkg/pipeline/pipeline.go`）：

```
1. 读 source schema
2. 如果目标表存在，读 destination schema
3. 比对生成 SchemaComparison
4. 生成 EvolutionPlan（DDL 列表）
5. 根据 --schema-contract 决定怎么处理
6. 在 strategy.Execute 里应用 EvolutionPlan
```

**自动演进的 DDL 类型**：

- `ADD COLUMN`（新列）
- `DROP COLUMN`（源删了的列）
- `ALTER COLUMN ... TYPE`（类型变宽）
- `ALTER COLUMN ... SET NOT NULL` / `DROP NOT NULL`

**不**自动处理（需要手工）：

- 重命名（ingestr 不知道是"重命名"还是"删+加"）
- 主键变化
- 索引变化

## 4. Schema 推断（schema-less 源）

MongoDB、JSON、Avro 等没有固定 schema 的源：

**ingestr 怎么推断**（`pkg/schemainfer/`）：

1. 读第一批 RecordBatch（默认一批 1000 行）
2. 把所有行的列 union 起来
3. 每列取最宽类型（int + bigint → bigint，string + null → string）
4. 推断列是否 nullable（任何行有 null → nullable）

**手动指定列**（推断不准时）：

```bash
ingestr ingest \
  --source-uri "mongodb://u:p@host:27017/db" \
  --source-table "events" \
  --dest-uri "bigquery://..." \
  --dest-table "events" \
  --columns "id:string,event_type:string,timestamp:timestamp,payload:json" \
  --no-inference \
  --yes
```

支持的类型关键字：`string`, `boolean`, `int16`, `int32`, `int64`, `float32`, `float64`, `decimal`, `date`, `time`, `timestamp`, `interval`, `json`, `uuid`, `binary`, `array`。

**何时不用推断**：

- 已知 schema 不变（强制指定更快）
- 推断结果不对（union 推断遇到混合类型时）
- 字段太多（推断慢）

## 5. Schema 相关的 4 个 flag 组合

| 需求 | flag 组合 |
|------|----------|
| 信任源 schema，列名直接用 | （无，evolve + direct 是默认）|
| 源 schema 不稳，要拒绝 | `--schema-contract freeze` |
| 源 schema 不稳，但能丢字段 | `--schema-contract discard_value` |
| 跨老 ingestr 兼容 | `--schema-naming snake_case` |
| MongoDB 不知道字段类型 | `--columns "..." --no-inference` |
| 强制重新建表（不演进）| `--full-refresh` |

## 6. Schema 演进的实战模式

**首次跑**（默认 `evolve`，通常没事）：

```bash
ingestr ingest ... --yes
# 自动建表 + 应用任何 DDL
```

**第二次跑**（源表加了一列）：

```bash
ingestr ingest ... --yes
# 自动 ADD COLUMN
```

**源表删了一列**（默认会 DROP COLUMN）：

```bash
# 如果想保留目标表这列：
ingestr ingest ... --schema-contract freeze --yes
# 报错 → 你知道有事 → 决定手动改

# 如果想丢弃：
ingestr ingest ... --yes
# 自动 DROP COLUMN
```

**源表改了主键**（罕见）：

```bash
ingestr ingest ... --full-refresh --yes
# 全量重置，强制重建
```

## 7. Schema 元列（ingestr 自动加）

ingestr 默认会加这些元列（`pkg/schemaevolution/ingestr_column_filler.go`）：

| 列 | 类型 | 含义 |
|----|------|------|
| `_ingestr_extracted_at` | timestamp | ingestr 提取时间 |
| `_ingestr_ingested_at` | timestamp | ingestr 写入时间 |
| `_ingestr_source_uri` | string | 源 URI |
| `_ingestr_source_table` | string | 源表名 |

如果不需要：

```bash
ingestr ingest ... --no-ingestr-columns --yes
```

## 8. 实战检查清单

- [ ] 首次跑前想好：源 schema 是稳还是变？
- [ ] 变 → `freeze` 还是 `discard_*`，避免 ingestr 默默改 DDL
- [ ] 不变 → 默认 `evolve`，但 `freeze` 更安全
- [ ] 跨老 ingestr → 加 `--schema-naming snake_case`
- [ ] MongoDB / JSON → 准备手动 `--columns`
- [ ] 看到 `_ingestr_*` 列 → 知道是 ingestr 加的元数据
