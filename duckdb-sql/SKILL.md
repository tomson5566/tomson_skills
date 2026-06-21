---
name: duckdb-sql
description: Generate DuckDB SQL queries and integrate DuckDB into Python projects. Use when user asks about DuckDB queries, data analysis, .ddb / .csv / .parquet files, wants help writing/editing/reviewing SQL, asks to use the duckdb skill, asks about DuckDB Python client / uv venv / FastAPI integration / Jupyter / ETL, references DuckDB SQL syntax, or wants to initialize a DuckDB environment in a project.
allowed-tools: Read, Grep, Glob, Bash
---

# DuckDB Skill — SQL + Python + uv

DuckDB 是嵌入式列存 OLAP 数据库。本 skill 让 agent **在项目里熟用 DuckDB**，覆盖：

- **写 SQL**：SELECT / JOIN / WINDOW / CTE / COPY / MERGE 等
- **Python 集成**：duckdb Python client + DataFrame/Arrow 互转
- **uv 独立环境**：标准部署 + 跨机器复现
- **项目级集成**：FastAPI / Jupyter / ETL / CLI 脚本模式
- **数据资产文档化**（向后兼容老 skill 行为）

## Reference 索引

按"百科速查 → 实战手册"组织：

| 文档 | 角色 | 何时读 |
|---|---|---|
| `01_sql_cheatsheet.md` | 百科 | 写 SQL 不知道语法（SELECT/JOIN/WINDOW/CTE/PIVOT/EXCLUDE/ASOF） |
| `02_dml_cheatsheet.md` | 百科 | 改数据（INSERT/UPDATE/DELETE/MERGE/COPY/ATTACH/EXPORT） |
| `03_functions_cheatsheet.md` | 百科 | 用函数（聚合/窗口/日期/字符串/正则/lambda） |
| `04_data_types_cheatsheet.md` | 百科 | 选类型（数值/字符串/时间/嵌套）+ 类型转换 |
| `05_dialect_cheatsheet.md` | 百科 | DuckDB 特有写法（friendly SQL / QUALIFY / EXCLUDE / PG 兼容） |
| `06_python_integration.md` | 手册 | 写 Python 调 duckdb（连接/df 互转/参数化/Arrow） |
| `07_uv_deployment.md` | 手册 | uv 建独立 venv（核心场景：`uv add duckdb`） |
| `08_project_patterns.md` | 手册 | 在 FastAPI/Jupyter/ETL/CLI 里怎么用 |
| `09_performance_tuning.md` | 手册 | 调优（索引/EXPLAIN/内存/并行/反模式） |
| `10_extension_links.md` | 百科 | 12 个官方分类 + 全部子文档链接（**扩展位**） |

**口诀**：要查"X 是什么"→ `01-05`；要查"怎么做"→ `06-09`；要"顺藤摸瓜"→ `10`。

---

## ⚠️ 重要规则（**先看**）

### 1. 数据资产检查（**向后兼容**老 skill 行为）

如果当前工作目录有 `duckdb_sql_assets/` 目录，**禁止直接读 .ddb / .csv / .parquet 文件**，先看资产文档：

```
duckdb_sql_assets/
├── tables_inventory.json    # 数据源清单
├── data_dictionary.md       # 业务字段说明
└── schema_*.sql             # 各表 schema
```

**资产存在时的行为**：
- 读 `tables_inventory.json` 知道有哪些表
- 读 `data_dictionary.md` 知道字段含义
- 读 `schema_*.sql` 验证列名
- **不跑** `duckdb -c ".schema"` 或类似命令
- 用户说 "refresh / update the assets" 才重扫

### 2. 默认生成 SQL，不执行

- 默认**只生成 + 展示** SQL 给用户审
- 显式说 "run this" / "execute it" 才跑
- 改数据 (INSERT/UPDATE/DELETE) **必须确认**，不擅自跑

### 3. uv 是部署默认（任务硬要求）

项目里要装 DuckDB，**默认用 uv**：
```bash
uv init && uv add duckdb
```

不要 `pip install duckdb`，不要用 conda（除非项目本来就是 conda）。**实测 11s 装完**，比 pip 快 10x。

### 4. Python 客户端优先

agent 调 DuckDB **用 `duckdb` Python 包**，不是 CLI 进程：
```python
import duckdb
df = duckdb.sql("SELECT 1+1").df()
```

不用 `subprocess.run(["duckdb", "-c", "..."])`（慢、解析 stdout 麻烦）。

---

## 典型使用场景

### 场景 1：写 SQL 不知道语法

→ 读 `references/01_sql_cheatsheet.md`（按章节定位）

### 场景 2：用户问"在项目里怎么用 DuckDB"

→ 先 `python3 -c "import duckdb; print(duckdb.__version__)"` 看是否装了
→ 没装就按 `references/07_uv_deployment.md` 第 1 段 `uv add duckdb`
→ 装好按 `references/06_python_integration.md` 写代码
→ FastAPI 集成看 `08_project_patterns.md` 模式 1

### 场景 3：ETL（CSV → Parquet）

```python
import duckdb
con = duckdb.connect(":memory:")
con.execute("""
    COPY (SELECT * FROM read_csv_auto('data/raw/*.csv') WHERE amount > 0)
    TO 'data/clean.parquet' (FORMAT PARQUET, COMPRESSION zstd)
""")
```
→ 完整模板在 `references/08_project_patterns.md` 模式 3

### 场景 4：项目有 DuckDB 数据资产

按"⚠️ 规则 1"流程，读 `duckdb_sql_assets/`，不直接 query 真实文件。

### 场景 5：query 慢，要调优

→ 跑 `EXPLAIN ANALYZE <query>` 找瓶颈
→ 读 `references/09_performance_tuning.md` 对应章节（索引/内存/反模式）

