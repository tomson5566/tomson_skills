# 数据处理

> ingestr 不是 dbt——它不做 SQL 转换、UDF、聚合。它只做"搬运 + 简单的列级处理"。
> 列级处理包括：脱敏（mask）、列排除、自定义 SQL 选列、列重命名（通过 schema naming）。

## 1. 数据脱敏（`--mask`）

格式：`--mask <column>:<algorithm>[:<param>]`

可多次指定，多次叠加。

| Algorithm | Param | 效果 | 例子 |
|-----------|-------|------|------|
| `hash` | - | SHA256 哈希（不可逆）| `alice@example.com` → `a3f5...d8` |
| `partial` | 末位保留 N 位 | 保留末 N 位，其余替换 | `123456789` (N=4) → `*****6789` |
| `round` | 圆整基数 | 四舍五入到基数倍 | `12345` (基 1000) → `12000` |
| `nullify` | - | 全部置 NULL | `secret` → `NULL` |
| `redact` | - | 替换为 `***REDACTED***` | `secret` → `***REDACTED***` |

```bash
ingestr ingest \
  --source-uri "postgres://u:p@prod/db" \
  --source-table "users" \
  --dest-uri "duckdb:///dev.db" \
  --dest-table "users_dev" \
  --mask "email:hash" \
  --mask "ssn:partial:4" \
  --mask "salary:round:1000" \
  --mask "phone:redact" \
  --yes
```

**适用场景**：

- 同步生产数据到开发/测试环境
- 合规（GDPR/CCPA/HIPAA）
- 数据共享给第三方时保护 PII

**理论**：`pkg/transformer/ColumnMasker` 在批次级别应用 mask。

## 2. 自定义 SQL（`query:` 前缀）

不一定要取整张表——可以用 SQL 选列、过滤、JOIN。

**语法**：`--source-table "query:<SQL>"`

```bash
# 选列 + 过滤
--source-table "query:SELECT id, name, email, created_at FROM users WHERE active = true"

# JOIN
--source-table "query:SELECT u.id, u.name, o.amount FROM users u JOIN orders o ON u.id = o.user_id"

# 聚合（注意 ingestr 不做聚合后的合并——需要下游处理）
--source-table "query:SELECT DATE_TRUNC('day', created_at) AS day, COUNT(*) AS cnt FROM events GROUP BY 1"

# 子查询
--source-table "query:SELECT * FROM (SELECT ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY created_at DESC) AS rn, * FROM events) WHERE rn = 1"
```

**注意**：

- 不同数据库的 SQL 方言不同，BigQuery 用反引号，PG 用双引号
- 用了 `query:` 就不传 `incremental-key` 给数据库（自己用 SQL 处理）
- 不能用 `incremental-key` 自动过滤了——手动 `WHERE created_at > '...'`

**理论**：`pkg/source.IsCustomQuery()` 识别 `query:` 前缀。

## 3. Schema-less 源的列定义（`--columns` + `--no-inference`）

MongoDB / JSON / Avro 没有固定 schema。两种方式定义：

**方式 A：让 ingestr 推断**（默认）

```bash
ingestr ingest \
  --source-uri "mongodb://..." \
  --source-table "events" \
  --dest-uri "..." \
  --dest-table "events" \
  --yes
# ingestr 读 1000 行推断
```

**方式 B：手动指定**（更稳）

```bash
ingestr ingest \
  --source-uri "mongodb://..." \
  --source-table "events" \
  --dest-uri "..." \
  --dest-table "events" \
  --columns "id:string,event_type:string,timestamp:timestamp,payload:json,user_id:int64" \
  --no-inference \
  --yes
```

**类型关键字**（来自 `pkg/schema/json_type.go` 和 `schema.go`）：

| 关键字 | 内部类型 | 适用 |
|--------|---------|------|
| `string` | TypeString | 文本 |
| `boolean` | TypeBoolean | 布尔 |
| `int16` / `int32` / `int64` | TypeInt* | 整数 |
| `float32` / `float64` | TypeFloat* | 浮点 |
| `decimal` | TypeDecimal | 精确小数（PG numeric, BigQuery NUMERIC）|
| `date` | TypeDate | 日期 |
| `time` | TypeTime | 时间 |
| `timestamp` | TypeTimestamp | 时间戳 |
| `json` | TypeJSON | JSON 文档 |
| `uuid` | TypeUUID | UUID |
| `binary` | TypeBinary | 二进制 |
| `array` | TypeArray | 数组 |

**推断的局限**：

- 同一字段混合类型（int 和 string）→ 推断会选 string
- 嵌套结构 → `json` 类型
- 大文档推断慢（默认看 1000 行）

## 4. 列排除（`--sql-exclude-columns`）

自定义 SQL 之外的"列排除"方式：

```bash
# 拉取时不拉 password 列
ingestr ingest \
  --source-uri "postgres://..." \
  --source-table "users" \
  --sql-exclude-columns "password" \
  --sql-exclude-columns "ssn" \
  --dest-uri "..." \
  --yes
```

可多次指定。

**vs `--mask`**：

- `--sql-exclude-columns`：**不拉**该列，源端就过滤（节省带宽）
- `--mask`：**拉了**再脱敏，目标表还保留该列（只是值变了）

**适用**：

- 带宽/内存敏感（`--sql-exclude-columns`）
- 目标表需要这列但值要变（`--mask`）

## 5. 行限制（`--sql-limit`）

**debug 用**——限制源端拉取行数：

```bash
ingestr ingest --sql-limit 100 ... --yes
# 只拉 100 行，验证连通 + 类型映射
```

跑通后去掉 `--sql-limit` 跑全量。

## 6. 全量重置（`--full-refresh`）

**忽略任何状态**——删除目标表重建：

```bash
ingestr ingest --full-refresh ... --yes
```

**vs `replace` 策略**：

- `replace`（策略）：drop → recreate → 写（每次都这样）
- `--full-refresh`（一次性 flag）：本次跑时强制 drop → recreate

**适用**：

- 目标表 schema 跟源严重不匹配
- 改过 `--schema-naming` 想重新建表
- 改过 `--primary-key`

## 7. CDC（变更数据捕获）— 特殊的数据处理

需要源端支持 logical replication。详细见 `references/cdc.md`。

```bash
ingestr ingest \
  --source-uri "postgres://u:p@host/db" \
  --source-table "orders" \
  --dest-uri "bigquery://..." \
  --dest-table "orders_cdc" \
  --yes
```

ingestr 自动派生 dest-aware slot 后缀，resume LSN 从目标推断。

## 8. 实战检查清单

- [ ] PII 字段都加了 `--mask`？
- [ ] 拉取列太多？用 `--sql-exclude-columns` 减负
- [ ] 只想取部分行/列？用 `query:` 前缀
- [ ] MongoDB 字段类型不稳？用 `--columns --no-inference`
- [ ] 第一次跑大表？用 `--sql-limit 100` 验证
- [ ] 目标表 schema 太乱？用 `--full-refresh` 重置
