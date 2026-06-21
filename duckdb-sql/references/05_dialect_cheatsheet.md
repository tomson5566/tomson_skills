# DuckDB 方言特性 — 让 SQL 更短更好读

完整页：https://duckdb.org/docs/current/sql/dialect/

---

## Friendly SQL — DuckDB 风格糖

### DDL 简写

```sql
-- CREATE OR REPLACE（脚本里不用先 DROP）
CREATE OR REPLACE TABLE users (id INTEGER, name VARCHAR);

-- CREATE TABLE AS SELECT（用查询结果建表，schema 自动推断）
CREATE TABLE active_users AS
SELECT * FROM users WHERE active = true;

-- CREATE TABLE IF NOT EXISTS
CREATE TABLE IF NOT EXISTS logs (...);
```

### INSERT 简写

```sql
-- INSERT OR IGNORE（= ON CONFLICT DO NOTHING）
INSERT OR IGNORE INTO users (id) VALUES (1);

-- INSERT OR REPLACE（= ON CONFLICT DO UPDATE SET 全列）
INSERT OR REPLACE INTO users (id, name) VALUES (1, 'alice');

-- INSERT INTO ... BY NAME（按列名匹配，不按位置）
INSERT INTO users BY NAME
SELECT 1 AS id, 'alice' AS name;
-- 顺序可乱，列名匹配即可
```

### 查询简写

```sql
-- FROM-first：FROM 开头（隐式 SELECT *）
FROM users;                  -- 等价于 SELECT * FROM users
FROM users WHERE active = true;

-- GROUP BY ALL（自动选所有非聚合列）
SELECT region, count(*), sum(amount)
FROM sales
GROUP BY ALL;   -- 自动按 region 分组

-- ORDER BY ALL（按所有 SELECT 列排序）
SELECT id, name, email FROM users ORDER BY ALL;

-- SELECT * EXCLUDE
SELECT * EXCLUDE (password, ssn) FROM users;

-- SELECT * REPLACE
SELECT * REPLACE (lower(city) AS city) FROM users;

-- UNION BY NAME（按列名合并，不按位置）
SELECT id, name FROM old_users
UNION BY NAME
SELECT id, name FROM new_users;

-- Prefix alias
SELECT res: a + b, ratio: x / y FROM t;
```

### DESCRIBE / SUMMARIZE / SHOW

```sql
-- 描述表结构
DESCRIBE users;
DESCRIBE SELECT * FROM users;

-- 统计描述（每列 min/max/avg/null count 等）
SUMMARIZE users;
SUMMARIZE SELECT * FROM users;

-- 当前数据库内所有表/视图
SHOW TABLES;
SHOW ALL TABLES;          -- 所有 attached 数据库

-- 列出表
FROM information_schema.tables
WHERE table_schema = 'main';
```

---

## DuckDB 特有函数 / 操作符

| 名称 | 用途 | 示例 |
|---|---|---|
| `regexp_matches(s, p)` | 正则匹配 | `WHERE regexp_matches(s, '^\d+$')` |
| `list_*` | 列表操作 | `list_transform(l, x -> x*2)` |
| `map_*` | 映射操作 | `map_keys(m), map_values(m)` |
| `struct_pack(...)` | 构造 struct | `struct_pack(a := 1, b := 'x')` |
| `COLUMNS(...)` | 列名模式匹配 | `SELECT COLUMNS('.*_id') FROM t` |
| `EXCLUDE` / `REPLACE` | 调整 `*` | `SELECT * EXCLUDE (pwd) FROM t` |
| `ASOF JOIN` | 近似时间点 JOIN | `o ASOF JOIN s ON o.stock = s.stock` |
| `LATERAL` | 横向引用 | `FROM t, LATERAL unnest(t.list)` |
| `QUALIFY` | 窗口后过滤 | `SELECT ... QUALIFY row_number() OVER (...) = 1` |
| `PIVOT` / `UNPIVOT` | 行列转置 | 见 01_sql_cheatsheet |
| `SAMPLE` | 抽样 | `USING SAMPLE 1%` |
| `IF NOT EXISTS` | 各种 DDL 保护 | `CREATE TABLE IF NOT EXISTS` |
| `current_setting('x')` | 读配置 | `SELECT current_setting('memory_limit')` |

