# 4 阶段链路全景

> 对应架构图:`源数据 → DuckDB → (可选 SQLite) → PowerBI/Tableau`
> 本 skill 把它扩成 **4 阶段**:取数 → 算 → 看 → 自动化

## 数据流向(完整版)

```
┌─────────────────────────────────────────────────────────┐
│  [Stage 1: 取数 INGEST]                                  │
│                                                          │
│  源:                                                     │
│  - 文件:  .csv  .xlsx  .parquet  .json  .avro            │
│  - 数据库: postgres  mysql  mssql  mongo                 │
│  - SaaS:  stripe  hubspot  salesforce  notion  jira      │
│  - 对象存储: s3  gcs  adls                              │
│                                                          │
│  → ingestr ingest --source-uri <X> --dest-uri duckdb:///  │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│  [Stage 2: 算 COMPUTE]                                   │
│                                                          │
│  DuckDB 模式:                                             │
│  - 内存连接: duckdb.sql("...") 全局(jupytER 友好)       │
│  - 文件连接: duckdb.connect("analytics.duckdb") 持久化    │
│  - 多 DB 关联: ATTACH 'other.db' AS other; SELECT ...   │
│                                                          │
│  工具:                                                    │
│  - 纯 SQL:  DuckDB 招牌语法(EXCLUDE/PIVOT/QUALIFY/ASOF)  │
│  - 注册 pandas/Arrow: con.register(df, 't')             │
│  - 反向回 DF: .df()  /  .pl()  /  .arrow()                │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│  [Stage 3: 看 VISUALIZE]                                 │
│                                                          │
│  3a. 静态图 (PNG/PDF, 报告)                              │
│      - matplotlib  基础,出版级                            │
│      - seaborn     统计图(分布/回归/分类)               │
│      - pandas .plot()  快速摸底                          │
│                                                          │
│  3b. 交互 (HTML, 看板)                                   │
│      - plotly      散点/折线/地图/桑基/Sunburst           │
│      - plotly dash 完整看板                              │
│      - streamlit   轻量 web app                          │
│                                                          │
│  3c. BI 工具 (企业分发)                                  │
│      - PowerBI:  通过 ODBC/JDBC 读 DuckDB                 │
│      - Tableau: 同上                                     │
│      - Excel:    DuckDB CLI 导出 CSV                     │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│  [Stage 4: 自动化 AUTOMATE]                              │
│                                                          │
│  一次性:  Python 脚本 / bash                              │
│  周期:    cron / Airflow / Dagster                       │
│  事件:    新文件到 S3 → Lambda/Cloud Run 触发 ingestr    │
│  增量:    ingestr --incremental-key=updated_at            │
└─────────────────────────────────────────────────────────┘
```

## 关键决策点(给 agent 的判断规则)

### 决策 1: 选 ingestr 还是直接读?

| 场景 | 推荐 |
|---|---|
| 单个 CSV < 100MB | **`duckdb.read_csv("file.csv")`** — 1 行搞定,不要 ingestr |
| 单个 CSV > 500MB 或多文件 | `ingestr ingest --source-uri file://...` |
| 数据库(SQL/列式) | `ingestr ingest --source-uri postgres://...` |
| SaaS API (Stripe/Notion) | **`ingestr`**(没有等价物) |
| 需要增量 / CDC | **`ingestr --incremental-key=...`** |

**口诀**:1 个文件 = DuckDB 直读,多个/复杂/增量 = ingestr。

### 决策 2: 选 SQL 还是 pandas?

| 场景 | 推荐 |
|---|---|
| 简单过滤/聚合/排序 | DuckDB SQL(快 5-20x) |
| 复杂机器学习(特征工程) | pandas/sklearn |
| 跨表 JOIN(>1M 行) | DuckDB SQL |
| 跟外部数据源 merge | DuckDB SQL(`JOIN` + `register(df)`) |
| 调试/探索 | DuckDB SQL + `.df()` 看头几行 |

**口诀**:能用 SQL 算就不要 pandas,性能差 1-2 个数量级。

### 决策 3: 静态图 vs 交互图 vs BI?

