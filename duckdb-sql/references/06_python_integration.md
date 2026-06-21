# DuckDB Python 集成

**任务关键**。本节覆盖：装包 → 内存/文件连接 → DataFrame/Arrow 互转 → 真实项目模式。

完整官方 API：https://duckdb.org/docs/current/api/python/overview

---

## 装包（uv）

```bash
# 单独 duckdb（CPU 即可，无 GPU wheel）
uv add duckdb

# 加 pandas 互转
uv add duckdb pandas

# 加 pyarrow 互转（大数据/列式推荐）
uv add duckdb pandas pyarrow

# CLI 装（命令行工具）
# macOS:  brew install duckdb
# Linux:  curl -fsSL https://install.duckdb.org | sh
```

**版本兼容**：
- `duckdb` Python 包 v1.x 配套 CLI v1.x
- Python 3.8+ 支持
- **不要**装 `duckdb-engine`（SQLAlchemy 适配器）—— 性能损耗大，直接用原生 client

---

## 最小示例

```python
import duckdb

# 1. 全局临时连接（最简单，脚本/REPL 友好）
result = duckdb.sql("SELECT 1 AS a, 'hello' AS b").df()
print(result)
#    a      b
# 0  1  hello

# 2. 显式连接（生产代码用这个）
con = duckdb.connect(":memory:")           # 内存数据库
con = duckdb.connect("path/to/file.ddb")    # 持久化文件
con = duckdb.connect("file.ddb", read_only=True)  # 只读

# 查
rows = con.execute("SELECT 1, 2").fetchall()      # → list[tuple]
df   = con.execute("SELECT 1, 2").df()             # → pandas.DataFrame
arrow = con.execute("SELECT 1, 2").arrow()         # → pyarrow.Table（需装 pyarrow）

# 取单值
val = con.execute("SELECT count(*) FROM t").fetchone()[0]
```

---

## 4 种拿数据方式

```python
import duckdb
con = duckdb.connect(":memory:")

# 1. fetchall() - 全部行 → list[tuple]
rows = con.execute("SELECT id, name FROM t").fetchall()
# [(1, 'alice'), (2, 'bob')]

# 2. fetchone() - 一行 → tuple | None
row = con.execute("SELECT id, name FROM t ORDER BY id LIMIT 1").fetchone()
# (1, 'alice')

# 3. df() - DataFrame（**最常用**）
df = con.execute("SELECT id, name FROM t").df()
#    id   name
# 0   1  alice
# 1   2   bob

# 4. arrow() - Arrow Table（大数据 / 列式下游）
table = con.execute("SELECT id, name FROM t").arrow()
```

**`.df()` vs `.arrow()`**：
- `.df()` 适合小-中等数据（< 1M 行），pandas 操作丰富
- `.arrow()` 适合大数据、列式下游（Polars、DuckDB 自己再读）、零拷贝
- **大批量 > 100MB 用 Arrow**（pandas 拷贝 4 次）

---

## DataFrame / Arrow 互转

```python
import duckdb
import pandas as pd
import pyarrow as pa

con = duckdb.connect(":memory:")

# pandas → DuckDB（注册为视图，**不复制**，用 DuckDB 引擎查）
df = pd.DataFrame({"id": [1, 2, 3], "name": ["a", "b", "c"]})
con.register("users_view", df)               # 注册为虚拟表
result = con.execute("SELECT * FROM users_view WHERE id > 1").df()

# 取消注册（释放引用）
con.unregister("users_view")

# DuckDB → pandas
df = con.execute("SELECT 1 AS a, 'x' AS b").df()

# Arrow → DuckDB
table = pa.table({"id": [1, 2], "v": ["x", "y"]})
con.register("arrow_view", table)
con.execute("SELECT * FROM arrow_view").df()

# DuckDB → Arrow
arrow_table = con.execute("SELECT 1 AS a, 2.5 AS b").arrow()
```

**注意**：`register()` 在 1.0+ 是**零拷贝**（pandas Arrow-backed / pyarrow 都是）；老 DataFrame（纯 pandas）会 copy 一次。

---

## 直接读 CSV / Parquet / JSON

DuckDB 不用 `pandas.read_csv()`，直接 SQL 读，**比 pandas 快 10-100x**：

```python
import duckdb
con = duckdb.connect(":memory:")

# CSV（auto-detect schema）
df = con.execute("SELECT * FROM 'data.csv'").df()
df = con.execute("SELECT * FROM read_csv_auto('data/*.csv')").df()

# Parquet
df = con.execute("SELECT * FROM 'data.parquet'").df()

# JSON / NDJSON
df = con.execute("SELECT * FROM 'data.json'").df()                      # 顶层数组
df = con.execute("SELECT * FROM 'data.ndjson'").df()                     # 每行一个 JSON

# 显式选项
df = con.execute("""
    SELECT * FROM read_csv('data.csv',
        header=true,
        delim='|',
        nullstr='NA',
        columns={'id': 'INTEGER', 'name': 'VARCHAR'},
        sample_size=10000
    )
""").df()
```

**关键优势**：
- 不用先 `pandas.read_csv()` 再传 DataFrame —— DuckDB 直接读
- 多文件 glob 一次查：`read_csv_auto('logs/2024-*/part-*.csv')`
- **不会 OOM**（流式处理，按需读）

---

## SQL 命令执行

### execute() vs sql()

