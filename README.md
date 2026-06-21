# tomson_skills

个人 AI Agent Skills 与工具集，涵盖 **AI 记忆管理**、**代码安全审计**、**数据分析链路**（ingestr ETL → DuckDB SQL → Python 可视化 → BI 看板）以及 **SQL Server 远程运维** 等场景。

> 9 个子项目按场景分类：**3 个数据工程 Skill 组成完整链路**（ingestr_etl → duckdb-sql → data-analysis-pipeline），**3 个 SQL Server 工具**（mssql-tools18 / mssql-legacy / sqlremote），其余 3 个为基础设施类 Skill（code-security-audit / memory-powermem-integration / github-readme-creator）。

## 📂 子项目一览

| 目录 | 分类 | 说明 |
|---|---|---|
| `ingestr_etl/` | 数据工程 | ingestr 单命令 ETL — 70+ 数据源 / 15+ 目标 / 6 种增量策略 / 17 references + 4 scripts |
| `duckdb-sql/` | 数据工程 | DuckDB SQL + Python 集成 + uv 部署 — 10 篇 reference（SQL/DML/函数/类型/Dialect/Python/uv/项目模式/调优/扩展） |
| `data-analysis-pipeline/` | 数据工程 | 中端数据分析链路编排 — 串联 ingestr → DuckDB → Python（matplotlib/plotly/seaborn）→ PowerBI/Tableau |
| `code-security-audit/` | 安全 | OpenClaw / Agent Skill 代码安全审计 — Semgrep + builtin SAST、Skill 包专项审计、SonarQube 集成 |
| `github-readme-creator/` | 工具 | Mavis README 生成技能 — 自动检测项目结构，生成准确的 README.md |
| `memory-powermem-integration/` | AI 记忆 | AI 记忆持久化 — 自动同步到 PowerMem，语义搜索，定时备份，10 维标签 |
| `mssql-legacy/` | SQL Server | Linux 远程管理 SQL Server 2012 — TLS 1.0 兼容，`mssql` 包装命令，巡检 SQL |
| `mssql-tools18/` | SQL Server | Microsoft SQL Server 命令行工具 — sqlcmd、bcp，附带自定义 `mssql` 包装脚本 |
| `sqlremote/` | SQL Server | SQL Server 2012 远程运维工具包 — 连接测试、逐库串行备份、TLS 兼容配置 |

### 根目录文件

| 文件 | 说明 |
|---|---|
| `LICENSE` | Apache License 2.0 |
| `.gitignore` | Python / Node 通用忽略规则 |
| `powermem-cli-usage-guide.md` | PowerMem CLI 完整使用指南（25 KB 详细手册） |
| `data-analysis-pipeline.tar.gz` | `data-analysis-pipeline/` 的离线打包（含 references） |
| `duckdb-sql.tar.gz` | `duckdb-sql/` 的离线打包（含 10 篇 references） |
| `ingestr_etl.tar.gz` | `ingestr_etl/` 的离线打包（含 17 篇 references + 4 scripts） |

> 三个 `.tar.gz` 是 `data-analysis-pipeline/`、`duckdb-sql/`、`ingestr_etl/` 的可分发生成包，用于在没有 Git 历史的场景下分发完整的 Skill。

---

## 🔗 数据工程链路（一图看懂）

`ingestr_etl` → `duckdb-sql` → `data-analysis-pipeline` 形成**「取数 → 算 → 看」3 步闭环**：

```
源数据（CSV/Parquet/API/Postgres/SaaS）
        │
        │  ingestr ingest --source-uri <src> --dest-uri duckdb:///...
        ▼
DuckDB（./analytics.duckdb）           ← ingestr_etl 负责
        │
        │  duckdb.sql("...").df() / con.execute(...)
        ▼
Pandas / Polars DataFrame              ← duckdb-sql 负责
        │
        │  matplotlib / seaborn（静态）/ plotly（交互）/ PowerBI / Tableau
        ▼
图表 / 看板 / 报告                     ← data-analysis-pipeline 负责
```

90% 的场景跳过 SQLite 中转；只在跨 DuckDB 文件 JOIN、喂老 BI 工具、跨进程共享时才用 SQLite 当聚合层。

---

## ingestr_etl

ingestr（bruin-data 出品）单命令 ETL CLI 的蒸馏 Skill：Go 实现、Apache Arrow + ADBC 内核、**70+ 数据源、15+ 数据目标**，支持 6 种增量策略（`replace` / `append` / `merge` / `delete+insert` / `scd2` / `truncate+insert`）。

### 核心能力

