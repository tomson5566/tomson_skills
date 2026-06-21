# DuckDB 分析模式

> DuckDB SQL 完整速查查 `duckdb-sql` skill 的 `references/01_sql_cheatsheet.md`(1017 行)。
> 本 reference 聚焦**"用 DuckDB 做分析"**的实战模式。

## 1. 两种连接模式

```python
import duckdb

# 模式 A: 全局连接(简单、jupyter 友好、自动管 lifecycle)
result = duckdb.sql("SELECT 1 AS a, 'hello' AS b").df()

# 模式 B: 显式连接(生产、文件持久化)
con = duckdb.connect("analytics.duckdb")
result = con.execute("SELECT ...").df()
con.close()  # 必须显式关
```

**经验**:
- **REPL / 一次性脚本**:全局(模式 A)
- **生产 / 长期跑的服务**:显式(模式 B)+ `try/finally` 关闭
- **FastAPI**:用 `lifespan` 建单例 `con`,`Depends` 注入,`read_only=True` 防误写

## 2. 读取 DuckDB 数据

```python
import duckdb

# 读表到 DataFrame
df = duckdb.sql("SELECT * FROM 'analytics.duckdb'.orders").df()

# 描述
duckdb.sql("DESCRIBE 'analytics.duckdb'.orders").df()
duckdb.sql("SHOW TABLES FROM 'analytics.duckdb'").df()
duckdb.sql("SUMMARIZE SELECT * FROM 'analytics.duckdb'.orders").df()  # 数值+分布概览

# 直接执行查询,落新表
duckdb.sql("""
    CREATE OR REPLACE TABLE analytics.daily_gmv AS
    SELECT order_date, sum(amount) AS gmv
    FROM analytics.orders
    GROUP BY order_date
""")
```

## 3. 注册外部数据源(混搭 Python 数据)

```python
import duckdb
import pandas as pd
import pyarrow as pa

# pandas DataFrame
df = pd.read_csv("live.csv")
duckdb.sql("SELECT * FROM df WHERE amount > 100").df()  # 直接引用变量名

# 或显式注册
con = duckdb.connect()
con.register("live_df", df)
con.sql("SELECT * FROM live_df").df()

# Arrow Table(零拷贝,DuckDB 1.0+)
table = pa.table({"a": [1, 2, 3], "b": ["x", "y", "z"]})
duckdb.sql("SELECT * FROM table").df()  # 零拷贝
```

**实战场景**:
- 1 个 DuckDB 文件 + 1 个 pandas DataFrame → 用 `register` 一起 JOIN
- 大 Parquet 不读进内存 → `duckdb.read_parquet("file.parquet")` 直接走 SQL

## 4. 招牌 SQL 速查(从 duckdb-sql skill 节选)

```sql
-- 排除列(不用列名)
SELECT * EXCLUDE (internal_id, updated_at) FROM users

-- 列模式匹配
SELECT * EXCLUDE (col_[0-9]+) FROM events  -- 伪 SQL,DuckDB 用 COLUMNS()

-- 动态列
SELECT COLUMNS('.*_id') FROM users   -- 所有 id 结尾的列
SELECT COLUMNS(c -> c LIKE '%date%') FROM users  -- 名字含 date 的列

-- 替换列值
SELECT * REPLACE (LOWER(name) AS name, age + 1 AS age) FROM users

-- 分组(GROUP BY ALL 自动识别)
SELECT country, plan, count(*) AS n
FROM users
GROUP BY ALL

-- 窗口函数(QUALIFY 直接过滤窗口结果)
SELECT user_id, order_date, amount,
       row_number() OVER (PARTITION BY user_id ORDER BY order_date) AS rn
FROM orders
QUALIFY rn = 1   -- 用户的首单

-- ASOF JOIN(时序近似匹配)
SELECT o.order_id, o.order_time, q.quote_time, q.price
FROM orders o
ASOF JOIN quotes q
  ON o.symbol = q.symbol AND o.order_time >= q.quote_time

-- PIVOT(行转列)
SELECT * FROM (SELECT country, plan, count(*) AS n FROM users GROUP BY ALL)
PIVOT (sum(n) FOR plan IN ('free', 'pro', 'enterprise'))

-- SAMPLE(随机抽样,快)
SELECT * FROM big_table USING SAMPLE 1%   -- 1% 随机
SELECT * FROM big_table USING SAMPLE 10000 ROWS

-- 窗口内累计
SELECT order_date, gmv,
       sum(gmv) OVER (ORDER BY order_date ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS cum_gmv
FROM daily_gmv
```

完整列表看 `duckdb-sql` skill 的 `references/01_sql_cheatsheet.md`。

## 5. 跨 DB JOIN(不需要 SQLite 中转)

```python
import duckdb

con = duckdb.connect("main.duckdb")
con.execute("ATTACH 'users.duckdb' AS users_db")
con.execute("ATTACH 'orders.duckdb' AS orders_db")
con.execute("ATTACH 's3://my-bucket/events.parquet' AS events_db")  # 直接 ATTACH S3!

# 跨 DB 关联
result = con.sql("""
    SELECT u.user_id, u.country, sum(o.amount) AS gmv, count(DISTINCT e.event_id) AS events
    FROM users_db.users u
    LEFT JOIN orders_db.orders o ON u.user_id = o.user_id
    LEFT JOIN events_db.events e ON u.user_id = e.user_id
    WHERE o.order_date >= '2026-01-01'
    GROUP BY u.user_id, u.country
""").df()
```

