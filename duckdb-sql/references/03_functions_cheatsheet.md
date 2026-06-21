# DuckDB Functions 速查

按类别分组。完整函数表见 https://duckdb.org/docs/current/sql/functions/overview

---

## Aggregate 聚合函数

**通用聚合**：
```sql
-- 计数
SELECT count(*), count(col), count(DISTINCT col), countif(col > 0) FROM t;

-- 求和/平均
SELECT sum(amount), avg(amount), product(amount) FROM t;
SELECT fsum(amount), favg(amount);  -- Kahan 求和（精确浮点累加）

-- 极值
SELECT min(col), max(col) FROM t;
SELECT arg_min(name, salary), arg_max(name, salary) FROM t;  -- 找最大/最小值对应的 name
SELECT arg_min(name, salary, 3) FROM t;  -- top 3 最低工资的 name

-- 字符串/列表聚合
SELECT string_agg(name, ', ' ORDER BY name) FROM t;  -- "alice, bob, carol"
SELECT list(name ORDER BY name DESC) FROM t;          -- ['name1', 'name2', ...]

-- 布尔
SELECT bool_and(active), bool_or(premium) FROM t;     -- 全 true / 任一 true

-- 直方图
SELECT histogram(bucket, 100, 200, 10) FROM t;  -- 范围 [100,200) 分 10 桶
```

**统计聚合**：
```sql
-- 顺序统计
SELECT
  median(x),
  quantile_cont(x, 0.5),    -- 中位数（同 median）
  quantile_cont(x, 0.95),   -- 95 分位
  quantile_disc(x, 0.5)     -- 中位数（同 median，按实际值）
FROM t;

-- 方差/标准差
SELECT var_samp(x), var_pop(x), stddev_samp(x), stddev_pop(x) FROM t;

-- 协方差/相关
SELECT covar_samp(x, y), corr(x, y) FROM t;

-- 模式（出现次数最多的值）
SELECT mode(x) FROM t;
```

**ordered-set 聚合**（需 ORDER BY）：
```sql
-- 用 ORDER BY 控制排序敏感的聚合
SELECT first(amount ORDER BY date ASC) FROM sales;
SELECT last(amount ORDER BY date DESC) FROM sales;
```

**FILTER 子句**（任何聚合都可用）：
```sql
SELECT
  count(*)                              AS total,
  count(*) FILTER (WHERE status = 'active') AS active,
  sum(amount) FILTER (WHERE region = 'US')  AS us_total
FROM t
GROUP BY dept;
```

**重要特性**：
- 除 `count` 外，**空组返回 NULL**（不是 0/空串）
- 除 `list/first/last` 外，**忽略 NULL**
- `DISTINCT` 适用于几乎所有聚合
- `ORDER BY` 子句（无逗号）：`sum(x ORDER BY y)`

---

## Window 窗口函数

```sql
-- 排名
row_number() OVER (...)
rank()       OVER (...)
dense_rank() OVER (...)
percent_rank() OVER (...)
ntile(4)     OVER (...)  -- 分成 4 桶

-- 偏移
lag(col, n, default)   OVER (ORDER BY ...)
lead(col, n, default)  OVER (ORDER BY ...)
first_value(col)       OVER (...)
last_value(col)        OVER (...)
nth_value(col, n)      OVER (...)

-- 聚合（用 window 形式）
sum(col)   OVER (PARTITION BY dept ORDER BY date)
avg(col)   OVER (PARTITION BY dept ORDER BY date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW)
count(*)   OVER (PARTITION BY dept)

-- 详细语法见 01_sql_cheatsheet.md "WINDOW" 一节
```

---

## Date/Time 函数