- **双视角** — 源码视角（理论：`internals.md` / `strategy_guide.md` / `schema_management.md`）+ 官方文档视角（实战：`migrations.md` / `uri_catalog.md` / `recipes.md`）
- **4 层结构** — 理论 / 实战 / 速查 / 帮助，**17 篇 references + 4 个 scripts**
- **数据源管理 CLI（v3.1+）** — `datasource` 子命令统一管理 MySQL `datahub.db_source` 表中的所有数据源（list / show / add / update / delete / search / count / status）
- **7 步标准工作流** — 解析请求 → 拼 URI → 校验（`validate_uri.py`）→ 生成命令（`plan_ingest.py`）→ 试跑 → 正式跑 → 排错
- **PII 脱敏** — `--mask "email:hash" / "ssn:partial:4" / "salary:round:1000"`
- **Web UI** — `ingestr server --port 8080`

### 快速上手

```bash
# 0. 确认 ingestr 已装（本机 v1.0.21）
ingestr --version

# 1. 5 分钟端到端 demo（SQLite ↔ SQLite）
bash ingestr_etl/scripts/first_run.sh

# 2. 一行命令：CSV → DuckDB
ingestr ingest \
  --source-uri 'csv://input.csv' \
  --source-table 'sample' \
  --dest-uri 'duckdb://output.duckdb' --yes

# 3. 增量 merge（按主键 upsert）
ingestr ingest ... \
  --incremental-strategy merge --primary-key id --incremental-key updated_at \
  --interval-start "2026-02-01T00:00:00Z" --interval-end "2026-03-01T00:00:00Z" --yes
```

### 数据源管理 CLI

```bash
# 列出所有数据源
datasource list
# 查看详情（密码默认隐藏）
datasource show MSSQL_HR_133_14 --show-password
# 新增源
datasource add --code MSSQL_HR_133_14 --name "HR 系统主库" --type sqlserver \
  --host 192.168.133.14 --port 1433 --database HR --username sa --password 'xxx'
```

> 默认连**本机 MySQL** `datahub.db_source`（Unix socket），可用 `DATAHUB_HOST` / `DATAHUB_PASSWORD` 等环境变量覆盖。

### References 索引

| 层 | 文档 | 用途 |
|---|---|---|
| 理论 | `internals.md` | ingestr 架构 + 源码导读 |
| 实战 | `quickstart.md` / `uri_formats.md` / `uri_catalog.md` / `strategy_guide.md` / `patterns.md` / `recipes.md` | 找 URI、复制粘贴命令、选增量策略 |
| 速查 | `flag_reference.md` / `INDEX.md` | 37 个 flag 速查、完整导航 |
| 帮助 | `troubleshooting.md` / `performance.md` / `best_practices.md` / `migrations.md` | 排错 / 调优 / 最佳实践 / v0→v1 迁移 |
| 数据源 | `data_sources.md` | 已注册数据源的人类可读快照 |
| 内部 | `schema_management.md` / `data_handling.md` / `cdc.md` / `internals.md` | Schema、CDC、底层数据处理 |

### 关键提醒

- ⚠️ `replace` 会**删整表**重建；`merge` 在 BigQuery/Snowflake 上 UPDATE 收费；`delete+insert` 会**删目标表里源表不存在的行**
- ⚠️ `append` / `merge` 必须显式配 `--interval-start/end`，否则全表扫
- ⚠️ 自动化必加 `--yes`（避免交互卡死）+ `--progress log`（避免 interactive 进度条卡输出）
- ⚠️ FSL 1.1 协议：不能用 ingestr 整出"竞品"商业 ingestion 服务

### 环境要求

- Linux x86_64（本机 `/home/tangzhiang/.local/bin/ingestr`）
- Python 3.10+（仅 `datasource` CLI 需要）
- ingestr v1.0.21+

---

## duckdb-sql

DuckDB（嵌入式列存 OLAP 数据库）的 SQL + Python + uv 综合 Skill，覆盖**写 SQL、Python 集成、uv 独立环境、项目级集成、性能调优、扩展入口**。

### 核心能力

- **10 篇 references** — 百科速查（01-05） + 实战手册（06-09） + 扩展入口（10）
- **数据资产检查**（向后兼容老 skill 行为）— 自动识别 `duckdb_sql_assets/` 目录，强制读 `tables_inventory.json` / `data_dictionary.md` / `schema_*.sql`
- **uv 部署默认** — `uv add duckdb`（实测 11s 装完，比 pip 快 10x）
- **Python 客户端优先** — `import duckdb; duckdb.sql("...").df()`，**不用 subprocess 调 CLI**
- **DuckDB 扩展** — `EXCLUDE` / `REPLACE` / `COLUMNS(...)` / `GROUP BY ALL` / `QUALIFY` / `ASOF JOIN` / `PIVOT` / `SAMPLE`

### Reference 索引

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

### 快速上手

```bash
# 项目里安装
uv init && uv add duckdb

# 临时跑（不建项目）
uv run --with duckdb python script.py
```

