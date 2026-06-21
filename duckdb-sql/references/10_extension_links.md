# DuckDB 官方文档扩展入口

**skill 留的扩展位**。当 references/01-09 不够用时，从这里顺藤摸瓜到官方 12 个分类的子文档。

> **约定**：所有链接以 `https://duckdb.org/docs/current/sql/` 为根。
> 比如 `query_syntax/select` → `https://duckdb.org/docs/current/sql/query_syntax/select`
>
> agent 抓新内容用 `curl` 即可（参考本 skill 学习时用的脚本 `/tmp/fetch_duckdb_docs.py`）。

---

## 1. 总览

- [Introduction](https://duckdb.org/docs/current/sql/introduction) — 必读，SQL 哲学 + 基本概念

---

## 2. Query Syntax（19 个子文档）— 写查询的核心

| 子文档 | URL | 说明 |
|---|---|---|
| SELECT | `query_syntax/select` | 投影、EXCLUDE/REPLACE/COLUMNS |
| FROM + JOIN | `query_syntax/from` | JOIN 类型、ASOF/LATERAL/POSITIONAL |
| WHERE | `query_syntax/where` | 过滤（部分内容在 select 页） |
| GROUP BY | `query_syntax/group_by` | 聚合 + GROUP BY ALL |
| ORDER BY | `query_syntax/order_by` | 排序 + NULLS FIRST/LAST |
| LIMIT | `query_syntax/limit` | 分页 |
| WINDOW | `query_syntax/window` | 命名窗口 |
| WITH (CTE) | `query_syntax/with` | 普通 + 递归 CTE |
| SAMPLE | `query_syntax/sample` | 抽样 |
| PIVOT / UNPIVOT | `query_syntax/pivot_unpivot` | 行列转置 |
| VALUES | `query_syntax/values` | 字面量行 |
| SET Operations | `query_syntax/setops` | UNION/INTERSECT/EXCEPT |
| Subqueries | `query_syntax/subquery` | 子查询 |
| QUALIFY | `query_syntax/qualify` | 窗口后过滤（DuckDB 特色） |
| DISTINCT | `query_syntax/distinct` | 去重 |
| HAVING | `query_syntax/having` | 聚合后过滤 |
| OFFSET | `query_syntax/offset` | 偏移 |
| Aliases | `query_syntax/aliases` | 别名规则 |
| Comments | `query_syntax/comments` | 注释语法 |

---

## 3. Statements（30+ 个 DDL/DML）— 改数据

| 子文档 | URL | 说明 |
|---|---|---|
| SELECT | `statements/select` | SELECT 全语法 |
| INSERT | `statements/insert` | 含 ON CONFLICT |
| UPDATE | `statements/update` | 含 RETURNING |
| DELETE | `statements/delete` | 含 USING |
| MERGE INTO | `statements/merge_into` | 复杂 upsert |
| COPY | `statements/copy` | **极重要** |
| ATTACH / DETACH | `statements/attach` | 跨库查询 |
| CREATE TABLE | `statements/create_table` | 含 AS SELECT |
| DROP | `statements/drop` | DROP TABLE/VIEW/SCHEMA |
| ALTER TABLE | `statements/alter_table` | 改 schema |
| CREATE VIEW | `statements/create_view` | 视图 |
| CREATE INDEX | `statements/create_index` | 索引 |
| CREATE SCHEMA | `statements/create_schema` | 命名空间 |
| CREATE SEQUENCE | `statements/create_sequence` | 序列 |
| CREATE MACRO | `statements/create_macro` | 自定义函数 |
| CREATE TYPE | `statements/create_type` | 自定义类型 |
| EXPORT / IMPORT | `statements/export` | 整库导入导出 |
| LOAD / INSTALL | `statements/load_install` | 扩展 |
| PRAGMA | `statements/pragma` | 运行时配置 |
| SET / RESET | `statements/set` | 会话变量 |
| SUMMARIZE | `statements/summarize` | 列统计 |
| DESCRIBE | `statements/describe` | 表结构 |
| SHOW | `statements/show` | 列出表 |
| CHECKPOINT | `statements/checkpoint` | 强制刷盘 |
| TRANSACTION | `statements/transactions` | BEGIN/COMMIT/ROLLBACK |
| PREPARE / EXECUTE | `statements/prepared_statements` | 准备语句 |
| CALL | `statements/call` | 调存储过程/TVF |
| COMMENT ON | `statements/comment_on` | 注释元数据 |
| USE | `statements/use` | 切当前 DB |
| VACUUM | `statements/vacuum` | 清理 |

---

## 4. Data Types（20+ 个）— 类型系统

| 子文档 | URL | 说明 |
|---|---|---|
| Overview | `data_types/overview` | **总表** |
| Numeric | `data_types/numeric` | INTEGER/DECIMAL/... |
| Text | `data_types/text` | VARCHAR/BLOB |
| Date | `data_types/date` | DATE |
| Time | `data_types/time` | TIME |
| Timestamp | `data_types/timestamp` | TIMESTAMP/TIMESTAMPTZ |
| Interval | `data_types/interval` | INTERVAL |
| Boolean | `data_types/boolean` | BOOLEAN |
| Nulls | `data_types/nulls` | NULL 语义 |
| Numeric (detail) | `data_types/numeric` | 数值细节 |
| Decimal | `data_types/decimal` | DECIMAL 精度 |
| List | `data_types/list` | LIST/ARRAY |
| Struct | `data_types/struct` | STRUCT |
| Map | `data_types/map` | MAP |
| Union | `data_types/union` | UNION |
| Array | `data_types/array` | 定长 ARRAY |
| Enum | `data_types/enum` | ENUM |
| Variant | `data_types/variant` | VARIANT 半结构化 |
| JSON | `data_types/json` | JSON 类型 |
| Bitstring | `data_types/bitstring` | BIT |
| Blob | `data_types/blob` | 二进制 |
| Geometry | `data_types/geometry` | spatial 扩展 |
| Literal Types | `data_types/literal_types` | 类型字面量 |
| Typecasting | `data_types/typecasting` | 显式/隐式转换 |
| Timezones | `data_types/timezones` | 时区处理 |

---

## 5. Functions（30+ 个）— 函数库

| 子文档 | URL | 说明 |
|---|---|---|
| Overview | `functions/overview` | **总表** |
| Aggregates | `functions/aggregates` | SUM/COUNT/... |
| Window Functions | `functions/window_functions` | ROW_NUMBER/LAG/... |
| Date/Time | `functions/date` | 日期函数 |
| Date Format | `functions/dateformat` | strftime/strptime |
| Date Part | `functions/datepart` | extract / date_part |
| Timestamp | `functions/timestamp` | 时间戳 |
| Time | `functions/time` | TIME 函数 |
| Interval | `functions/interval` | INTERVAL 函数 |
| Text | `functions/text` | 字符串 |
| Pattern Matching | `functions/pattern_matching` | LIKE/ILIKE |
| Regular Expressions | `functions/regular_expressions` | POSIX 正则 |
| Numeric | `functions/numeric` | 数学 |
| Bitstring | `functions/bitstring` | 位操作 |
| Blob | `functions/blob` | 二进制 |
| List | `functions/list` | 列表 |
| Struct | `functions/struct` | 结构 |
| Map | `functions/map` | 映射 |
| Nested | `functions/nested` | 嵌套类型 |
| Array | `functions/array` | 数组 |
| Enum | `functions/enum` | 枚举 |
| Lambda | `functions/lambda` | lambda 表达式 |
| Utility | `functions/utility` | 工具函数 |
| Geometry | `functions/geometry` | spatial |

---

## 6. Expressions（10+ 个）— 表达式

| 子文档 | URL | 说明 |
|---|---|---|
| Overview | `expressions/overview` | 总览 |
| Case | `expressions/case` | CASE WHEN |
| Cast | `expressions/cast` | 类型转换 |
| Collations | `expressions/collations` | 排序规则 |
| Comparison | `expressions/comparison_operators` | 比较 |
| IN | `expressions/in` | IN 操作符 |
| Logical | `expressions/logical_operators` | AND/OR/NOT |
| Star | `expressions/star` | * 表达式 |
| Subqueries | `expressions/subqueries` | 子查询 |
| Try | `expressions/try` | TRY_CAST / TRY |

---

## 7. Dialect（6 个）— DuckDB 方言特色

| 子文档 | URL | 说明 |
|---|---|---|
| Overview | `dialect/overview` | 方言总览 |
| Friendly SQL | `dialect/friendly_sql` | **必读** —— 简写大全 |
| Indexing | `dialect/indexing` | ART + Zonemap 索引 |
| Keywords & Identifiers | `dialect/keywords_and_identifiers` | 关键字/标识符 |
| Order Preservation | `dialect/order_preservation` | 行序保留 |
| PostgreSQL Compatibility | `dialect/postgresql_compatibility` | PG 兼容性 |
| SQL Quirks | `dialect/sql_quirks` | DuckDB 怪癖 |

---

## 8. Meta — 元信息

| 子文档 | URL | 说明 |
|---|---|---|
| information_schema | `meta/information_schema` | SQL 标准 schema 元数据 |
| duckdb_* functions | `meta/duckdb_table_functions` | DuckDB 专属 TVF |

---

## 9. Constraints — 约束

- [Constraints](https://duckdb.org/docs/current/sql/constraints) — UNIQUE/CHECK/NOT NULL/FOREIGN KEY

---

## 10. Indexes — 索引

- [Indexes](https://duckdb.org/docs/current/sql/indexes) — ART + Zonemap 详解

---

## 11. Sample — 示例

- [Sample](https://duckdb.org/docs/current/sql/sample) — 完整示例

---

## 12. PEG Parser — 语法

- [PEG Parser](https://duckdb.org/docs/current/sql/peg_parser) — 完整 SQL 语法（极少用，agent 不必查）

---

## 抓新内容到本地

未来要"扩展学习"时，参考 `/tmp/fetch_duckdb_docs.py`（学习本 skill 时生成）：

```python
import urllib.request, concurrent.futures
from pathlib import Path

OUT = Path("/tmp/duckdb_docs_v2")
OUT.mkdir(exist_ok=True)

PAGES = [
    "query_syntax/qualify",       # 比如新加的 QUALIFY
    "query_syntax/setops",
    "statements/create_table",
    # ...
]

def fetch(page):
    url = f"https://duckdb.org/docs/current/sql/{page}"
    out = OUT / f"{page.replace('/', '_')}.html"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        out.write_bytes(urllib.request.urlopen(req, timeout=15).read())
        return f"OK  {page}"
    except Exception as e:
        return f"ERR {page}: {e}"

with concurrent.futures.ThreadPoolExecutor(max_workers=10) as ex:
    for r in ex.map(fetch, PAGES):
        print(r)
```

然后用 `/tmp/extract_duckdb_v3.py` 提取干净 markdown（同样在 `/tmp/`，本 skill 学习时生成）。

---

## 相关官方资源（**非 sql/ 但有用**）

- [API Python](https://duckdb.org/docs/current/api/python/overview) — Python client
- [Data Import/Export](https://duckdb.org/docs/current/data/overview) — 导入导出细节（CSV/Parquet/JSON/HTTPFS）
- [Connect](https://duckdb.org/docs/current/connect/overview) — 各种客户端（CLI/Python/R/Java/...）
- [Configuration](https://duckdb.org/docs/current/configuration/overview) — 启动参数
- [Extensions](https://duckdb.org/docs/current/extensions/overview) — 扩展列表（httpfs, spatial, fulltext, ...）
- [Performance Guide](https://duckdb.org/docs/current/guides/performance/overview) — 性能官方指南
- [SQL Glossary](https://duckdb.org/docs/current/sql/glossary) — 术语表

---

## 已知没收录的子页面（agent 真要用时再查）

- `connect/` 下各语言客户端
- `data/csv/`, `data/parquet/`, `data/json/` 详细导入
- `extensions/` 各扩展（httpfs, iceberg, delta, ...）
- `guides/` 各种实战指南
- `ops/` 运维
