# ingestr 内部架构（源码理论）

> **目的**：理解 ingestr 为什么这么设计。读完这些再去看官方文档会事半功倍，因为所有 CLI flag、行为细节都是这套架构的"投影"。
>
> **来源**：`docs/ingestr-1.0.21.zip`（Go 源码，108 个 Go 文件）
>
> **方法**：先讲概念，再给"看哪行源码能验证"。

## 一、3 个核心抽象

ingestr 的整个代码库围绕 **3 个接口** 转：

| 接口 | 位置 | 职责 | 关键方法 |
|------|------|------|---------|
| `Source` | `pkg/source/source.go` | 怎么**取**数据 | `Connect`, `GetTable`, `Close` |
| `Destination` | `pkg/destination/destination.go` | 怎么**写**数据 | `Connect`, `PrepareTable`, `Write`, `MergeTable`, `SwapTable`, `Close` |
| `WriteStrategy` | `pkg/strategy/strategy.go` | 怎么**协调**取+写 | `Validate`, `Execute`, `RequiresPrimaryKey` |

数据流：

```
Source.Read()  ────→  chan RecordBatchResult (Arrow)  ────→  Destination.Write()
                              ↑
                              │
                    Strategy 协调 Prepare/Write/Swap
```

**为什么这样设计**：源和目标各自独立变化（加新数据库、新 SaaS），中间用 Arrow 通道做"零拷贝"传递。策略是胶水层。

## 二、Apache Arrow 是数据底座

**Why Arrow**（`pkg/schema/schema.go`）：

- **零拷贝**：source 读完直接给 destination，跨 Go goroutine 不复制内存
- **类型统一**：所有数据库的类型都映射到 Arrow 类型
- **生态**：BigQuery Storage Write API、Snowflake Arrow loader、DuckDB 全都吃 Arrow

**所有 source 输出 `<-chan source.RecordBatchResult`**，里面就是 `arrow.RecordBatch`。

**TypeMapping**（`pkg/source/postgres/mapper.go`, `pkg/source/bigquery/mapper.go` 等）：

每种数据库有自己的类型 → 内部 `schema.DataType` 枚举 → `arrow.DataType` 的映射。

```go
// pkg/schema/schema.go 摘录
const (
    TypeUnknown DataType = iota
    TypeBoolean
    TypeInt16
    TypeInt32
    TypeInt64
    TypeFloat32
    TypeFloat64
    TypeDecimal
    TypeString
    TypeBinary
    TypeDate
    TypeTime
    TypeTimestamp
    TypeTimestampTZ
    TypeInterval
    TypeJSON
    TypeUUID
    TypeArray
)
```

**关键时间戳约定**：所有 Arrow 时间戳用 **microsecond**。源码 `AGENTS.md` 明确说：

> BigQuery's Storage Write API expects microseconds regardless of Arrow schema unit metadata

所以 MongoDB 的 `primitive.DateTime`（毫秒）要 `* 1000` 转微秒。Postgres / BigQuery / Snowflake 内部就是微秒，零成本。

## 三、ADBC（Arrow Database Connectivity）— 为什么这么多个数据库走 ADBC

**ADBC** = Arrow 生态的标准数据库连接协议（类似 ODBC/JDBC 但原生支持 Arrow）。

**好处**：

- 一次实现，多个数据库复用
- 数据直接进 Arrow，少一层 SQL → 行 → Arrow 转换
- C++ 实现，跨语言

**ingestr 的 ADBC 抽象**（`pkg/source/adbc/dialect.go`）：

```go
type Dialect interface {
    Driver() string
    BuildSelectQuery(...) string  // SQL 模板（带 schema 嵌入 BigQuery 用）
    MapDataType(dbType string) schema.DataType
    SupportsCTE() bool
    // ...
}
```

每个数据库有自己的 Dialect（`pkg/source/bigquery/dialect.go`, `pkg/source/snowflake/dialect.go`, `pkg/source/duckdb/dialect.go`）。

**两个变体**（解决"路径里带 schema"的特殊问题）：

- `DatasetAwareDialect` — BigQuery 用（query 路径要带 dataset）
- `SchemaProvider` — 直接调 API 拿 schema（更快，比 SQL `DESCRIBE`）

**驱动自动管理**（`pkg/source/adbc/driver.go`）：

用 `github.com/columnar-tech/dbc` 客户端下载/缓存 ADBC 驱动。第一次跑某个数据库会联网下，后续从缓存读。

**为什么 Postgres/MySQL/MSSQL 不用 ADBC**：它们有成熟的 Go 原生驱动（pgx、go-sql-driver、mstools），用 ADBC 反而绕。源码里这些是**直接实现 Source**，不走 ADBC。

