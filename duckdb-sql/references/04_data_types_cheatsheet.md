# DuckDB Data Types 速查

完整表：https://duckdb.org/docs/current/sql/data_types/overview

---

## 数值类型

| Type | Aliases | 范围 | 大小 |
|---|---|---|---|
| `TINYINT` | `INT1` | -128..127 | 1B |
| `SMALLINT` | `INT2`/`SHORT` | -32K..32K | 2B |
| `INTEGER` | `INT4`/`INT` | -2.1B..2.1B | 4B |
| `BIGINT` | `INT8`/`LONG` | -9.2e18..9.2e18 | 8B |
| `HUGEINT` | `INT128` | -1.7e38..1.7e38 | 16B |
| `BIGNUM` | | 可变长，超大整数 | 可变 |
| `FLOAT` | `FLOAT4`/`REAL` | 单精度 | 4B |
| `DOUBLE` | `FLOAT8` | 双精度 | 8B |
| `DECIMAL(p,s)` | `NUMERIC(p,s)` | 精确定点 | 2-16B |
| `UTINYINT/USMALLINT/UINTEGER/UBIGINT/UHUGEINT` | | 对应无符号 | |

**DECIMAL 默认**：`DECIMAL(18, 3)` — 18 位总精度，3 位小数。**WIDTH > 19 性能差**（用 INT128）。

```sql
CREATE TABLE t (
  id INTEGER PRIMARY KEY,
  amount DECIMAL(10, 2),     -- 最多 10 位，2 位小数
  ratio DOUBLE
);
```

---

## 字符串

| Type | 说明 |
|---|---|
| `VARCHAR` | 可变长（推荐，**别用 CHAR(n)**） |
| `BLOB` | 二进制数据（别名 `BYTEA`/`VARBINARY`） |
| `BIT` | 比特串 |

字符串字面量：`'hello'`（单引号），`"col_name"`（双引号是 identifier）。

```sql
-- 字符串内单引号
SELECT 'it''s ok';
-- 或用 E''
SELECT E'string with\nnewline';
```

---

## 日期/时间

| Type | 范围/精度 | 大小 |
|---|---|---|
| `DATE` | 公元前 5M 年 ~ 后 5M 年 | 4B |
| `TIME` | 微秒精度 | 8B |
| `TIMESTAMP` | 微秒精度（**不存时区**） | 8B |
| `TIMESTAMPTZ` | TIMESTAMP + 时区 | 8B |
| `INTERVAL` | 月-日-微秒三元组 | 16B |

**重要**：
- `TIMESTAMP` 不存时区，存的是绝对时刻（UTC 等价值）。**写入/读取时按会话时区转换**
- `TIMESTAMPTZ` 推荐用于跨时区应用
- `now()` / `current_timestamp` 返 TIMESTAMPTZ
- 字符串 → TIMESTAMP：`'2024-01-15 10:30:00'::TIMESTAMP`

```sql
-- 设置会话时区
SET TimeZone = 'Asia/Shanghai';

-- TIMESTAMPTZ 显示按当前时区
SELECT now();  -- 2024-01-15 18:30:00+08

-- 切换时区
SELECT now() AT TIME ZONE 'UTC';  -- 2024-01-15 10:30:00
```

---

## 布尔/UUID/JSON

| Type | 说明 |
|---|---|
| `BOOLEAN` | true/false |
| `UUID` | 16 字节 |
| `JSON` | JSON 文档（**需装 json 扩展**） |

```sql
-- UUID
SELECT uuid();  -- 生成 v4
SELECT '6cc6d8b4-3e3e-4a7a-8b2a-7f1b9b1b9b1b'::UUID;

-- JSON
INSTALL json;
LOAD json;
SELECT '{"a": 1}'::JSON;
SELECT json_extract('{"a": 1}', '$.a');  -- 1
```

---

## 嵌套类型（**DuckDB 强项**）

### STRUCT（类似 dict）
```sql
SELECT {'a': 1, 'b': 'x'} AS s;            -- 字面量
SELECT s.a, s['b'] FROM ...;                 -- 访问
CREATE TABLE t (s STRUCT(a INTEGER, b VARCHAR));  -- 字段类型
```

### LIST（数组，可变长）
```sql
SELECT [1, 2, 3] AS l;
SELECT l[1], l[2:4], list_concat([1,2], [3,4]);
CREATE TABLE t (l INTEGER[]);     -- LIST 等价于 ARRAY 但更灵活
```

### ARRAY（数组，定长）
```sql
CREATE TABLE t (l INTEGER[3]);    -- 必须恰好 3 个元素
```

### MAP（key-value）
```sql
SELECT MAP {'a': 1, 'b': 2} AS m;
SELECT m['a'], map_keys(m), map_values(m);
CREATE TABLE t (m MAP(VARCHAR, INTEGER));
```

### UNION（任一类型）
```sql
SELECT union_value(num := 2) AS u;
SELECT union_value(str := 'ABC')::UNION(str VARCHAR, num INTEGER);
CREATE TABLE t (u UNION(num INTEGER, str VARCHAR));
```

### VARIANT（半结构化，每行自带类型信息）
```sql
SELECT 42::VARIANT;
CREATE TABLE t (v VARIANT);
```

---

## NULL 处理

DuckDB 把 NULL 当作"未知"。关键规则：

- `NULL = NULL` → NULL（不是 TRUE）
- `count(NULL)` → 0（聚合忽略 NULL）
- `count(*)` → 包含 NULL 行
- `sum(NULL)` → NULL

```sql
SELECT NULL IS NULL;           -- true
SELECT NULL = NULL;            -- NULL（不是 true!）
SELECT NULLIF(a, b);           -- a==b ? NULL : a
SELECT COALESCE(a, b, c, 0);   -- 第一个非 NULL
```

---

## 类型转换

**隐式转换**（DuckDB 很宽容）：
- 数值类型互转（TINYINT → INTEGER → BIGINT）
- VARCHAR ↔ DATE/TIMESTAMP/BOOLEAN（可解析时）
- `0` ↔ FALSE，`1` ↔ TRUE
- `''` ↔ NULL（CSV 空字段）

**显式转换**：
```sql
SELECT CAST(col AS INTEGER);
SELECT col::INTEGER;            -- 简写
SELECT TRY_CAST(col AS INTEGER);  -- 失败返 NULL，不报错
```

**查看类型**：
```sql
SELECT typeof(col);
```

---

## 类型选择实战建议

| 场景 | 用什么 |
|---|---|
| 普通整数 | `INTEGER`（4 字节最常用） |
| 超大整数 | `BIGINT`（>2.1B） |
| 极大整数 | `HUGEINT` 或 `BIGNUM`（>9.2e18） |
| 浮点计算 | `DOUBLE`（**别用 FLOAT，精度不够**） |
| 钱/金融 | `DECIMAL(18, 2)`（避免浮点累积误差） |
| 文本 | `VARCHAR`（别用 `CHAR(n)`） |
| 时间戳 | `TIMESTAMPTZ`（除非你明确要无时区） |
| JSON 数据 | `JSON` 类型 + json 扩展 |
| 半结构化（key 频繁变） | `VARIANT` 或 `STRUCT` |
| 同构数组 | `LIST<T>` |
| 异构字段 | `STRUCT(k1 T1, k2 T2)` |
| Key-value（多 key） | `MAP(K, V)` |
