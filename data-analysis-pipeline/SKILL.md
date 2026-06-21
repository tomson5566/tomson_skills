---
name: data-analysis-pipeline
description: 一站式中端数据分析流水线 — 串联 ingestr(数据抽取)、DuckDB(内存分析)、Python 可视化(图表)和 BI 工具(PowerBI/Tableau) 形成 4 阶段闭环。Use this skill when the user wants to do data analysis, ETL pipelines, ingest CSV/Parquet/API data into DuckDB, write SQL on top, then visualize with Python (matplotlib/plotly/seaborn) or export to BI tools. 触发词:数据分析流水线、ETL 链路、ingestr、DuckDB 分析、Python 可视化、pandas to_sql、plotly 图表、PowerBI、Tableau、CSV 导入数据库、SQLite 中转、桑基图、关联分析、用户分群、销售分析、留存分析。
---

# data-analysis-pipeline — 中端数据分析链路

> **核心定位**:把零散的数据分析动作,**串成"取数 → 算 → 看"3 步闭环**。
> 不替代 ingestr(专门 ETL) / duckdb-sql(专门 SQL) / 任何可视化库(专门绘图),而是**告诉 agent 何时用哪个、怎么串**。

## 一句话定义

> **取数用 ingestr → 算用 DuckDB → 画用 Python (matplotlib/plotly/seaborn) → 发给 PowerBI/Tableau**。

任意一步被卡住,先跳到对应子 skill(本 skill 会标"去查 X skill 的 Y reference")。

## 对应架构图

```
源数据 (.csv / .xlsx / API / Postgres / SaaS)
        │
        │  [Step 1: 取数]     ingestr ingest --source-uri <src> --dest-uri duckdb:///path.db
        ▼
DuckDB (./analytics.duckdb)        ← 落盘为可复用分析数据源
        │
        │  [Step 2: 算]        Python: import duckdb; duckdb.sql("...").df()
        │                     或 SQL 直接读 .duckdb
        ▼
Pandas / Polars DataFrame          ← 干净、可视化友好的结构
        │
        │  [Step 3a: 快速看]   matplotlib / seaborn → PNG/PDF
        │  [Step 3b: 交互]     plotly → HTML
        │  [Step 3c: 发出去]   PowerBI / Tableau / Excel 报表
        ▼
图表 / 看板 / 报告
```

**SQLite 中转(图里的 "运算结果 → sqlite")** = **可选**,只在以下场景需要:
- 多个 DuckDB 文件要 JOIN(每个文件当一个 DB,SQLite 当聚合层)
- 数据要喂给老 BI 工具(SQLite 兼容性最广)
- 跨进程共享数据(BI 工具读 .db 文件,SQLite 是事实标准)

**90% 场景跳过 SQLite** — DuckDB 直接出 DataFrame 喂 Python 可视化。

## 4 阶段决策表(给 agent 用)

| 阶段 | 问自己 | 用什么 | 何时跳到子 skill |
|---|---|---|---|
| **1. 取数** | 数据在哪?格式?增量? | `ingestr ingest --source-uri <X> --dest-uri duckdb:///...` | `ingestr_etl` skill 的 `quickstart.md` / `uri_catalog.md` |
| **2. 算** | 算什么?一次性的?要 JOIN 多个源? | DuckDB SQL: `duckdb.sql("""...""")` 或 `con.execute(...)` | `duckdb-sql` skill 的 `01_sql_cheatsheet.md` / `08_project_patterns.md` |
| **3. 看** | 静态图够吗?要交互?要给老板? | (a) 静态:matplotlib/seaborn;(b) 交互:plotly;(c) BI:PowerBI/Tableau/Excel | (a/b) 本 skill `04_visualization.md`;(c) 同上 + 看 BI 工具文档 |
| **4. 自动化** | 每天/每周跑? | Bash + cron / Airflow / Dagster | `ingestr_etl` skill 的 `cdc.md`(增量) + `cron` skill |