```python
import duckdb
import pandas as pd

# 1. 简单查
df = duckdb.sql("SELECT 1+1 AS x").df()

# 2. 跨库查询
con = duckdb.connect(":memory:")
con.execute("""
    COPY (SELECT * FROM read_csv_auto('data/raw/*.csv') WHERE amount > 0)
    TO 'data/clean.parquet' (FORMAT PARQUET, COMPRESSION zstd)
""")

# 3. 注册 pandas DataFrame
external_df = pd.read_csv("other.csv")
con.register("ext", external_df)
df_joined = con.execute("""
    SELECT e.*, o.external_col
    FROM events e
    JOIN ext o ON e.user_id = o.id
""").df()
```

### 已知限制

- **不支持 GPU**：本机无 CUDA wheel
- **不支持 PL/pgSQL**：写存储过程用 Python
- **不支持触发器 / 视图更新**
- **单写多读**：并发写有限制，OLTP 场景换 Postgres
- **大 OFFSET 慢**：用键值游标
- **窗口函数单线程**：1 亿行 window 会慢（30-120s）

### 环境要求

- Linux x86_64
- Python 3.8+（3.13 需 duckdb 1.3+）
- uv 0.11.8+
- duckdb-python 1.5.x / duckdb-cli v1.x

---

## data-analysis-pipeline

中端数据分析链路的**编排 Skill**：不替代 ingestr / duckdb-sql / 任何可视化库，而是**告诉 agent 何时用哪个、怎么串**。

> **一句话定义**：取数用 ingestr → 算用 DuckDB → 画用 Python（matplotlib/plotly/seaborn）→ 发给 PowerBI/Tableau。

### 核心能力

- **4 阶段决策表** — 给 agent 用的标准化决策（取数 / 算 / 看 / 自动化）
- **典型场景 → 链路模板** — 5 大常见场景（多 CSV 合并 / RFM 分群 / 日报同步 / PowerBI 看板 / 跨源关联分析）
- **何时跳到子 skill** — 精确路由到 `ingestr_etl` / `duckdb-sql` / plotly 官方文档
- **反模式清单** — 提醒 agent 别犯的 4 个错（全用 pandas / 多此一举转换 / 杀鸡用牛刀 ingestr / 散点图用 plotly）

### 架构图

```
源数据（CSV / Parquet / API / Postgres / SaaS）
        │
        │  [Step 1: 取数]    ingestr ingest --source-uri <X> --dest-uri duckdb:///...
        ▼
DuckDB（./analytics.duckdb）
        │
        │  [Step 2: 算]      Python: duckdb.sql("...").df()  或  con.execute(...)
        ▼
Pandas / Polars DataFrame
        │
        │  [Step 3a: 静态]  matplotlib / seaborn → PNG/PDF
        │  [Step 3b: 交互]  plotly → HTML
        │  [Step 3c: BI]    PowerBI / Tableau / Excel
        ▼
图表 / 看板 / 报告
```

### 4 阶段决策表

| 阶段 | 问自己 | 用什么 | 何时跳到子 skill |
|---|---|---|---|
| **1. 取数** | 数据在哪？格式？增量？ | `ingestr ingest --source-uri <X> --dest-uri duckdb:///...` | `ingestr_etl` → `quickstart.md` / `uri_catalog.md` |
| **2. 算** | 算什么？一次性的？要 JOIN 多个源？ | DuckDB SQL | `duckdb-sql` → `01_sql_cheatsheet.md` / `08_project_patterns.md` |
| **3. 看** | 静态图够？要交互？给老板？ | (a) 静态: matplotlib/seaborn；(b) 交互: plotly；(c) BI: PowerBI/Tableau | 本 skill → `04_visualization.md` |
| **4. 自动化** | 每天/每周跑？ | Bash + cron / Airflow / Dagster | `ingestr_etl` → `cdc.md`（增量） + cron |

### References 索引

| 文档 | 角色 | 内容 |
|---|---|---|
| `01_pipeline_overview.md` | 全景 | 4 阶段链路 + 数据流向 + 决策树 |
| `02_ingestr_to_duckdb.md` | 实战 | ingestr → DuckDB：CSV/Postgres/API 写入 + 增量 + 调度 |
| `03_duckdb_analysis.md` | 实战 | DuckDB 分析：跨 DB JOIN / 窗口函数 / 性能调优 / Python 互转 |
| `04_visualization.md` | 实战 | Python 可视化：matplotlib / seaborn / plotly / BI 工具 + 桑基/分群 |

### 典型场景 → 链路模板

| 用户说 | 链路 |
|---|---|
| "把这 3 个 CSV 合到一起算 GMV" | ingestr 3 次 → DuckDB 1 个文件 → `SELECT sum(...)` → 折线图 |
| "算每个用户的 RFM 分群" | ingestr 1 次（订单表）→ DuckDB SQL 窗口函数算 R/F/M → plotly 散点分群 |
| "API 数据每天同步，出日报" | ingestr `--incremental-key=updated_at` + cron + DuckDB + matplotlib → PNG 落盘 |
| "PowerBI 看板从哪读？" | ingestr `--dest-uri duckdb:///...`（PowerBI 通过 ODBC/JDBC 读 DuckDB）或落 SQLite |
| "这俩数据源做关联分析" | ingestr 2 次 → 2 个 DuckDB → `ATTACH 'a.db' AS a; SELECT ... FROM a.t JOIN b.t` |

