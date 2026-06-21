# DuckDB 性能调优

**DuckDB 已经是列存 + 向量化执行**，但仍有优化空间。这节列实战调优手段。

---

## EXPLAIN / EXPLAIN ANALYZE — 查执行计划

```sql
-- 看逻辑计划
EXPLAIN SELECT * FROM t WHERE x > 100;

-- 看物理执行 + 实际耗时
EXPLAIN ANALYZE SELECT * FROM t WHERE x > 100;
```

输出关键看：
- **operator timings**：哪个算子慢（filter / hash join / aggregate）
- **cardinality**：行数估计 vs 实际（差距大说明统计过期）
- **memory usage**：内存占用
- **parallelism**：是否走多线程

**关键格式**：
```sql
EXPLAIN (ANALYZE, FORMAT JSON) SELECT ...;  -- 机器可读
```

---

## 1. 列存 + 压缩（默认就开）

DuckDB 默认**列存**（不是行存），每个列单独 Parquet-like 压缩：
- 数值列：Dictionary / RLE / Delta 编码
- 字符串：FSST / Dictionary
- 全表压缩比通常 5-10x

**优化手段**：
- **大表用 .ddb 或 Parquet**（不要 CSV 存长期数据）
- **建表用 `WITH (storage_compression = 'zstd')`**（默认 zstd）

```sql
-- 建表时显式指定压缩
CREATE TABLE t (...) WITH (storage_compression = 'zstd');   -- 默认
-- 'uncompressed' / 'snappy' / 'gzip' / 'lz4' / 'zstd'

-- ALTER 改压缩
ALTER TABLE t SET COMPRESSION 'zstd';
```

---

## 2. 索引（**DuckDB 有 ART 索引**）

```sql
-- 主键/唯一约束自动建索引
CREATE TABLE t (id INTEGER PRIMARY KEY, name VARCHAR, age INTEGER);

-- 显式建索引（ART B-tree）
CREATE INDEX idx_name ON t(name);
CREATE INDEX idx_age ON t(age);

-- 唯一索引
CREATE UNIQUE INDEX idx_email ON users(email);

-- 表达式索引
CREATE INDEX idx_lower_name ON t(lower(name));
```

**DuckDB 索引特点**：
- **ART (Adaptive Radix Tree)** —— DuckDB 自研，比 B-tree 在大数据集上更快
- **不是必要的**：DuckDB 对大表扫描已很快（小表加索引可能反而慢）
- **适用场景**：点查（`WHERE x = ?`）、范围查（`BETWEEN`）
- **不适用**：高基数列的 LIKE 前缀查、全表扫描

**是否要建索引**：
- 1 万行以下：**不要建**（开销大于收益）
- 100 万行 + 点查：**建**（10-100x 加速）
- 1000 万行 + 范围查：**建**
- 全表 scan：**不建**

**查索引使用情况**：
```sql
EXPLAIN SELECT * FROM t WHERE name = 'alice';
-- 看 plan 里有没有 "Index Scan"
```

---

## 3. Zone Map（**自动 min/max 索引**）

DuckDB **自动**为每个列存 block 维护 min/max 统计。`WHERE x > 1000` 会**跳过整个 block**：

```sql
-- 自动生效，无需配置
SELECT * FROM t WHERE created_at > '2024-06-01';
-- 自动跳过 created_at < 2024-06-01 的 block
```

**这就是为啥按时间分区建表能加速范围查**。

---

## 4. 投影下推（Projection Pushdown）

DuckDB 只读 SELECT 列表里的列，**不读其他列**：

```sql
-- 只查 col1 → 几乎不读其他列
SELECT col1 FROM huge_table;

-- 查全部列 → 读所有列
SELECT * FROM huge_table;
```

**优化**：
- **永远别用 `SELECT *`** 在大表上
- 显式列名：`SELECT id, name, email FROM users`

---

## 5. 谓词下推（Predicate Pushdown）

WHERE 条件会**尽早下推**到数据源：
- 对 `read_csv` / `read_parquet`：自动加 `WHERE` 到文件读取
- 对 JOIN：自动 reordering（先小表过滤）

```sql
-- DuckDB 自动只读 2024-06 之后的数据
SELECT * FROM read_parquet('data/*.parquet')
WHERE created_at >= '2024-06-01';
```

**优化**：
- WHERE 用**最严格**条件先写
- 用**索引列 / 分区列**做过滤

---

## 6. 内存管理

```sql
-- 设置内存上限（默认总内存 80%）
SET memory_limit = '4GB';

-- 大查询时溢出到磁盘
SET temp_directory = '/tmp/duckdb_tmp';

-- 线程数
SET threads = 8;          -- 0 = 自动（N-1 核）
PRAGMA threads = 8;
```

**Python 端**：
```python
con = duckdb.connect(":memory:", config={
    "memory_limit": "4GB",
    "threads": 4,
    "temp_directory": "/tmp/duckdb",
})
```

---

## 7. 大数据集查询技巧

### a. 避免大 OFFSET 分页

```sql
-- ❌ 慢：扫描 100万+1000 行后丢前 100万
SELECT * FROM events ORDER BY id LIMIT 100 OFFSET 1000000;

-- ✅ 键值游标分页
SELECT * FROM events WHERE id > 1000000 ORDER BY id LIMIT 100;
```

### b. 聚合在分区内做

```sql
-- ❌ 慢：全表扫 + group by
SELECT region, sum(amount) FROM events GROUP BY region;

-- ✅ 快：分区表只扫相关分区
CREATE TABLE events_partitioned (
    id BIGINT,
    region VARCHAR,
    amount DECIMAL(10,2)
) PARTITIONED BY (region);  -- 不支持 PARTITIONED BY，目前 DuckDB 分区靠目录 + read_parquet
```