**QUALIFY** 是 DuckDB/Snowflake/BigQuery 特有：像 HAVING，但作用在窗口函数上：

```sql
-- 每组只保留最大 salary 的行
SELECT name, dept, salary
FROM employees
QUALIFY row_number() OVER (PARTITION BY dept ORDER BY salary DESC) = 1;
```

---

## PostgreSQL 兼容

DuckDB **尽量兼容 PostgreSQL**。**不兼容 / 差异点**：

| 项 | DuckDB 行为 | PG 行为 |
|---|---|---|
| `SELECT` 无 `FROM` | 允许（`SELECT 1;`） | 允许 |
| 隐式类型转换 | 更宽容 | 严格 |
| 默认事务 | 每条 statement 自动 commit | 同上 |
| `SERIAL` | 不支持，用 `INTEGER PRIMARY KEY` + 序列或 `GENERATED ALWAYS AS IDENTITY` | `SERIAL` 是 PG 简写 |
| `ILIKE` | 支持 | 支持 |
| `RETURNING` | 支持 | 支持 |
| `WITH RECURSIVE` | 支持 | 支持 |
| `DISTINCT ON` | 支持 | 支持 |
| `FILTER (WHERE ...)` 聚合 | 支持 | 支持 |
| `EXCLUDE` / `REPLACE` / `COLUMNS` | 支持 | 不支持 |
| `QUALIFY` | 支持 | 不支持（8.4+ 不支持，要子查询） |
| `ASOF JOIN` | 支持 | 不支持 |
| `SAMPLE` | 支持 | 不支持 |
| `LIST` / `STRUCT` / `MAP` | 原生 | JSON / 数组 / record 类型 |

**其他常见 PG 写法 DuckDB 也支持**：`generate_series`、`regexp_*` 系列、`array_agg`（别名 `list`）、`string_agg` 等。

---

## 标识符与关键字

```sql
-- 关键字可作列名（小写）
SELECT "select" FROM t;        -- 强制转义用双引号
SELECT "group" FROM t;          -- group, order 等保留字

-- 不区分大小写（默认）
SELECT Name FROM Users;         -- 等价于 SELECT name FROM users

-- 保留双引号保留大小写
CREATE TABLE "MyTable" (id INTEGER);
SELECT * FROM "MyTable";        -- 区分大小写
```

---

## 与其他数据库的常见差异

| 操作 | DuckDB | MySQL | PostgreSQL | SQLite |
|---|---|---|---|---|
| 字符串字面量 | `'x'` | `'x'` / `"x"` | `'x'` | `'x'` |
| 标识符引号 | `"x"` | `` `x` `` | `"x"` | `"x"` |
| 字符串拼接 | `\|\|` 或 `concat()` | `CONCAT()` | `\|\|` | `\|\|` |
| LIMIT offset | 支持 | 支持 | 支持 | 支持 |
| 布尔类型 | `BOOLEAN` | `TINYINT(1)` | `BOOLEAN` | `INTEGER` |
| 日期 | `DATE` / `TIMESTAMP` | `DATE` / `DATETIME` | 同 DuckDB | 同 DuckDB |
| 数组 | 原生 `LIST` / `ARRAY` | 不支持 | `ARRAY` | 无 |
| 自增主键 | `GENERATED ... IDENTITY` | `AUTO_INCREMENT` | `SERIAL` | `AUTOINCREMENT` |

---

## DuckDB 不支持 / 用别的方式做

- **SERIAL**：用 `CREATE SEQUENCE` + `nextval` 或 `GENERATED ALWAYS AS IDENTITY`
- **存储过程**：DuckDB 是嵌入式分析库，无 PL/pgSQL；用 Python 客户端写逻辑
- **触发器**：不支持；用 Python 客户端在外层拦截
- **视图更新**：视图只读（不能 INSERT INTO view）
- **外键约束（CASCADE）**：FK 语法支持但 CASCADE/RESTRICT 行为在不同版本演进中
- **行级安全 / RLS**：不支持；用应用层做