### 维护点

- ingestr 还在 active 开发（本机 v1.0.21），URI 格式可能变 — 查最新用 `ingestr ingest --help` 或 `ingestr_etl` → `uri_formats.md`
- DuckDB v1.x（本机 1.0+），Python 3.8+ 都支持；3.13 需 duckdb 1.3+
- 可视化库版本：matplotlib 3.8+ / seaborn 0.13+ / plotly 5.20+ 主流 API 稳

---

## code-security-audit

面向 OpenClaw / Agent Skill / 普通代码仓库的代码安全审计技能。优先使用 Semgrep，Semgrep 不可用时自动回退内置轻量 builtin 规则；还支持 SonarQube 查询和 Skill 包专项审计。

### 核心能力

- **多引擎扫描** — `auto` 模式优先 Semgrep，失败后自动回退 builtin，无需人工干预
- **builtin 轻量规则** — 覆盖私钥块、硬编码凭据、MD5/SHA1 弱哈希、命令注入、SQL 拼接、关闭 TLS、Prompt Injection 等
- **Skill 包专项审计** — 检查 `SKILL.md` 规范性、危险命令、敏感信息、冗余运行时目录
- **SonarQube 集成** — 查询 quality gate、issues 和生成 Markdown 报告
- **CI 友好退出码** — 发现 BLOCKER/CRITICAL 返回 `2`，适合 CI/CD 阻断

### 快速上手

```bash
# 安装依赖
cd code-security-audit && npm install && npm test

# 本地代码扫描（auto 模式）
node scripts/semgrep_scan.js \
  --engine=auto \
  --path=/path/to/project \
  --severities=BLOCKER,CRITICAL,MAJOR \
  --exclude=node_modules,.venv \
  --output=security-report.md

# Skill 包专项审计
python3 scripts/audit_skill.py /path/to/skill \
  --engine=builtin \
  --print-issues

# SonarQube quality gate
export SONAR_HOST_URL=http://127.0.0.1:9000
export SONAR_TOKEN=your-token
node scripts/quality-gate.js --project=my-project
```

### 风险分级

| 等级 | 说明 | 建议 |
|---|---|---|
| 🔴 BLOCKER | 阻断级，如私钥块 | 立即处理 |
| 🟠 CRITICAL | 严重级，如硬编码凭据、命令注入 | 建议 CI 阻断 |
| 🟡 MAJOR | 重要级，如弱哈希、Prompt Injection 标记 | 迭代内修复 |
| 🟢 MINOR | 次要级，作为优化项处理 | — |
| 🔵 INFO | 提示信息 | — |

### 环境要求

- Node.js 18+ / Python 3.8+
- 可选：Semgrep（不装也能用 builtin 引擎）

---

## github-readme-creator

Mavis Agent Skill，自动生成精准的项目级 GitHub `README.md`。通过检测项目实际结构（`package.json`、`pyproject.toml`、`go.mod`、`Cargo.toml` 等），输出准确内容，而非泛泛的营销文案。

### 核心能力

- **项目检测** — 自动读取项目配置文件，了解项目类型、依赖、语言
- **敏感信息扫描** — 生成 README 前先检测是否存在泄露凭据（GitHub PAT、AWS、OpenAI、SSH 私钥等），发现问题后提示修复
- **精准章节** — 标题、概述、功能特性、环境要求、安装方式、使用示例、配置说明、项目结构、贡献指南、开源协议
- **无占位符** — 所有内容均基于项目实际状态生成
- **`.gitignore` 校验** — 自动检查是否覆盖 `.env*`、`*.key`、`*.pem`、credentials 等
- **示例用占位符** — 所有命令示例用 `YOUR_API_KEY` / `export GITHUB_TOKEN=...`，不用真实值

### 工作流

1. **确定项目源** — 本地路径 / GitHub URL / 描述
2. **采集或推断** — 项目名、类型、语言、安装方式、用法、特性、License、文档链接
3. **敏感信息扫描** — 排除 `.git/`、`node_modules/`、`dist/`、`.venv/` 后扫凭据模式；高危发现要求用户确认后再继续
4. **生成 README 章节** — 标题、徽章、概述、功能、要求、安装、用法、配置（用占位符）、项目结构、文档、贡献、Issue、License
5. **校验** — 无未替换占位符、命令与包管理器匹配、链接正确、License 匹配、Markdown 合法、无真实凭据泄露

### 使用方式

在 Mavis Agent 中触发 Skill，由 Agent 自动完成仓库检测、敏感信息扫描和 README 生成。

---

## memory-powermem-integration

AI 记忆持久化工具，自动将会话记忆同步到 PowerMem（LLM 记忆数据库），支持语义搜索、标签分类和定时备份。

### 核心能力