**支持的 ATTACH 源**:duckdb/postgres/sqlite/mysql/**S3/HTTP(S) Parquet**/Iceberg(beta)

## 6. 写入 DuckDB(给 Python 计算结果落盘)

```python
# 简单落表
duckdb.sql("CREATE OR REPLACE TABLE out AS SELECT * FROM df")

# 落 Parquet(给 BI 工具读)
duckdb.sql("""
    COPY (SELECT * FROM analytics.orders) TO 'orders.parquet' (FORMAT PARQUET, COMPRESSION zstd)
""")

# 落 CSV(给 Excel 打开)
duckdb.sql("""
    COPY (SELECT * FROM analytics.daily_gmv) TO 'gmv.csv' (HEADER, DELIMITER ',')
""")

# 落 JSON
duckdb.sql("""
    COPY (SELECT * FROM analytics.users LIMIT 1000) TO 'users.json' (FORMAT JSON, ARRAY true)
""")
```

## 7. Python UDF(自定义函数)

```python
import duckdb
from duckdb.typing import INTEGER, VARCHAR

con = duckdb.connect()

# 注册 Python 函数
def categorize(amount: int) -> str:
    if amount > 1000: return "high"
    if amount > 100:  return "mid"
    return "low"

con.create_function("categorize", categorize, [INTEGER], VARCHAR)

# SQL 里用
con.sql("SELECT amount, categorize(amount) AS tier FROM orders").df()
```

**适用场景**:简单业务规则用 SQL CASE,复杂逻辑用 Python UDF。

## 8. 性能调优(实战经验)

```python
con = duckdb.connect("analytics.duckdb")
con.execute("SET memory_limit = '8GB'")          # 限制内存
con.execute("SET threads TO 4")                  # 限制线程
con.execute("PRAGMA enable_profiling")           # 性能分析
con.execute("PRAGMA enable_object_cache")        # 缓存远程对象(S3)
```

### 8.1 物化视图(避免重复算)

```sql
CREATE OR REPLACE TABLE daily_metrics AS
SELECT order_date, count(*) AS n, sum(amount) AS gmv, count(DISTINCT user_id) AS dau
FROM orders
GROUP BY order_date;

-- 后续查
SELECT * FROM daily_metrics WHERE order_date >= '2026-06-01';
```

### 8.2 索引(DuckDB 不支持传统 B-tree,只 ART)

```sql
-- 默认就建了(主键/唯一约束)
-- 显式建(在主键以外)
CREATE INDEX idx_orders_user ON orders(user_id);
```

### 8.3 EXPLAIN 看执行计划

```sql
EXPLAIN SELECT ...   -- 文本
EXPLAIN ANALYZE SELECT ...  -- 实际跑 + 测时
```

### 8.4 读 vs 写权衡

| 操作 | 默认行为 | 调优 |
|---|---|---|
| 大 CSV 读 | 流式 | `SET temp_directory='/fast/ssd/'` |
| 多表 JOIN | in-memory hash | 物化中间表 |
| 频繁重复查 | 每次重算 | 物化视图 |
| 远程 Parquet(S3) | 每次重拉 | `enable_object_cache=true` |

完整性能调优查 `duckdb-sql` skill 的 `references/09_performance_tuning.md`。

## 9. 输出格式选择(给下游)

| 下游 | 格式 | 命令 |
|---|---|---|
| 另一个 Python 脚本 | DataFrame | `.df()` |
| Excel 用户 | CSV/Parquet | `COPY ... TO 'x.csv'` |
| PowerBI | Parquet/ODBC | ODBC 连接 `.duckdb` 或 COPY to Parquet |
| 下次分析 | DuckDB 表 | `CREATE OR REPLACE TABLE` |
| 网页 | JSON | `COPY ... TO 'x.json'` |
| 邮件附件 | CSV | 同 Excel |

## 10. 跟图里 SQLite 的关系

**DuckDB vs SQLite**(BI 工具中转场景):

| 维度 | DuckDB | SQLite |
|---|---|---|
| 写并发 | 单写者 | 单写者(同) |
| 数据规模 | 几 TB | 几 GB |
| SQL 能力 | PostgreSQL 级 + 招牌语法 | SQL 92 子集 |
| 远程 S3/HTTP | ✅ `ATTACH` | ❌ |
| 工具链 | Pandas/Arrow/Plotly 强 | 老 BI 兼容 |

**架构图选 SQLite 中转的真实原因**:PowerBI Desktop(免费版)老版本不直连 DuckDB,SQLite 兼容性最广。

**现代做法**:
- **PowerBI 直连 DuckDB**:装 DuckDB ODBC 驱动 → 直接读 `.duckdb`
- **Tableau 同上**
- **不想装驱动**:DuckDB `COPY ... TO 'x.parquet'` → PowerBI 读 Parquet

跳过 SQLite 的链路:
```
ingestr → DuckDB → COPY to Parquet → PowerBI
```