## 四、Registry 模式（自注册）

**没有中央 switch-case 路由**。每个 source/destination 在自己的 `register.go` 里：

```go
// pkg/source/postgres/register.go
func init() {
    registry.RegisterSource(
        []string{"postgres", "postgresql", "postgresql+psycopg2"},
        func() interface{} { return NewPostgresSource() },
    )
}
```

`init()` 在 Go 包加载时自动跑。**怎么保证所有 register.go 都被 import？** 用 `cmd/genregistry` 扫 `pkg/source/` 和 `pkg/destination/`，生成 `internal/registry/imports/imports.gen.go`，这个文件做 blank import：

```go
import (
    _ "github.com/bruin-data/ingestr/pkg/source/postgres"
    _ "github.com/bruin-data/ingestr/pkg/source/mysql"
    // ... 所有 source/destination
)
```

`uri.DefaultRegistry.GetSource(uri)` 查表 → 拿到 constructor → 调 `()` → 返回实例。

**好处**：加新 source 不改主流程，加 `register.go` + `init()` 就行。

## 五、URI 归一化（细节藏在这里）

`internal/uri/parser.go::NormalizeScheme`：

```go
aliases := map[string]string{
    "postgresql":          "postgres",
    "postgresql+psycopg2": "postgres",
    "postgresql+asyncpg":  "postgres",
    "pg":                  "postgres",
    "redshift+psycopg2":   "redshift",
    "azure-sql":           "azuresql",
}
```

**为什么**：用户从 dlt / SQLAlchemy 文档抄 URI，scheme 各种写法都接受，ingestr 归一化到内部名。

