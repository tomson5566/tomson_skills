# DuckDB SQL 速查 — Query Syntax

agent 写 DuckDB 查询时查这里。**这不是 SQL 完整语法手册**，只列项目里最常用的写法。完整文档见 https://duckdb.org/docs/current/sql/

## SELECT — 投影

DuckDB 的 SELECT 表达式"逻辑上最后执行"（先 FROM/WHERE/GROUP BY 跑完才 SELECT）。可包含任意表达式、聚合、窗口函数。

```sql
-- 基本投影 + 算术 + 别名
SELECT col1 + col2 AS res, sqrt(col1) AS root FROM tbl;

-- DuckDB 风格 prefix alias（不用 AS）
SELECT
  res: col1 + col2,
  root: sqrt(col1)
FROM tbl;

-- DISTINCT
SELECT DISTINCT city FROM addresses;

-- EXCLUDE：全列但去掉某列
SELECT * EXCLUDE (city) FROM addresses;

-- REPLACE：全列但替换某列
SELECT * REPLACE (lower(city) AS city) FROM addresses;

-- COLUMNS() 模式匹配（按正则选列）
SELECT COLUMNS('.*_id') FROM tbl;
SELECT COLUMNS(*)::VARCHAR FROM tbl;        -- 转所有列为字符串
SELECT MIN(COLUMNS(*)) FROM tbl;            -- 对所有列取 MIN
```

**注意**：`EXCLUDE` / `REPLACE` / `COLUMNS` 是 DuckDB 扩展语法，其他数据库没有。

## FROM — 数据源 + JOIN

FROM 子句列出数据源（表、视图、子查询、文件 path）。**JOIN 在 FROM 内声明**：

```sql
-- 显式 JOIN 清晰
SELECT * FROM t1 INNER JOIN t2 ON t1.id = t2.id;
SELECT * FROM t1 LEFT JOIN t2 ON t1.id = t2.id;     -- LEFT JOIN 时 NULL 行保留
SELECT * FROM t1 RIGHT JOIN t2 ON t1.id = t2.id;
SELECT * FROM t1 FULL OUTER JOIN t2 ON t1.id = t2.id;

-- USING 简写（双方列名相同时）
SELECT * FROM t1 JOIN t2 USING (id);

-- NATURAL JOIN（自动按同名列 join，慎用，易出错）
SELECT * FROM t1 NATURAL JOIN t2;

-- 多表 JOIN
SELECT *
FROM orders o
JOIN customers c ON o.customer_id = c.customer_id
JOIN products p ON o.product_id = p.product_id;

-- 同一表多次引用（self join）
SELECT e1.name, e2.name AS manager
FROM employees e1
LEFT JOIN employees e2 ON e1.manager_id = e2.employee_id;
```

**ASOF JOIN**（DuckDB 特色）：**最近时间点**连接，财经常用：
```sql
-- 找每个订单在当时的最近股价
SELECT *
FROM orders o
ASOF JOIN stock_prices s
  ON o.stock = s.stock
 AND s.ts <= o.ts;  -- ASOF 关键：取 <= o.ts 的最大 s.ts
```

**LATERAL JOIN** / **POSITIONAL JOIN**（DuckDB 扩展）：参考官方文档（不常用）。

## WHERE — 行过滤

```sql
SELECT * FROM tbl WHERE col > 100 AND status = 'active';

-- 半开区间（推荐）
WHERE created_at >= '2024-01-01' AND created_at < '2024-02-01';
-- 比 BETWEEN 准确：BETWEEN 两端都包含（含 2 月 1 日 0 点）

-- IN / NOT IN
WHERE country IN ('US', 'CA', 'MX');
WHERE id NOT IN (SELECT user_id FROM banned);

-- 模式匹配
WHERE name LIKE 'A%';             -- 通配符：% 任意串，_ 单字符
WHERE name ILIKE 'a%';            -- 大小写不敏感
WHERE name SIMILAR TO '(A|B)%';   -- SQL 正则
WHERE regexp_matches(email, '^[a-z]+@');  -- POSIX 正则

-- NULL 处理
WHERE col IS NULL;                -- 不是 = NULL！
WHERE col IS NOT NULL;
```

## GROUP BY + HAVING — 聚合

```sql
SELECT
  status,
  COUNT(*)                                    AS order_count,
  SUM(total_amount)                           AS total_revenue,
  AVG(total_amount)                           AS avg_amount,
  COUNT(*) FILTER (WHERE status = 'completed') AS completed_count   -- FILTER 聚合
FROM orders
WHERE order_date >= '2024-01-01'
GROUP BY status
HAVING COUNT(*) > 10                          -- HAVING 过滤聚合后
ORDER BY order_count DESC;
```

**关键**：
- `FILTER (WHERE ...)` 是 DuckDB/PostgreSQL 扩展，等价于 `SUM(CASE WHEN ... THEN 1 END)`，可读性好
- SELECT 里没在 GROUP BY 的非聚合列会报错（SQL 严格模式）
- `COUNT(DISTINCT user_id)` 计不重复用户

## ORDER BY + LIMIT — 排序分页

```sql
SELECT * FROM tbl
ORDER BY col1 ASC, col2 DESC NULLS LAST   -- NULLS FIRST/LAST 控制 NULL 位置
LIMIT 100 OFFSET 1000;                    -- 分页（大数据 OFFSET 慢，见性能页）
```

