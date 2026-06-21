# DuckDB 项目级集成模式

**在 FastAPI / Jupyter / ETL / CLI 脚本里怎么用 DuckDB**。覆盖最常见 4 个场景。

---

## 模式 1：FastAPI 后端（**最常见**）

### 关键原则
- **单例连接**：启动时建 1 个 `con`，所有请求共享（**不要每个请求新建**）
- **只读权限**：线上库必须 `read_only=True`，防意外写入
- **连接注入**：用 FastAPI Depends 注入

### 最小骨架

```python
# app.py
import duckdb
from fastapi import FastAPI, Depends
from contextlib import asynccontextmanager

DB_PATH = "data/app.ddb"

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时：建单例连接
    app.state.con = duckdb.connect(DB_PATH, read_only=True)
    yield
    # 关闭时：释放
    app.state.con.close()

app = FastAPI(lifespan=lifespan)

def get_con():
    return app.state.con

@app.get("/users/{user_id}")
def get_user(user_id: int, con = Depends(get_con)):
    # 走索引（小数据集用 read_csv/直接查内存更快，大数据集靠 .ddb）
    return con.execute(
        "SELECT id, name, email FROM users WHERE id = ?",
        [user_id]
    ).df().to_dict(orient="records")[0] if con.execute(
        "SELECT count(*) FROM users WHERE id = ?", [user_id]
    ).fetchone()[0] else None

@app.get("/stats/orders")
def get_stats(con = Depends(get_con)):
    return con.execute("""
        SELECT
            date_trunc('day', created_at) AS day,
            count(*) AS orders,
            sum(amount) AS revenue
        FROM orders
        WHERE created_at >= current_date - INTERVAL '7 days'
        GROUP BY day
        ORDER BY day
    """).df().to_dict(orient="records")
```

### 关键陷阱
- **不要**用 `duckdb.connect()` 在请求处理函数里——会**锁文件** + 慢 100x
- **多 worker**（gunicorn -w 4）：每个 worker 一个 con，全局共享靠共享文件
- **热重载**：开发时 uvicorn --reload 会重复建 con，用 lifespan 管理
- **事务边界**：DuckDB 写是 statement-level auto-commit；显式事务用 `con.execute("BEGIN")` + `con.execute("COMMIT")`

---

## 模式 2：Jupyter / 数据分析

```python
import duckdb
import pandas as pd

# 1. 全局（最简，jupyter 友好）
df = duckdb.sql("""
    SELECT *
    FROM read_csv_auto('data/sales_2024*.csv')
    WHERE amount > 100
    ORDER BY date
""").df()

# 2. 注册 DataFrame
df_users = pd.read_parquet("users.parquet")
duckdb.register("users", df_users)         # 注册到全局
result = duckdb.sql("SELECT * FROM users WHERE age > 18").df()
duckdb.unregister("users")

# 3. 持久 .ddb（大数据/多 session 共享）
con = duckdb.connect("analysis.ddb")
con.execute("CREATE OR REPLACE TABLE clean AS SELECT * FROM read_csv_auto('raw/*.csv')")
# 在另一个 jupyter 进程里直接读：
con2 = duckdb.connect("analysis.ddb", read_only=True)
df2 = con2.execute("SELECT * FROM clean").df()
con2.close()
```

**Jupyter 最佳实践**：
- 探索性分析用全局 `duckdb.sql()`，免去连接管理
- 持久化结果用 `CREATE TABLE` 写入 `.ddb`，下次直接 `read_only` 查
- 用 `Magic` 命令更短：
  ```python
  %load_ext duckdb
  %duckdb SELECT 1+1
  ```

---

## 模式 3：ETL 脚本