```sql
-- 当前
SELECT current_date, current_timestamp, now();

-- 提取
SELECT
  extract(year  FROM ts),
  extract(month FROM ts),
  extract(day   FROM ts),
  extract(hour  FROM ts),
  date_part('dow', ts)    -- day of week (0=Sun)
FROM t;

-- 截断（按粒度对齐）
SELECT date_trunc('month', ts), date_trunc('week', ts) FROM t;

-- 格式化
SELECT strftime(ts, '%Y-%m-%d %H:%M:%S');
SELECT strptime('2024-01-15', '%Y-%m-%d');  -- 字符串 → timestamp

-- 算术
SELECT ts + INTERVAL '7 days', ts - INTERVAL '1 month';
SELECT date '2024-01-01' + 30;  -- 加 30 天

-- 差
SELECT ts1 - ts2;  -- → INTERVAL
SELECT date_diff('day', start, end) FROM t;

-- 时区
SELECT ts AT TIME ZONE 'Asia/Shanghai';
SELECT now() AT TIME ZONE 'UTC';
```

**strftime 格式符**（节选）：
- `%Y` 4 位年 / `%y` 2 位年
- `%m` 月 / `%d` 日
- `%H` 24h / `%I` 12h / `%M` 分 / `%S` 秒
- `%w` 周日=0 / `%u` 周一=1
- `%j` 一年中的第几天

---

## Text 字符串函数

```sql
-- 大小写
SELECT upper(s), lower(s);

-- 长度
SELECT length(s), bit_length(s);

-- 切片（DuckDB 支持负索引，跟 Python 一样）
SELECT s[1:3], s[2:], s[:-1];

-- 拼接
SELECT a || b || c;
SELECT concat(a, b, c);  -- 跳过 NULL
SELECT concat_ws(', ', a, b, c);  -- 跳过 NULL + 自定义分隔符

-- 查找
SELECT position('world' IN s);
SELECT contains(s, 'sub');
SELECT starts_with(s, 'pre'), ends_with(s, 'suf');

-- 替换
SELECT replace(s, 'old', 'new');
SELECT regexp_replace(s, '\d+', 'X', 'g');  -- 正则替换，g=全局

-- 抽取
SELECT substring(s, 3, 5);                  -- 从 1 开始
SELECT regexp_extract(s, '(\d+)-(\d+)', 1);  -- 第一个捕获组
SELECT regexp_extract(s, '(\d+)-(\d+)', ['a','b']);  -- 命名捕获组 → STRUCT

-- 分割
SELECT string_split(s, ',');             -- LIST
SELECT string_split_regex(s, '\s+');
SELECT regexp_split_to_table(s, ',');   -- 一行一元素

-- 修剪
SELECT trim(s), ltrim(s), rtrim(s);
SELECT ltrim(s, ' \t');                 -- 自定义字符

-- 填充
SELECT lpad(s, 10, '0'), rpad(s, 10, '-');

-- 哈希
SELECT md5(s), sha256(s), hash(s);

-- 编码
SELECT hex(s), unhex(hex_str);
SELECT encode(s), decode(encoded);  -- hex/base64
SELECT to_base64(blob), from_base64(s);
```

---

## Numeric 数值函数

```sql
-- 基础
SELECT abs(x), sign(x), round(x, 2), floor(x), ceil(x);

-- 数学
SELECT sqrt(x), cbrt(x), exp(x), ln(x), log10(x), log2(x);
SELECT power(x, y), x ^ y;
SELECT mod(a, b), a % b;

-- 三角
SELECT sin(x), cos(x), tan(x), asin(x), acos(x), atan(x), atan2(y, x);
-- 注：x 必须是弧度

-- 统计
SELECT random();                -- [0, 1) 随机浮点
SELECT setseed(0.42);           -- 固定种子（影响 random()）
SELECT generate_series(1, 10);  -- 1, 2, ..., 10

-- 位运算
SELECT x & y, x | y, x # y, ~x, x << 2, x >> 2;
SELECT bit_count(x);  -- 1 的个数
```

---

## Pattern Matching 模式匹配