### 场景 6：要学新特性（QUALIFY / LATERAL / ...）

→ `references/10_extension_links.md` 列了所有子文档 URL
→ 用 `curl` 拉新内容到本地，按现有 reference 风格补充

---

## 核心速记（**10 件事**）

agent 不会查 reference 时也能写对 80% 的 DuckDB SQL：

```sql
-- 1. 装 duckdb：uv add duckdb（详细见 07）
-- 2. 简单查
SELECT col1, col2 FROM tbl WHERE col1 > 100 ORDER BY col1 LIMIT 10;
-- 3. 全列去某列
SELECT * EXCLUDE (pwd) FROM users;
-- 4. 窗口
SELECT *, ROW_NUMBER() OVER (PARTITION BY dept ORDER BY salary DESC) rn FROM emp;
-- 5. CTE
WITH cte AS (SELECT ...) SELECT * FROM cte;
-- 6. 读 CSV/Parquet
SELECT * FROM read_csv_auto('data/*.csv');
SELECT * FROM read_parquet('data/*.parquet');
-- 7. 写 Parquet
COPY (SELECT ...) TO 'out.parquet' (FORMAT PARQUET, COMPRESSION zstd);
-- 8. 跨库查询
ATTACH 'other.ddb' AS other (READ_ONLY);
SELECT * FROM other.users;
-- 9. upsert
INSERT INTO t VALUES (1, 'a') ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name;
-- 10. Python 拿 df
import duckdb; df = duckdb.sql("SELECT 1+1 AS x").df()
```

**DuckDB 跟 PG 的关键差异**（**别写错**）：
- `||` 是字符串拼接（同 PG）
- `::TYPE` 是类型转换简写（PG 也有）
- `EXCLUDE` / `REPLACE` / `COLUMNS(...)` / `GROUP BY ALL` / `QUALIFY` / `ASOF JOIN` / `SAMPLE` 是 DuckDB 扩展
- 字符串用单引号 `'x'`，标识符用双引号 `"x"`

---

## 完整查询示例

```python
# 0. 装包：uv add duckdb pandas
import duckdb
import pandas as pd

# 1. 创建 + 写入
con = duckdb.connect("data.ddb")
con.execute("""
    CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY,
        user_id INTEGER,
        event VARCHAR,
        amount DECIMAL(10,2),
        created_at TIMESTAMPTZ DEFAULT current_timestamp
    )
""")
con.executemany(
    "INSERT INTO events VALUES (?, ?, ?, ?, ?)",
    [(i, i % 100, f"evt_{i}", i * 1.5, None) for i in range(1000)]
)
con.close()

# 2. 查询
con = duckdb.connect("data.ddb", read_only=True)
df = con.execute("""
    SELECT
        event,
        count(*)         AS n,
        avg(amount)      AS avg_amount,
        median(amount)   AS median_amount
    FROM events
    WHERE created_at >= current_timestamp - INTERVAL '7 days'
    GROUP BY event
    ORDER BY n DESC
    LIMIT 10
""").df()

# 3. 注册 pandas DataFrame
external_df = pd.read_csv("other.csv")
con.register("ext", external_df)
df_joined = con.execute("""
    SELECT e.*, o.external_col
    FROM events e
    JOIN ext o ON e.user_id = o.id
""").df()
con.close()
```

---

## 与老 skill 行为兼容

老 skill（v0.1）有完整"数据资产文档化"流程（`duckdb_sql_assets/`、`tables_inventory.json`、`data_dictionary.md`）。**这个 skill 完整保留了**：

| 老功能 | 位置 | 说明 |
|---|---|---|
| 数据资产检查 | ⚠️ 规则 1 | 资产存在时优先读，不直接 query |
| 资产初始化 | （保留在 description + 行为） | 用户说 "initialize" 时走老流程 |
| Schema 提取 | （保留在 description） | 用 `duckdb -c ".schema"` 等 |
| Enum 检测 | （保留在 description） | 阈值：max_cardinality=20, max_ratio=0.05 |
| 两步查询（先 plan 后 SQL）| （保留） | 默认只展示不执行 |
| SQL 评审 | （保留） | review 章节在 description 提到 |

**新功能增量**（v0.2+）：
- Python 集成（reference 06）
- uv 部署模板（reference 07）
- 项目模式（reference 08）
- 性能调优（reference 09）
- 官方文档扩展入口（reference 10）

---

## 安装与卸载

### 装（推荐 uv）

```bash
# 项目里
uv add duckdb
# 全加：uv add duckdb pandas pyarrow

# 临时跑（不建项目）
uv run --with duckdb python script.py

# 全局 CLI（独立用途）
uv tool install duckdb-cli
```

### 卸载

```bash
uv remove duckdb
# 或：rm -rf .venv
```

---

## 已知限制

- **不支持 GPU**：本机无 CUDA wheel；CPU 跑（i7 也能 1.6s/图，已验证 paddleocr 同源）
- **不支持 PL/pgSQL**：写存储过程用 Python
- **不支持触发器 / 视图更新**
- **单写多读**：并发写有限制，OLTP 场景换 Postgres
- **大 OFFSET 慢**：用键值游标
- **窗口函数单线程**：1 亿行 window 会慢（30-120s）

→ 详情见 `references/09_performance_tuning.md`

---

## 相关资源

- **官方文档**：https://duckdb.org/docs/current/sql/
- **Python API**：https://duckdb.org/docs/current/api/python/overview
- **GitHub**：https://github.com/duckdb/duckdb
- **社区 Discord**：https://discord.duckdb.org/
- **DuckDB SQL 速查 PDF**：https://duckdb.org/cheat-sheet