```python
#!/usr/bin/env python3
"""ETL: 读 CSV → 清洗 → 写 Parquet"""
import duckdb
from pathlib import Path

SRC = Path("data/raw")
DST = Path("data/clean")
DST.mkdir(parents=True, exist_ok=True)

con = duckdb.connect(":memory:")

# 1. 读多个 CSV（glob），清洗
con.execute("""
    CREATE OR REPLACE TABLE clean AS
    SELECT
        id::INTEGER                       AS id,
        trim(name)                        AS name,
        lower(email)                      AS email,
        CAST(amount AS DECIMAL(10,2))     AS amount,
        CAST(date AS DATE)                AS date,
        current_timestamp                 AS processed_at
    FROM read_csv_auto('data/raw/orders_*.csv')
    WHERE id IS NOT NULL
""")

# 2. 验证
n = con.execute("SELECT count(*) FROM clean").fetchone()[0]
print(f"clean rows: {n}")
assert n > 0, "no rows!"

# 3. 写 Parquet（压缩 zstd）
con.execute(f"""
    COPY (SELECT * FROM clean WHERE date >= '2024-01-01')
    TO '{DST}/orders_2024.parquet' (FORMAT PARQUET, COMPRESSION zstd)
""")

# 4. 写 .ddb（供下游 API 读）
con.execute("ATTACH 'data/warehouse.ddb' AS wh")
con.execute("CREATE OR REPLACE TABLE wh.orders AS SELECT * FROM clean")

print("ETL done.")
con.close()
```

**优势**：
- 不用 pandas → 内存省 5-10x
- 不用 Dask/Spark → 代码少 90%
- CSV → Parquet 一次写完，下次秒读

---

## 模式 4：CLI 脚本（**数据分析**）

```python
#!/usr/bin/env python3
"""analyze.py: 给定 CSV 文件，输出统计"""
import sys
import duckdb
import argparse

def analyze(path: str, group_by: str = "category"):
    con = duckdb.connect(":memory:")
    df = con.execute(f"""
        SELECT
            {group_by},
            count(*)        AS n,
            avg(amount)     AS avg_amount,
            median(amount)  AS median_amount
        FROM read_csv_auto('{path}')
        GROUP BY ALL
        ORDER BY n DESC
        LIMIT 20
    """).df()
    print(df.to_string(index=False))

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("csv_path")
    p.add_argument("--group-by", default="category")
    args = p.parse_args()
    analyze(args.csv_path, args.group_by)
```

跑：
```bash
uv run python analyze.py data/sales.csv --group-by region
```

---

## 模式 5：跨库查询（多 .ddb 文件）

```python
import duckdb

# 场景：主库 + 月度归档库
con = duckdb.connect(":memory:")
con.execute("ATTACH 'data/main.ddb' AS main")
con.execute("ATTACH 'data/archive_2023.ddb' AS arch (READ_ONLY)")
con.execute("ATTACH 'data/archive_2022.ddb' AS arch2 (READ_ONLY)")

# 跨库 UNION ALL
df = con.execute("""
    SELECT 'main' AS src, * FROM main.orders
    UNION ALL
    SELECT 'arch' AS src, * FROM arch.orders
    UNION ALL
    SELECT 'arch2' AS src, * FROM arch2.orders
    WHERE created_at >= '2022-01-01'
""").df()
```

**应用**：日志按月分库、用户按地域分库——查询时挂上即可，**不复制数据**。

---

## 模式 6：多源联邦查询（不复制）

```python
# 同时查 CSV + Parquet + 远程 S3
con = duckdb.connect(":memory:")
con.execute("INSTALL httpfs")           # 装扩展
con.execute("LOAD httpfs")              # 加载

df = con.execute("""
    SELECT
        a.user_id,
        a.event,
        b.profile_data
    FROM read_csv_auto('local/events.csv') a
    JOIN read_parquet('s3://bucket/users/*.parquet') b
      ON a.user_id = b.user_id
    WHERE a.ts >= '2024-06-01'
""").df()
```

---

## 模式 7：内存数据库当 LRU 缓存

```python
import duckdb
from functools import lru_cache

# 假设大查询很慢，结果可缓存 5 分钟
@lru_cache(maxsize=128)
def cached_query(query: str, ts_bucket: int):
    con = duckdb.connect("data.ddb", read_only=True)
    try:
        return con.execute(query).df()
    finally:
        con.close()

# 用法
import time
bucket = int(time.time() // 300)  # 5 分钟桶
df = cached_query("SELECT * FROM huge_table LIMIT 1000", bucket)
```