```sql
-- LIKE（大小写敏感）
WHERE s LIKE 'A%'        -- 以 A 开头
WHERE s LIKE '%x%'       -- 含 x
WHERE s LIKE 'a_c'       -- 3 字符 a_c
WHERE s LIKE 'a\%c' ESCAPE '\'  -- 转义 %

-- ILIKE（大小写不敏感）
WHERE s ILIKE 'a%'

-- SIMILAR TO（SQL 正则）
WHERE s SIMILAR TO '(A|B)%'

-- POSIX 正则（regexp_matches / regexp_extract 等）
WHERE regexp_matches(s, '^[0-9]+$')
WHERE regexp_matches(s, 'pattern', 'i')  -- 大小写不敏感 flag
```

**regex flags**：`g` 全局 / `i` 大小写不敏感 / `m` 多行 / `s` dotall / `x` verbose

---

## Lambda 函数字段

DuckDB 支持 **lambda 函数**（类似 Python lambda），用于 list/map 转换：

```sql
-- 列表每个元素 * 2
SELECT list_transform([1, 2, 3], x -> x * 2);
-- → [2, 4, 6]

-- 过滤
SELECT list_filter([1, 2, 3, 4], x -> x > 2);
-- → [3, 4]

-- 聚合
SELECT list_reduce([1, 2, 3, 4], (acc, x) -> acc + x);
-- → 10

-- map 转换
SELECT map_from_entries([{'k': 'a', 'v': 1}, {'k': 'b', 'v': 2}]);

-- 嵌套 struct/list 操作
SELECT list_transform(
  list_filter(orders, x -> x.status = 'active'),
  x -> x.amount * 0.9  -- 9 折
) FROM users;
```

---

## Struct / List / Map（嵌套类型）

```sql
-- Struct（类似 dict）
SELECT {'a': 1, 'b': 'x'} AS s;
SELECT s.a, s['b'] FROM (SELECT {'a': 1, 'b': 'x'} AS s);

-- List（数组）
SELECT [1, 2, 3] AS l;
SELECT l[1], l[2:4], list_concat([1,2], [3,4]);

-- Map（key-value 集合）
SELECT MAP {'a': 1, 'b': 2} AS m;
SELECT m['a'], map_keys(m), map_values(m);

-- 解构（dot notation 在 SELECT 里）
SELECT * FROM (VALUES ({'x': 1, 'y': 2})) t(s);
SELECT s.x, s.y FROM ...;

-- UNNEST 展开
SELECT unnest([1, 2, 3]) AS x;  -- 3 行
SELECT unnest([{'a':1}, {'a':2}]) AS item;
```

---

## 类型转换

```sql
-- 显式转换
SELECT CAST(col AS INTEGER);
SELECT col::INTEGER;                    -- DuckDB 简写
SELECT TRY_CAST(col AS INTEGER);        -- 失败返 NULL（不抛错）

-- 常见转换
SELECT '2024-01-15'::DATE;
SELECT '42'::INTEGER;
SELECT 42::VARCHAR;
SELECT [1,2,3]::VARCHAR;                -- 数组转字符串

-- 类型判断
SELECT typeof(col);  -- 'INTEGER' / 'VARCHAR' 等
```

---

## 常用工具函数

```sql
-- UUID
SELECT uuid();                -- 生成 UUID v4
SELECT '6cc6d8b4-3e3e-4a7a-8b2a-7f1b9b1b9b1b'::UUID;

-- 序列
SELECT nextval('seq_name');
CREATE SEQUENCE my_seq START 1;

-- 条件
SELECT if(cond, a, b);                              -- 三元
SELECT CASE WHEN x > 0 THEN 'pos' ELSE 'neg' END;
SELECT coalesce(a, b, c, 'default');                -- 第一个非 NULL
SELECT nullif(a, b);                                -- a == b ? NULL : a

-- 当前用户/版本
SELECT current_user, current_database(), version();
```