- **按需检索** — AI 需用时主动查询 PowerMem 历史，无需轮询
- **自动同步** — 通过 Cron 定时记忆沉降（默认每日 01:00）
- **10 维度标签** — 每条记忆自动标注时间、主题、关键词、项目、操作、状态、优先级等
- **幂等写入** — 内置相似度去重，无需手动计算内容哈希
- **自动数据库备份** — 每周日备份 PowerMem SQLite，保留 4 周
- **远程 Ollama Embedding** — 支持通过 `OLLAMA_EMBEDDING_BASE_URL` 连接远程 Embedding 服务
- **生产稳定** — 使用 `--no-infer` 跳过 LLM 推理，写入时间从 35–90s 降至 3–6s

### 快速上手

```bash
# 配置 Ollama Embedding（PowerMem 只认这两个变量名）
export OLLAMA_EMBEDDING_BASE_URL=http://target-host:11434
# 或
export ollama_base_url=http://target-host:11434

# 验证 PowerMem 连接
pmem config test

# 手动语义搜索
pmem memory search "deployment"

# 快速添加记忆（禁用推理）
pmem memory add "your memory summary" --metadata '{"tag1_time":"2025-05-24"}' --no-infer
```

### 触发词示例

- 用户主动回忆类："你还记得" / "你记不记得" / "回想一下" / "回忆回忆" / "之前我们" / "上次那个" / "那时候" / "查找记忆" / "搜一下记忆" / "查一下之前"
- 同步类："记忆检索" / "搜一下之前" / "查找相关记忆" / "记忆沉淀" / "周五同步" / "PowerMem sync"

### 环境要求

- Linux（CentOS / Ubuntu / Debian）
- Python 3.10+
- PowerMem CLI（`/root/miniconda3/bin/pmem`）
- 可选：Cron 定时任务

---

## mssql-legacy

Linux 远程管理旧版 SQL Server 的实战工具集，重点解决 **Ubuntu 22.04/24.04 + OpenSSL 3** 连接 **SQL Server 2012 RTM / TLS 1.0** 时的兼容性问题。

### 核心价值

- **兼容旧系统**：在 Ubuntu 24.04 / OpenSSL 3 环境下连接 SQL Server 2012 RTM
- **不污染系统安全策略**：不修改 `/etc/ssl/openssl.cnf`，仅对 `sqlcmd` 进程临时启用 TLS 1.0
- **一条命令管理 SQL Server**：`mssql` 包装命令自动加载凭据、OpenSSL 配置和 `-C` 证书信任参数
- **内置巡检 SQL**：版本检查、数据库恢复模式、日志大小、磁盘空间等常用 SQL 脚本
- **适合自动化运维**：支持 `mssql -Q`、`mssql -i`、日志输出、环境变量覆盖和脚本化调用

### 工作原理

复制一份专用 OpenSSL 配置 `openssl-sqlserver.cnf`，仅在执行 `sqlcmd` 时设置 `OPENSSL_CONF`，TLS 1.0 兼容性只对当前进程生效，系统其他程序仍保持现代 TLS 策略。

### 快速上手

```bash
# 查询版本
mssql -Q "SELECT @@VERSION"

# 列出所有数据库
mssql -Q "SELECT name, recovery_model_desc FROM sys.databases ORDER BY name"

# 执行 SQL 文件
mssql -i ~/workspaces/sqlremote/sql/02_check_databases.sql

# 覆盖默认连接
MSSQL_SERVER=192.0.2.10 mssql -Q "SELECT @@VERSION"
```

### 环境变量

| 变量 | 说明 |
|---|---|
| `MSSQL_SERVER` | SQL Server 地址 |
| `MSSQL_USER` | 登录用户名（优先读取 `.env` 中的 `msuser`） |
| `MSSQL_PASSWORD` | 登录密码（优先读取 `.env` 中的 `mskey`） |
| `SQLREMOTE_DIR` | 工作目录 |

### 一键检查

```bash
bash scripts/check-prereqs.sh
```

检查系统架构、mssql-tools18 安装状态、`.env` 权限、OpenSSL 兼容配置、`mssql` 命令可用性及 SQL Server 端口连通性。

### 适用场景

- Linux 服务器需要远程管理 SQL Server 2012
- `sqlcmd` 连接时报 TLS / SSL 协议错误
- 不能为了连接旧数据库而降低整台 Linux 机器的 OpenSSL 安全级别
- 自动化脚本中执行 SQL Server 巡检、备份、日志治理等任务

### 兼容性

| 组件 | 支持情况 |
|---|---|
| 操作系统 | Ubuntu 22.04 / 24.04 LTS，x86_64 / amd64 |
| SQL Server | 重点适配 SQL Server 2012 RTM；2012 SP4、2014+ 通常不再需要 TLS 1.0 隔离 |
| 客户端工具 | Microsoft ODBC Driver 18、mssql-tools18、sqlcmd、bcp |
| OpenSSL | OpenSSL 3.x 环境下实测可用 |
| 架构 | x86_64 / amd64；mssql-tools18 暂不支持 ARM64 |