| 受众 | 场景 | 推荐 |
|---|---|---|
| 写报告/PDF | 静态出版级 | matplotlib |
| 摸底探索 | 快速 | pandas `.plot()` |
| 数据科学家内部 | 探索 | plotly 散点 + hover |
| 老板/业务 | 要点要细节 | plotly HTML,鼠标点开看 |
| 客户/外部 | 看板 | PowerBI / Tableau / Streamlit |
| 邮件附件 | 静态图 | matplotlib PNG |
| 海量数据(>1M 点) | 性能 | datashader / plotly webgl |

**口诀**:内部探索 plotly,正式交付 matplotlib,分发 BI/Excel。

### 决策 4: 要不要 SQLite 中转?

**架构图里 SQLite 在 DuckDB 和 PowerBI/Tableau 之间**,但 90% 场景不需要。判断:

| 场景 | 要 SQLite? |
|---|---|
| 单 DuckDB 文件,Python 可视化 | ❌ |
| PowerBI 读 DuckDB(直接 ODBC) | ❌ |
| 多个 DuckDB 文件要 JOIN | **✅**(SQLite 当聚合层) |
| PowerBI 不能直连 DuckDB,需要中转 | **✅** |
| 老 BI 工具(只认 SQLite/MySQL) | **✅** |
| 跨进程/跨网络共享数据 | **✅** |

**跨 DB JOIN 实战**(DuckDB 内置,不需要 SQLite):
```python
import duckdb
con = duckdb.connect("main.duckdb")
con.execute("ATTACH 'users.duckdb' AS users_db; ATTACH 'orders.duckdb' AS orders_db")
result = con.sql("""
    SELECT u.user_id, sum(o.amount) AS gmv
    FROM users_db.users u JOIN orders_db.orders o ON u.user_id = o.user_id
    GROUP BY u.user_id
""").df()
```

## 4 阶段时间预算(经验值)

| 阶段 | 占比 | 说明 |
|---|---|---|
| 取数 | 20% | 1 次跑通后 0 成本(增量) |
| 算 | 30% | SQL 调优+数据探索 |
| 看 | 30% | 选图、调样式、写注释 |
| 自动化 | 20% | 写 DAG / cron / webhook |

**反模式**:90% 时间在第 3 阶段(把图调漂亮)— 业务真要看的是**问题**不是图。

## 输出物管理(重要!)

每次跑完流水线产物:
```
/tmp/analysis_<date>/
├── analytics.duckdb           # DuckDB 数据源(可复用)
├── queries.sql                # 所有用过的 SQL(可审计)
├── notebooks.ipynb            # 探索记录
├── figures/                   # 图表
│   ├── gmv_trend.png
│   ├── user_segment.html
│   └── ...
└── report.md                  # 业务结论(给老板看)
```

**为什么要分开**:`.duckdb` 可以用无数次(改 SQL 重新算);`figures/` 是给人看的;`report.md` 是结论。混在一起下次找不回来。

## 跟图里 SQLite 中转的关系

架构图里画了 SQLite 中转。**现代栈完全跳过**:

```
源 → ingestr → DuckDB → Python (pandas/matplotlib)
                ↓
            (可选) PowerBI 直接 ODBC 读 DuckDB
```

**SQLite 中转仍然有用的 3 个场景**:

1. **PowerBI Desktop(免费版)直连 DuckDB 麻烦** → ingestr 写 SQLite
   ```bash
   ingestr ingest --source-uri duckdb:///analytics.duckdb --dest-uri sqlite:///report.db
   ```

2. **跨 DB 汇总**(你有 N 个 DuckDB 文件,要做全公司分析)
   ```python
   import duckdb
   con = duckdb.connect("aggregator.duckdb")
   for db_path in glob.glob("dept_*.duckdb"):
       con.execute(f"ATTACH '{db_path}' AS {Path(db_path).stem}")
   con.sql("SELECT * FROM dept_a.t UNION ALL SELECT * FROM dept_b.t ...")
   ```

3. **BI 工具只能连关系数据库** → ingestr 把 DuckDB 表"再导"一次到 SQLite/Postgres

**90% 情况下不画 SQLite 这一层**。架构图这么画是"兼容老 BI 工具"的稳妥设计,不是必须。