---

## 配置管理（env vars 模式）

```python
# config.py
import os
import duckdb
from typing import Optional

class DuckDBConfig:
    def __init__(self):
        self.db_path = os.getenv("DUCKDB_PATH", "data/app.ddb")
        self.read_only = os.getenv("DUCKDB_READ_ONLY", "true").lower() == "true"
        self.memory_limit = os.getenv("DUCKDB_MEMORY", "2GB")
        self.threads = int(os.getenv("DUCKDB_THREADS", "4"))

    def connect(self) -> duckdb.DuckDBPyConnection:
        con = duckdb.connect(
            self.db_path,
            read_only=self.read_only,
            config={
                "memory_limit": self.memory_limit,
                "threads": self.threads,
            },
        )
        return con

# app.py
from config import DuckDBConfig
config = DuckDBConfig()
con = config.connect()
```

`.env`：
```
DUCKDB_PATH=data/app.ddb
DUCKDB_READ_ONLY=true
DUCKDB_MEMORY=4GB
DUCKDB_THREADS=4
```

---

## 测试模式

```python
# test_pipeline.py
import duckdb
import pytest

@pytest.fixture
def fresh_db(tmp_path):
    """每个 test 一个独立 .ddb 文件"""
    db_path = tmp_path / "test.ddb"
    con = duckdb.connect(str(db_path))
    con.execute("""
        CREATE TABLE events (
            id INTEGER PRIMARY KEY,
            name VARCHAR,
            amount DECIMAL(10,2)
        )
    """)
    yield con
    con.close()

def test_insert(fresh_db):
    fresh_db.execute("INSERT INTO events VALUES (1, 'a', 10.5)")
    result = fresh_db.execute("SELECT count(*) FROM events").fetchone()[0]
    assert result == 1

def test_csv_load(fresh_db, tmp_path):
    csv = tmp_path / "data.csv"
    csv.write_text("id,name,amount\n1,a,10.5\n2,b,20.0\n")
    fresh_db.execute(f"INSERT INTO events SELECT * FROM read_csv_auto('{csv}')")
    assert fresh_db.execute("SELECT count(*) FROM events").fetchone()[0] == 2
```

**关键**：用 `tmp_path` fixture 隔离 test，不污染真实数据。

---

## 项目结构模板

```
myproject/
├── pyproject.toml          # uv 装包
├── uv.lock                 # 锁文件（git）
├── .python-version         # Python 版本
├── README.md
├── src/
│   └── myproject/
│       ├── __init__.py
│       ├── config.py       # DuckDBConfig 类
│       ├── db.py           # connect + 初始化
│       ├── queries/        # SQL 模板
│       │   ├── users.sql
│       │   └── orders.sql
│       └── api/            # FastAPI 路由
│           └── users.py
├── data/                   # .ddb 文件 + CSV/Parquet
│   ├── raw/
│   ├── clean/
│   └── app.ddb
├── tests/
│   └── test_pipeline.py
└── scripts/
    └── etl.py              # ETL 脚本
```

**SQL 模板加载**：
```python
from pathlib import Path

QUERIES_DIR = Path(__file__).parent / "queries"

def load_query(name: str) -> str:
    return (QUERIES_DIR / f"{name}.sql").read_text()

# 用法
df = con.execute(load_query("users_by_id"), [42]).df()
```

---

## 监控与可观测性

```python
import time
import logging

logger = logging.getLogger(__name__)

def timed_query(con, sql, params=None):
    start = time.time()
    try:
        result = con.execute(sql, params or []).df()
        elapsed = time.time() - start
        logger.info(f"query ok rows={len(result)} time={elapsed:.3f}s sql={sql[:80]}")
        return result
    except Exception as e:
        logger.exception(f"query failed sql={sql[:80]}")
        raise
```

**DuckDB 内置统计**：
```sql
-- 看 query profile
EXPLAIN ANALYZE SELECT * FROM huge_table;
-- 返执行计划 + 实际耗时

-- 看表统计
SELECT * FROM duckdb_tables();
SELECT * FROM duckdb_columns() WHERE table_name = 'users';
```