**文件型特殊处理**：jsonl/csv/parquet/avro/sqlite/duckdb/motherduck/md/mmap **不走** `url.Parse`（Windows 路径 `C:\` 会被 `url.Parse` 误识别）。

## 六、Strategy 模式（写行为可插拔）

7 个策略（`pkg/strategy/*.go`）：

| 策略 | 需要的 flag | 行为 |
|------|------------|------|
| `replace` (默认) | 无 | drop → 重建 → 全量写 |
| `truncate+insert` | 无 | `TRUNCATE` → 全量写 |
| `append` | `--incremental-key` | 只追加新行 |
| `delete+insert` | `--incremental-key` | staging → 删增量键命中行 → 插新行 |
| `merge` | `--primary-key` (+ 推荐 `--incremental-key`) | staging → 按 PK upsert |
| `scd2` | `--primary-key` (+ 可选 `--incremental-key`) | 加 `_scd_valid_from`/`_scd_valid_to` |
| `none` | 无 | 干跑（只连不写） |

**所有策略**都遵循 staging 表模式（除 `none`）：

```
[源] → 写 staging 表 → [staging] → swap/merge/delete+insert → [目标]
                          ↑
                   24h TTL，崩溃可恢复
```

`ManagedStagingTTL = 24 * time.Hour`（`pkg/destination/destination.go`）。

**Atomic swap**（`Destination.SupportsAtomicSwap()`）：

- 大多数 SQL 数据库支持（用 `ALTER TABLE ... RENAME` 原子换表）
- 文件型（CSV/Parquet/JSON）不支持 → 直接写目标
- `pkg/destination/destination.go::SupportsAtomicSwap` 决定走哪条路径

## 七、Schema 演进管线

`pkg/schemaevolution/` 三个组件：

| 组件 | 作用 |
|------|------|
| `SchemaComparison` | 比对 source vs destination 的 schema，记录"漂移" |
| `EvolutionPlan` | 把漂移翻译成 DDL（`ALTER TABLE ADD COLUMN` 等） |
| `IngestrColumnFiller` | 加 ingestr 自己的元列（`_ingestr_extracted_at` 等） |

**4 个契约模式**（`--schema-contract`）：

| 模式 | 行为 |
|------|------|
| `evolve` (默认) | 自动应用 EvolutionPlan |
| `freeze` | 任何漂移直接报错 |
| `discard_row` | 漂移字段所在行整行丢弃 |
| `discard_value` | 漂移字段填 NULL |

**3 个命名约定**（`--schema-naming`）：

| 模式 | 行为 |
|------|------|
| `direct` (默认) | 保留原列名 |
| `snake_case` | 强制 snake_case（兼容老 ingestr Python 版） |
| `auto` | 目标表已有则继承，否则 direct |

## 八、Schema-less 源的处理

MongoDB / JSON / Avro 等没有固定 schema：

1. `SourceTable.HasKnownSchema() bool` 返回 `false`
2. Pipeline 触发 `pkg/schemainfer` 拿第一批 RecordBatch 推断
3. 推断失败可手动：`--columns "id:bigint,name:text,created_at:timestamp"` + `--no-inference`

**为什么需要这层**：MongoDB 同一 collection 不同文档可以字段不同，硬推 schema 不可行。实际做法是"看样本，定 schema"。

## 九、Pipeline 总编排（`pkg/pipeline/pipeline.go`）

`Pipeline.Run(ctx)` 流程（1385 行源码）：

```
1. 解析 query annotations（cost attribution 用）
2. uri.DefaultRegistry.GetSource(source-uri)  ← 走 registry
3. source.Connect()
4. uri.DefaultRegistry.GetDestination(dest-uri)
5. destination.Connect()
6. 决定 CDC slot suffix（如果是 CDC 源）
7. 拉 source schema（source.GetTable().GetSchema()）
8. schema 推断（如果 HasKnownSchema() == false）
9. auto-detect 主键（如果用户没给）
10. 决定 strategy
11. 调 strategy.Validate()（检查 PK / incremental-key 齐了没）
12. 比对 source vs destination schema（如果目标表已存在）
13. strategy.Execute()  ← 写数据
14. ApplyEvolution()（应用 schema 演进）
15. 关连接
```

**关键点**：错误处理全程 `fmt.Errorf("...: %w", err)` 包链；中断走 `context.Cancel`；失败自动打印最近 SQL（`config.PrintFailedQuery`）。

## 十、内存与并发

| 项 | 设置 |
|----|------|
| Extract 端并发 | `--extract-parallelism`（默认 4）|
| 数据缓冲 | 通道 `<-chan RecordBatchResult`，无大缓冲 |
| Schema 推断 | 一次 Read 拿样本 |
| Staging 表 | 数据库里，不在内存 |
| 大文件 | 流式，arrow.RecordBatch 按列分块 |

**并发模型**：source 推 batch 到 channel，destination 拉。中间是 `pipeline.ApplyBatchTransformation`（行/字段过滤）、`progress.Tracker.Wrap`（进度跟踪）等可选 wrap。

## 十一、看源码的路线

| 想了解 | 读这些文件 |
|--------|-----------|
| 怎么加新 source | `pkg/source/csv/source.go`（最简单的）+ `pkg/source/postgres/register.go`（注册）+ `internal/registry/registry.go`（核心 registry）|
| 怎么加新 destination | `pkg/destination/sqlite/destination.go`（最简单的）|
| 怎么加新 strategy | `pkg/strategy/replace.go`（最简单的）+ `pkg/strategy/strategy.go`（init 注册）|
| URI 怎么解析 | `internal/uri/parser.go`（95 行）|
| Pipeline 怎么跑 | `pkg/pipeline/pipeline.go` Run() 方法（按行号看）|
| 怎么用 ADBC | `pkg/source/adbc/source.go` + `pkg/source/duckdb/dialect.go` |
| Schema 怎么演 | `pkg/schemaevolution/evolution_plan.go` + `pkg/pipeline/pipeline.go` 的 schema 比对段 |
| 时间戳为什么 microsecond | `pkg/schema/schema.go` + 任何 source 的 mapper.go |

## 十二、理论→实践的桥梁

读懂上面这些，你再看 CLI 行为就能反推：

| 你看到的 | 背后原理 |
|---------|---------|
| `--incremental-strategy merge` 需要 `--primary-key` | `MergeStrategy.Validate()` 检查 |
| `--schema-contract freeze` 跑失败 | `schemaevolution` 抛 `SchemaMismatch` |
| 文件型 URI 三斜杠 | `internal/uri/parser.go::fileBasedSchemes` 跳过 `url.Parse` |
| 第一次跑某个 ADBC 数据库慢 | `pkg/source/adbc/driver.go` 用 dbc 下载驱动 |
| 错误信息三层嵌套 | 源错误用 `%w` 包装保留链 |
| Staging 表名带后缀 | 各 strategy 的 `GenerateStagingTableName` |
| 时间戳列总差几秒 | microsecond 转换（如 MongoDB 毫秒）|

## 十三、总结

ingestr 的设计哲学：

1. **数据格式统一**（Arrow）
2. **驱动统一**（ADBC 走 SQL 类，原生 driver 走 OSS 强的）
3. **行为可插拔**（Source / Destination / Strategy 三接口）
4. **错误可追溯**（`%w` 包装 + 打印最近 SQL）
5. **失败可恢复**（staging 表 + 24h TTL）
6. **类型规约统一**（microsecond 时间戳 + 内部 `DataType` 枚举）
7. **用户友好**（URI 归一化、scheme 别名、自动 PK 检测）

这 7 条就是 skill 里所有命令模板的"理论根"。每一行 CLI flag 都能追到这 7 条之一。