### 文档导航

| 文档 | 内容 |
|---|---|
| `prerequisites.md` | 操作系统、软件包、OpenSSL、凭据、网络连通性要求 |
| `commands.md` | `mssql` 包装命令、`sqlcmd` 参数、`bcp` 使用示例 |
| `sql-recipes.md` | 健康检查、日志治理、备份、磁盘空间、性能排查 SQL |
| `migration.md` | 迁移到新机器的完整步骤、避坑清单和清理方法 |
| `docs/troubleshooting.md` | TLS、连接、权限、备份、性能、ODBC trace 故障排查 |
| `conf/README.md` | 专用 `openssl-sqlserver.cnf` 的生成和清理说明 |

---

## mssql-tools18

Microsoft SQL Server 命令行工具（sqlcmd、bcp）的 Linux 安装包，附带本机自定义的 `mssql` 包装脚本，用于在 Linux / OpenClaw 主机上远程连接和运维 SQL Server，尤其是兼容 SQL Server 2012 这类旧版本实例。

### 目录结构

```
/opt/mssql-tools18/
├── bin/
│   ├── bcp      # 批量导入/导出工具
│   ├── mssql    # 本机自定义 sqlcmd 包装脚本
│   └── sqlcmd   # 官方命令行查询工具
└── share/
    └── resources/en_US/ # 语言资源文件
```

### 工具说明

**sqlcmd**：SQL Server 官方命令行查询工具，适合执行 SQL 查询、批处理脚本、巡检和维护命令。

```bash
/opt/mssql-tools18/bin/sqlcmd -S YOUR_HOST -U YOUR_USER -P 'YOUR_PASSWORD' -C -Q "SELECT @@VERSION;"
```

**bcp**：批量复制工具，适合大批量导入/导出表数据或查询结果。

```bash
/opt/mssql-tools18/bin/bcp "SELECT name FROM sys.databases" queryout dbs.txt \
  -S YOUR_HOST -U YOUR_USER -P 'YOUR_PASSWORD' -C -c -t ','
```

**mssql**（本机包装脚本）：减少每次手写连接参数，并隔离旧版 SQL Server 所需的 OpenSSL 兼容配置。自动加载 `.env` 凭据和 `OPENSSL_CONF` TLS 兼容配置，默认添加 `-C` 信任证书。

```bash
/opt/mssql-tools18/bin/mssql -Q "SELECT @@VERSION;"
```

### 与 sqlremote 的关系

本目录只保存工具本体和包装命令；实际运维脚本、OpenSSL 兼容配置、SQL 文件、执行报告位于 `~/workspaces/sqlremote/`。

### 安全建议

- 不要在命令行历史中长期保留 `-P '真实密码'`
- 优先通过受权限保护的 `.env` 或环境变量传递密码
- `.env` 权限设置为 `600`
- 不要把凭据提交到 Git

---

## sqlremote

轻量级 SQL Server 2012 远程运维工具包，从 Linux / OpenClaw 主机实现连接测试、基础巡检和逐库串行完整备份，不依赖 SQL Server Agent。

### 核心能力

- **SQL Server 2012 TLS 1.0 兼容**：通过专用 `OPENSSL_CONF` 仅在当前进程放宽 TLS 配置，避免污染系统全局 OpenSSL 策略
- **连接测试**：`scripts/sqlcmd-test.sh` 验证连通性和版本
- **基础巡检 SQL**：版本检查、数据库状态和恢复模式
- **远程逐库完整备份**：从本机发起 `BACKUP DATABASE`，备份文件写入 SQL Server 服务器本机路径
- **备份校验**：可选每个库备份后执行 `RESTORE VERIFYONLY WITH CHECKSUM`
- **串行执行**：逐库顺序备份，默认库间暂停，降低对生产 IO 的冲击
- **运行留痕**：备份清单和执行日志统一写入 `reports/`

### 快速上手

```bash
# 配置凭据（不要提交到 Git）
cat > ~/workspaces/sqlremote/.env <<'EOF'
msuser=YOUR_SQL_LOGIN
mskey=YOUR_SQL_PASSWORD
EOF
chmod 600 ~/workspaces/sqlremote/.env

# 测试连接
~/workspaces/sqlremote/scripts/sqlcmd-test.sh 192.0.2.10

# 查看数据库状态
mssql -Q "SELECT name, recovery_model_desc, state_desc FROM sys.databases ORDER BY name;"

# 远程逐库完整备份
~/workspaces/sqlremote/scripts/remote_full_backup_133_14.sh
```

### 常用环境变量