```python
# execute(sql, [params]) - 命令式
con.execute("CREATE TABLE t (id INTEGER, name VARCHAR)")
con.execute("INSERT INTO t VALUES (?, ?)", [1, "alice"])   # 参数化
con.execute("INSERT INTO t VALUES ($id, $name)", {"id": 2, "name": "bob"})

# sql(sql) - 链式（**更优雅**，返 DuckDBPyRelation）
rel = con.sql("SELECT * FROM t WHERE id > 0")
df = rel.df()                  # 转 df
rel = rel.filter("id > 1")     # 链式筛选
rel = rel.project("id, name")  # 链式投影
```

### 参数化查询（**必须用**防 SQL 注入）

```python
# ❌ 错误：拼接字符串
user_id = "1; DROP TABLE users; --"
con.execute(f"SELECT * FROM users WHERE id = {user_id}")  # 注入!

# ✅ 正确：参数化
con.execute("SELECT * FROM users WHERE id = ?", [user_id])
con.execute("SELECT * FROM users WHERE id = $id", {"id": user_id})
```

### executemany（批量）

```python
con.executemany(
    "INSERT INTO t VALUES (?, ?)",
    [(1, "a"), (2, "b"), (3, "c")]
)
```

---

## 持久化 .ddb 文件

```python
# 写
con = duckdb.connect("data.ddb")
con.execute("CREATE TABLE users (id INTEGER, name VARCHAR)")
con.execute("INSERT INTO users VALUES (1, 'alice')")
con.close()

# 读（只读，避免锁）
con = duckdb.connect("data.ddb", read_only=True)
df = con.execute("SELECT * FROM users").df()
con.close()

# 同时挂多个库
con = duckdb.connect(":memory:")
con.execute("ATTACH 'data1.ddb' AS db1")
con.execute("ATTACH 'data2.ddb' AS db2 (READ_ONLY)")
df = con.execute("""
    SELECT * FROM db1.users u
    JOIN db2.orders o ON u.id = o.user_id
""").df()
```

**文件特点**：
- `.ddb` 文件 = 1 个或多个 table 的物理存储
- 单文件设计，便于备份/迁移
- 同一进程多连接 + 跨进程**共享文件**需要配置（默认悲观锁）

---

## 配置文件 & 连接选项

```python
con = duckdb.connect(":memory:", config={
    "memory_limit": "4GB",           # 内存上限
    "threads": 4,                    # 查询并行度
    "max_memory": "8GB",             # 同 memory_limit（alias）
    "default_order": "ASC",          # 默认排序
    "default_null_order": "NULLS LAST",
    "preserve_insertion_order": False,  # 默认 True，行插入顺序保留
    "temp_directory": "/tmp/duckdb", # 临时溢出目录（大数据查询时用）
})

# 运行时修改
con.execute("SET memory_limit = '2GB'")
con.execute("SET threads TO 4")          # 注意用 TO
con.execute("PRAGMA threads=4")          # 等价
```

---

## 错误处理

```python
import duckdb

try:
    con.execute("SELECT * FROM nonexistent")
except duckdb.CatalogException as e:
    print(f"table 不存在: {e}")
except duckdb.ParserException as e:
    print(f"SQL 语法错: {e}")
except duckdb.BinderException as e:
    print(f"绑定错（列名/类型不匹配）: {e}")
except duckdb.Error as e:                # 通用父类
    print(f"DuckDB 错: {e}")
```

**常见错误**：
- `CatalogException` — 表/视图不存在
- `ParserException` — SQL 语法错
- `BinderException` — 引用不存在的列、类型不匹配
- `IOException` — 文件读写失败
- `OutOfMemoryException` — 内存超限

---

## 性能提示

```python
# 1. 准备语句（多次执行同 SQL）
stmt = con.prepare("INSERT INTO t VALUES (?, ?)")
for i in range(10000):
    stmt.execute(i, f"row_{i}")
stmt.close()

# 2. 批量 insert 比循环快 100x
con.execute("BEGIN")
con.executemany("INSERT INTO t VALUES (?, ?)", big_list)
con.execute("COMMIT")

# 3. 导出大数据用 Arrow，零拷贝
arrow = con.execute("SELECT * FROM huge_table").arrow()
# 比 .df() 省内存 10x

# 4. 用 .df(pl=True) 拿 Polars（duckdb 1.0+）
import polars as pl
df_pl = con.execute("SELECT * FROM t").pl()
```

---

## 关闭连接

```python
con.close()  # 显式关，释放文件锁

# 或用 context manager（**不直接支持**，但可这样模拟）
class DuckDBSession:
    def __init__(self, path=":memory:"):
        self.con = duckdb.connect(path)
    def __enter__(self):
        return self.con
    def __exit__(self, *args):
        self.con.close()

with DuckDBSession("data.ddb") as con:
    df = con.execute("SELECT * FROM users").df()
```

---

## 实战项目模式（详见 08）

| 场景 | 模式 | 关键点 |
|---|---|---|
| 数据分析（Jupyter） | `duckdb.sql(...)` 全局 | 不显式连接，DF 直接拿来用 |
| ETL 脚本 | 显式 `con = connect(...)` | 写文件 + close |
| FastAPI 后端 | 启动时建连接，依赖注入 | **不要每个请求新建连接** |
| 读 Parquet 报表 | `read_parquet('glob/*.parquet')` | 不用先 import pandas |
| 数据共享 | ATTACH + 跨库 JOIN | 不复制数据 |
| 备份 | `EXPORT DATABASE` | 整库导出 SQL+文件 |