**避免大 OFFSET**：用键值游标分页：
```sql
SELECT * FROM tbl WHERE id > 1000 ORDER BY id LIMIT 100;
```

## WINDOW — 窗口函数

```sql
-- ROW_NUMBER / RANK / DENSE_RANK
SELECT
  name,
  salary,
  dept,
  ROW_NUMBER() OVER (PARTITION BY dept ORDER BY salary DESC) AS rn,
  RANK()       OVER (PARTITION BY dept ORDER BY salary DESC) AS rk,
  DENSE_RANK() OVER (PARTITION BY dept ORDER BY salary DESC) AS drk
FROM employees;

-- 累计聚合
SELECT
  date,
  amount,
  SUM(amount) OVER (ORDER BY date) AS running_total
FROM sales;

-- 移动平均（3 天）
SELECT
  date,
  amount,
  AVG(amount) OVER (ORDER BY date ROWS BETWEEN 2 PRECEDING AND CURRENT ROW) AS ma3
FROM sales;

-- LAG / LEAD 取前/后一行
SELECT
  date,
  amount,
  LAG(amount, 1, 0) OVER (ORDER BY date)  AS prev,
  LEAD(amount, 1, 0) OVER (ORDER BY date) AS next
FROM sales;

-- 每组取 Top N：ROW_NUMBER 套子查询
WITH ranked AS (
  SELECT *, ROW_NUMBER() OVER (PARTITION BY dept ORDER BY salary DESC) AS rn
  FROM employees
)
SELECT * FROM ranked WHERE rn <= 3;

-- 或 DuckDB 简化：DISTINCT ON
SELECT DISTINCT ON (dept) *
FROM employees
ORDER BY dept, salary DESC;
```

**WINDOW 子句**：多个窗口函数用同一窗口定义时，命名复用避免重复：
```sql
SELECT
  name,
  ROW_NUMBER() OVER w AS rn,
  RANK()       OVER w AS rk
FROM employees
WINDOW w AS (PARTITION BY dept ORDER BY salary DESC);
```

**窗口框架 (Frame)**：`ROWS BETWEEN ... AND ...` 控制窗口边界：
- `UNBOUNDED PRECEDING` / `UNBOUNDED FOLLOWING` — 起点/终点
- `n PRECEDING` / `n FOLLOWING` — 相对当前位置
- `CURRENT ROW` — 当前行
- 默认 `RANGE UNBOUNDED PRECEDING`（按值范围而非物理行数）

## WITH (CTE) — 公共表表达式

```sql
-- 普通 CTE
WITH high_spenders AS (
  SELECT customer_id, SUM(amount) AS total
  FROM orders
  GROUP BY customer_id
  HAVING SUM(amount) > 1000
)
SELECT c.name, hs.total
FROM customers c
JOIN high_spenders hs USING (customer_id);

-- 多 CTE（链式）
WITH
  q1 AS (SELECT ...),
  q2 AS (SELECT ... FROM q1),
  q3 AS (SELECT ... FROM q2)
SELECT * FROM q3;

-- MATERIALIZED 提示（强制物化，避免优化器把它当子查询展开）
WITH cte AS MATERIALIZED (SELECT ...)
SELECT * FROM cte;
```

**递归 CTE**（处理树/图）：
```sql
WITH RECURSIVE org_tree AS (
  -- 锚点：起始节点
  SELECT id, name, manager_id, 1 AS depth
  FROM employees
  WHERE manager_id IS NULL

  UNION ALL

  -- 递归：子节点
  SELECT e.id, e.name, e.manager_id, t.depth + 1
  FROM employees e
  JOIN org_tree t ON e.manager_id = t.id
)
SELECT * FROM org_tree ORDER BY depth, name;
```

## SAMPLE — 抽样

```sql
-- 10% 行抽样
SELECT * FROM large_table USING SAMPLE 10%;

-- 1000 行抽样
SELECT * FROM large_table USING SAMPLE 1000 ROWS;

-- 伯努利抽样（每行独立概率 1%）
SELECT * FROM large_table USING SAMPLE 1% BERNOULLI;
```

## PIVOT / UNPIVOT — 行列转置

```sql
-- PIVOT：行转列
SELECT * FROM (SELECT country, year, sales FROM data)
PIVOT (SUM(sales) FOR year IN (2020, 2021, 2022));

-- UNPIVOT：列转行
SELECT * FROM (SELECT * FROM data)
UNPIVOT (sales FOR year IN (sales_2020, sales_2021, sales_2022));
```

## 完整查询执行顺序

逻辑上（不是书写顺序）：
```
FROM (含 JOIN)
WHERE
GROUP BY
HAVING
窗口函数（在 SELECT 里）
SELECT (含 DISTINCT)
ORDER BY
LIMIT / OFFSET
```
理解这点能避免很多 GROUP BY 错（"为什么我 SELECT 里的字段不在 GROUP BY"）。

## 常见反模式

- **大 OFFSET 分页** → 改键值游标
- **隐式 JOIN (`,`)** → 用 `INNER JOIN ... ON`
- **对字符串列用函数再比较** → 索引失效，先 WHERE 后函数
- **`= NULL`** → 永远是 NULL，**用 `IS NULL`**
- **BETWEEN 端点日期** → 半开区间更安全
- **`SELECT *`** → 显式列名（性能 + 可读性 + 抗 schema 变化）