| 变量 | 默认值 | 说明 |
|---|---:|---|
| `ROOT_BACKUP_PATH` | `D:\backup` | SQL Server 服务器本机看到的备份根路径 |
| `VERIFY_BACKUP` | `1` | 备份后执行 `RESTORE VERIFYONLY` |
| `INCLUDE_SYSTEM_DB` | `1` | 包含 `master/model/msdb` |
| `SLEEP_SECONDS` | `3` | 每个库之间暂停秒数 |
| `USE_DATE_SUBDIR` | `1` | `1` 使用 `D:\backup\yyyyMMdd`，`0` 直接使用根目录 |
| `CREATE_BACKUP_DIR` | `1` | `1` 尝试通过 `xp_cmdshell` 建目录 |

### 注意事项

- 备份路径是 SQL Server 服务器上的路径，不是 Linux 本机路径
- 执行前确认目标目录已存在且 SQL Server 服务账号有写权限
- 生产环境通常禁用 `xp_cmdshell`，建议提前在 Windows 服务器上创建备份目录

### 运行要求

- Linux / OpenClaw 主机，Bash 4+
- `/opt/mssql-tools18/bin/sqlcmd` 或 `$HOME/.local/bin/mssql`
- 目标 SQL Server 账号具备相应权限

---

## 项目结构

```
tomson_skills/
├── ingestr_etl/                         # ingestr 单命令 ETL（v3 — 17 refs + 4 scripts）
│   ├── SKILL.md
│   ├── README.md
│   ├── metadata.json
│   ├── scripts/
│   │   ├── datasource.py                # 数据源管理 CLI（v3.1+）
│   │   ├── first_run.sh                 # 5 分钟端到端 demo
│   │   ├── ingestr.sh                   # 本机 wrapper
│   │   ├── plan_ingest.py               # 命令生成器
│   │   └── validate_uri.py              # URI 校验器
│   └── references/
│       ├── INDEX.md                     # 完整导航
│       ├── quickstart.md
│       ├── uri_formats.md
│       ├── uri_catalog.md               # 70 源详细
│       ├── data_sources.md              # 已注册源快照
│       ├── strategy_guide.md
│       ├── patterns.md
│       ├── recipes.md                   # 5 大典型场景
│       ├── flag_reference.md            # 37 flag 速查
│       ├── schema_management.md
│       ├── data_handling.md
│       ├── cdc.md                       # 增量 / CDC
│       ├── internals.md                 # 架构 + 源码
│       ├── performance.md
│       ├── best_practices.md
│       ├── troubleshooting.md
│       └── migrations.md                # v0→v1 迁移
│
├── duckdb-sql/                          # DuckDB SQL + Python + uv（v0.2.0）
│   ├── SKILL.md
│   ├── metadata.json
│   └── references/
│       ├── 01_sql_cheatsheet.md         # SELECT/JOIN/WINDOW/CTE
│       ├── 02_dml_cheatsheet.md         # INSERT/UPDATE/DELETE/MERGE
│       ├── 03_functions_cheatsheet.md   # 聚合/窗口/日期/字符串
│       ├── 04_data_types_cheatsheet.md  # 类型 + 转换
│       ├── 05_dialect_cheatsheet.md     # DuckDB 特有写法
│       ├── 06_python_integration.md     # duckdb Python client
│       ├── 07_uv_deployment.md          # uv venv 部署
│       ├── 08_project_patterns.md       # FastAPI/Jupyter/ETL/CLI
│       ├── 09_performance_tuning.md     # 调优
│       └── 10_extension_links.md        # 官方扩展入口
│
├── data-analysis-pipeline/              # 数据分析链路编排
│   ├── SKILL.md
│   └── references/
│       ├── 01_pipeline_overview.md      # 4 阶段全景
│       ├── 02_ingestr_to_duckdb.md      # ingestr → DuckDB
│       ├── 03_duckdb_analysis.md        # DuckDB 分析
│       └── 04_visualization.md          # matplotlib/plotly/seaborn/BI
│
├── code-security-audit/                 # OpenClaw/Agent Skill 安全审计
│   ├── SKILL.md
│   ├── README.md
│   ├── _meta.json
│   ├── openclaw.plugin.json
│   ├── package.json
│   ├── CHANGELOG.md
│   ├── CONTRIBUTING.md
│   ├── assets/
│   ├── references/
│   │   ├── vulnerability_rules.md
│   │   ├── report_template.md
│   │   └── examples/
│   ├── scripts/
│   │   ├── semgrep_scan.js              # 本地 SAST 扫描入口
│   │   ├── audit_skill.py               # Skill 包专项审计
│   │   ├── analyze.js                   # SonarQube issues 查询
│   │   ├── quality-gate.js              # SonarQube quality gate
│   │   ├── report.js                    # SonarQube Markdown 报告
│   │   ├── review_filter.py
│   │   ├── dep_audit.sh
│   │   ├── dep_audit_java.sh
│   │   └── smoke_test.js
│   └── src/
│       ├── index.js
│       ├── analyzer.js
│       ├── api.js
│       ├── reporter.js
│       └── rules.js
│
├── github-readme-creator/               # README 生成技能
│   ├── SKILL.md
│   └── references/
│       ├── readme-template.md
│       └── secret-scan.md
│
├── memory-powermem-integration/         # AI 记忆 → PowerMem
│   ├── SKILL.md
│   ├── README.md
│   ├── README_FLOW.md
│   ├── scripts/
│   │   ├── memory_sync.py               # Cron 记忆同步
│   │   ├── backup_powermem.sh           # 每周数据库备份
│   │   ├── tag_extractor.py
│   │   ├── read_memory.py
│   │   └── content_hash.py
│   └── references/
│       ├── pmem_cli_commands.md
│       ├── pmem_add_behavior.md
│       ├── pmem_troubleshooting.md
│       ├── memory_schema.md
│       └── backup_powermem.sh
│
├── mssql-legacy/                        # SQL Server 2012 远程运维
│   ├── SKILL.md
│   ├── README.md
│   ├── LICENSE
│   ├── .gitignore
│   ├── conf/
│   │   └── README.md
│   ├── docs/
│   │   ├── prerequisites.md
│   │   ├── commands.md
│   │   ├── sql-recipes.md
│   │   ├── migration.md
│   │   └── troubleshooting.md
│   ├── scripts/
│   │   ├── check-prereqs.sh             # 前提依赖检查
│   │   ├── mssql-wrapper.sh             # mssql 包装脚本
│   │   └── sqlcmd-test.sh               # 连接测试
│   └── sql/
│       ├── 01_check_version.sql
│       ├── 02_check_databases.sql
│       ├── 03_check_log_size.sql
│       └── 04_check_disk_space.sql
│
├── mssql-tools18/                       # SQL Server CLI 工具
│   ├── README.md
│   ├── bin/
│   │   ├── sqlcmd                       # 官方 sqlcmd（v18.6）
│   │   ├── bcp                          # 官方 bcp
│   │   └── mssql                        # 本机包装脚本
│   └── share/resources/
│       └── en_US/                       # 语言资源（BatchParserGrammar, *.rll）
│
├── sqlremote/                           # SQL Server 2012 远程运维工具包
│   ├── README.md
│   ├── .env                             # 凭据（gitignore）
│   ├── .gitignore
│   ├── conf/
│   │   └── openssl-sqlserver.cnf        # TLS 1.0 兼容配置
│   ├── data/                            # 本地数据
│   ├── logs/                            # 运行日志
│   ├── reports/                         # 巡检和备份报告
│   ├── scripts/
│   │   ├── remote_full_backup_133_14.sh
│   │   └── sqlcmd-test.sh
│   └── sql/
│       ├── 01_check_version.sql
│       └── 02_check_databases.sql
│
├── data-analysis-pipeline.tar.gz        # 离线分发包（含 references）
├── duckdb-sql.tar.gz                    # 离线分发包（含 10 篇 references）
├── ingestr_etl.tar.gz                   # 离线分发包（含 17 refs + 4 scripts）
├── powermem-cli-usage-guide.md          # PowerMem CLI 完整使用指南
├── LICENSE                              # Apache 2.0
├── .gitignore                           # Python / Node 通用忽略
└── README.md                            # 本文件
```