**实际做法**：把数据按时间/区域拆 Parquet 文件，存到目录，靠 `read_parquet` glob：
```
data/events/year=2024/month=06/part-*.parquet
```
```sql
-- 只读 2024-06 月（谓词下推）
SELECT * FROM read_parquet('data/events/year=2024/month=06/*');
```

### c. 用 Arrow 减少拷贝

```python
# 大结果用 Arrow 拿
arrow = con.execute("SELECT * FROM huge_table").arrow()  # 零拷贝

# 走 Polars
df = con.execute("SELECT * FROM huge_table").pl()         # duckdb 1.0+
```

### d. 流式读（不支持完整 cursor，但可以分页/分批）

```python
# 拿 iterator
rel = con.sql("SELECT * FROM huge_table")
while True:
    batch = rel.fetch_arrow_reader(batch_size=100_000)  # 一批 10万行
    if batch is None:
        break
    process(batch)
```

---

## 8. JOIN 优化

```sql
-- 大小表 JOIN：小表做 build side（小表先广播）
SELECT /*+ BROADCAST(small) */ *
FROM big_table b JOIN small_table s ON b.id = s.id;

-- 等值 JOIN 用 HASH JOIN（默认）
-- 非等值（<, >, ASOF）用 NESTED LOOP 或 ASOF 优化

-- 优化手段：
-- 1. JOIN 键加索引
CREATE INDEX idx_user_id ON orders(user_id);

-- 2. 大表先过滤再 JOIN
SELECT *
FROM (SELECT * FROM big WHERE status = 'active') b
JOIN small s ON b.id = s.id;

-- 3. 用 CTE 拆复杂查询（避免大 in-memory 临时表）
```

---

## 9. 并行执行

DuckDB 默认用 `N-1` 个线程（自动），无需配置。

```sql
-- 强制单线程（debug 用）
SET threads = 1;

-- 8 线程（生产）
SET threads = 8;
```

**哪些算子并行**：
- Scan（多 block 并行读）
- Filter
- Aggregate（group by 多分区并行）
- Hash Join（build/probe 两阶段并行）
- Sort

**哪些不并行**：
- Window function（**单线程**！大数据慎用）
- 全局 LIMIT（最后一步）

---

## 10. 性能反模式（**避坑**）

| 反模式 | 后果 | 修法 |
|---|---|---|
| `SELECT *` 大表 | 多读 5-10x 数据 | 显式列名 |
| 对大列用 `LIKE '%xx%'` | 全扫 | 改全文索引或反范式 |
| `OFFSET 1000000` | 扫描百万 + 丢 | 键值游标 |
| `count(*)` 在窗口里 | 全量 buffer | 改聚合 |
| `ORDER BY` 无 LIMIT | 排序全量 | 加 LIMIT 或窗口函数 |
| 嵌套多层子查询 | 优化器不识别 | 改 CTE |
| `IN (SELECT ...)` 大集合 | 全哈希 | 改 JOIN |
| 用 pandas `.iterrows()` 循环 | Python 慢 | 直接 SQL + Arrow |
| 频繁 `register()/unregister()` | register 开销 | 一次注册多查询 |
| 同一 query 跑 1000 次 | 每次解析 | 用 `prepare()` |

---

## 11. 性能分析脚本

```python
import time
import duckdb

con = duckdb.connect("data.ddb", read_only=True)

queries = [
    "SELECT count(*) FROM events",
    "SELECT region, sum(amount) FROM events GROUP BY 1",
    "SELECT * FROM events WHERE user_id = 42",
]

for q in queries:
    start = time.time()
    result = con.execute(q).df()
    elapsed = time.time() - start
    print(f"{elapsed:.3f}s | {len(result):>8d} rows | {q[:60]}")
```

**用 EXPLAIN 找瓶颈**：
```sql
EXPLAIN ANALYZE
SELECT region, sum(amount)
FROM events
WHERE created_at >= '2024-01-01'
GROUP BY region;

-- 看输出：
-- 1. 哪个算子占 90% 时间？
-- 2. 哪行 row count 估计错？
-- 3. 有没有不必要的 sort / materialization？
```

---

## 12. 性能数字参考（**实测经验值**）

| 场景 | 数据量 | 典型时间 |
|---|---|---|
| `count(*)` 全表 | 1 亿行 | 0.5-1.5s |
| `count(*) WHERE indexed_col = ?` | 1 亿行 | 0.05-0.2s |
| `SELECT 5 cols` 全表 | 1 亿行 | 2-5s |
| Parquet 10GB `count(*)` | 10亿行 | 3-8s |
| Parquet 10GB `sum(col)` 单列 | 10亿行 | 1-3s（只读 1 列） |
| 1 亿行 group by 单列 | 1 亿行 | 1-3s |
| 1 亿行 group by 3 列 | 1 亿行 | 3-8s |
| 两表 hash join 各 100万 | 200万 | 0.5-1.5s |
| 1 亿行 window function | 1 亿行 | **30-120s（单线程！）** |

**机器**：8 核 / 32GB / NVMe SSD，duckdb 1.5.x

---

## 13. 配置文件调优（高级）

`~/.duckdbrc` 文件（**home directory** 启动时自动加载）：

```ini
.memory_limit 4GB
.threads 8
.temp_directory /tmp/duckdb
```

**项目级**（项目根目录的 `.duckdbrc`）：
- duckdb 不支持项目级 .duckdbrc
- 用脚本：`SET memory_limit = '4GB';` 在 SQL 开头
- 或 `con.execute("SET memory_limit = '4GB'")` 在 Python 启动时