**反模式**(agent 别犯的错):
- ❌ 全用 Python 读 CSV 后用 pandas 算 — 中等数据量(>1M 行)pandas 慢,DuckDB 1 行 SQL 顶 20 行 pandas
- ❌ DuckDB → CSV → pandas → matplotlib — 多此一举,`duckdb.sql(...).df()` 直接到 DataFrame
- ❌ ingestr 只想读 1 个 CSV — overhead 大,直接 `duckdb.read_csv("file.csv")`
- ❌ 散点图/直方图用 plotly — 重,纯展示用 matplotlib 更省

## 典型场景 → 链路模板

| 用户说 | 链路 |
|---|---|
| "把这 3 个 CSV 合到一起算 GMV" | ingestr 3 次 → DuckDB 1 个文件 → `SELECT sum(...)` → 折线图 |
| "算每个用户的 RFM 分群" | ingestr 1 次(订单表)→ DuckDB SQL 用窗口函数算 R/F/M → plotly 散点分群 |
| "API 数据每天同步,出日报" | ingestr `--incremental-key=updated_at` + cron + DuckDB + matplotlib → PNG 落盘 |
| "PowerBI 看板从哪读?" | ingestr `--dest-uri duckdb:///...` (PowerBI 通过 ODBC/JDBC 读 DuckDB) 或落 SQLite |
| "这俩数据源做关联分析" | ingestr 2 次 → 2 个 DuckDB → `ATTACH 'a.db' AS a; SELECT ... FROM a.t JOIN b.t` |

## 何时该跳到子 skill

| 你的痛点 | 跳到 |
|---|---|
| "ingestr 怎么连 Stripe/Snowflake/Notion?" | `ingestr_etl` skill → `references/uri_catalog.md` |
| "DuckDB 的 EXCLUDE / QUALIFY / PIVOT 怎么写?" | `duckdb-sql` skill → `references/01_sql_cheatsheet.md` |
| "DuckDB 怎么调 Python 库(线性回归/ML)?" | `duckdb-sql` skill → `references/06_python_integration.md` |
| "plotly dash 怎么做看板?" | 查 plotly 官方文档(本 skill 覆盖基础) |
| "我只有 Excel,没编程背景" | DuckDB CLI(`duckdb -c "SELECT ..."`) → CSV 导出 → Excel |

## references 索引

- `01_pipeline_overview.md` — 4 阶段链路全景 + 数据流向 + 决策树
- `02_ingestr_to_duckdb.md` — ingestr 实战:从 CSV/Postgres/API 写入 DuckDB + 增量 + 调度
- `03_duckdb_analysis.md` — DuckDB 分析模式:跨 DB JOIN / 窗口函数 / 性能调优 / Python 互转
- `04_visualization.md` — Python 可视化:matplotlib / seaborn / plotly / BI 工具对接 + 桑基/分群等高级图

## 跟其他 skill 的边界

| Skill | 边界 |
|---|---|
| `ingestr_etl` | **专门 ETL**:从任何源到任何目标。70+ 源 URI、15+ 目标、6 种增量策略。**本 skill 是它的"消费者"** |
| `duckdb-sql` | **专门 DuckDB SQL + Python 集成**。1017 行 SQL 速查 + 9 大实战 reference。**本 skill 是它的"前端应用"** |
| `understand-anything` | **代码理解**(不是数据分析)。不要搞混 |
| `deep-wiki` | **代码/文档问答**(不是数据分析) |
| `paddleocr-service` | **OCR 抽文字**(可作 ingestr 的源) |
| `pdf` / `xlsx` / `docx` / `pptx` | **文件读写**(可作 ingestr 的源或落点) |

## 维护点

- ingestr 还在 active 开发(本机装的是 v1.0.21),URI 格式可能变 — 查最新用 `ingestr ingest --help` 或 `ingestr_etl` skill 的 `uri_formats.md`
- DuckDB v1.x(本机已装 1.0+),Python 3.8+ 都支持;3.13 需 duckdb 1.3+
- 可视化库版本:matplotlib 3.8+ / seaborn 0.13+ / plotly 5.20+ 主流 API 稳