---

## 安全注意事项

- **不要提交** `.env`、凭据、私钥、`.pem`、`*.key`、`*.bak`、`*.trn`、`*.mdf`、`*.ldf`、`reports/`、`logs/`、`data/`
- `.env` 文件在 Linux 上必须设置 `chmod 600`
- README 和文档中使用 RFC 5737 文档地址（如 `192.0.2.0/24`），不暴露真实内网 IP
- 如有凭据被误提交，立即轮换密码，并用 `git filter-repo` 或 BFG 清理 Git 历史

---

## 数据工程 Skill 之间的边界

为避免重复和误用，3 个数据工程 Skill 严格分工：

| Skill | 边界 |
|---|---|
| `ingestr_etl` | **专门 ETL**：从任何源到任何目标。70+ 源 URI、15+ 目标、6 种增量策略。**`data-analysis-pipeline` 是它的"消费者"** |
| `duckdb-sql` | **专门 DuckDB SQL + Python 集成**。10 篇 reference 覆盖 SQL 速查 → Python 集成 → uv 部署 → 性能调优。**`data-analysis-pipeline` 是它的"前端应用"** |
| `data-analysis-pipeline` | **专门链路编排**：不重复上面两个 Skill 的内容，只告诉 agent 何时用哪个、怎么串 |
| `github-readme-creator` | **专门 README 生成**：项目检测 + 敏感信息扫描 + 精准章节 |
| `memory-powermem-integration` | **专门 AI 记忆持久化**：PowerMem 同步 + 语义搜索 |
| `code-security-audit` | **专门代码安全审计**：Semgrep + builtin + SonarQube + Skill 包审计 |

---

## 开源协议

Apache License 2.0 — 见 [LICENSE](LICENSE)

---

> 部分文档由 AI 辅助生成
