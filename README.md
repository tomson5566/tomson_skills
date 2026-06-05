# tomson_skills

个人 AI Agent Skills 与数据库自动化工具集，涵盖 AI记忆管理、代码安全审计、SQL Server 远程运维等场景。

## 📂 子项目一览

| 目录 | 说明 |
|---|---|
| `code-security-audit/` | OpenClaw / Agent Skill 代码安全审计 — Semgrep + builtin SAST、Skill 包专项审计、SonarQube 集成 |
| `github-readme-creator/` | Mavis README 生成技能 — 自动检测项目结构，生成准确的 README.md |
| `memory-powermem-integration/` | AI 记忆持久化 — 自动同步到 PowerMem，语义搜索，定时备份 |
| `mssql-legacy/` | Linux 远程管理 SQL Server 2012 — TLS 1.0 兼容，`mssql` 包装命令，巡检 SQL |
| `mssql-tools18/` | Microsoft SQL Server 命令行工具 — sqlcmd、bcp，附带自定义 `mssql` 包装脚本 |
| `sqlremote/` | SQL Server 2012 远程运维工具包 — 连接测试、逐库串行备份、TLS 兼容配置 |

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
cd ~/.openclaw/skills/code-security-audit && npm install && npm test

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
- **敏感信息扫描** — 生成 README 前先检测是否存在泄露凭据，发现问题后提示修复
- **精准章节** — 标题、概述、功能特性、环境要求、安装方式、使用示例、配置说明、项目结构、贡献指南、开源协议
- **无占位符** — 所有内容均基于项目实际状态生成

### 使用方式

在 Mavis Agent 中触发 Skill，由 Agent 自动完成仓库检测和 README 生成。

---

## memory-powermem-integration

AI 记忆持久化工具，自动将会话记忆同步到 PowerMem（LLM 记忆数据库），支持语义搜索、标签分类和定时备份。

### 核心能力

- **按需检索** — AI 需用时主动查询 PowerMem 历史，无需轮询
- **自动同步** — 通过 Cron 定时记忆沉降（默认每日 01:00）
- **10维度标签** — 每条记忆自动标注时间、主题、关键词、项目、操作、状态、优先级等
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
| `MSSQL_USER` | 登录用户名（优先读取 `.env` 中的 `msuser`）|
| `MSSQL_PASSWORD` | 登录密码（优先读取 `.env` 中的 `mskey`）|
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
├── code-security-audit/              # OpenClaw/Agent Skill 安全审计
│   ├── SKILL.md
│   ├── README.md
│   ├── _meta.json
│   ├── openclaw.plugin.json
│   ├── package.json
│   ├── assets/
│   ├── references/
│   ├── scripts/
│   │   ├── semgrep_scan.js           # 本地 SAST 扫描入口
│   │   ├── audit_skill.py           # Skill 包专项审计
│   │   ├── analyze.js               # SonarQube issues 查询
│   │   ├── quality-gate.js          # SonarQube quality gate 查询
│   │   ├── report.js # SonarQube Markdown 报告
│   │   └── smoke_test.js           # 自检脚本
│   └── src/
├── github-readme-creator/             # README 生成技能
│   ├── SKILL.md
│   └── references/
├── memory-powermem-integration/      # AI 记忆 → PowerMem
│   ├── SKILL.md
│   ├── README_FLOW.md
│   ├── scripts/
│   │   ├── memory_sync.py            # Cron 记忆同步
│   │   ├── backup_powermem.sh       # 每周数据库备份
│   │   ├── tag_extractor.py
│   │   ├── read_memory.py
│   │   └── content_hash.py
│   └── references/
│       ├── pmem_cli_commands.md
│       ├── pmem_add_behavior.md
│       ├── pmem_troubleshooting.md
│       └── memory_schema.md
├── mssql-legacy/                     # SQL Server 2012 远程运维
│   ├── SKILL.md
│   ├── README.md
│   ├── LICENSE
│   ├── .gitignore
│   ├── conf/
│   ├── docs/
│   │   └── troubleshooting.md
│   ├── scripts/
│   │   ├── check-prereqs.sh         # 前提依赖检查
│   │   ├── mssql-wrapper.sh # mssql 包装脚本
│   │   └── sqlcmd-test.sh          # 连接测试
│   └── sql/
│       ├── 01_check_version.sql
│       ├── 02_check_databases.sql
│       ├── 03_check_log_size.sql
│       └── 04_check_disk_space.sql
├── mssql-tools18/                    # SQL Server CLI 工具
│   ├── bin/
│   │   ├── sqlcmd
│   │   ├── bcp
│   │   └── mssql                   # 本机包装脚本
│   ├── README.md
│   └── share/resources/
├── sqlremote/                         # SQL Server 2012 远程运维工具包
│   ├── README.md
│   ├── .env                          # 凭据（gitignore）
│   ├── conf/
│   │   └── openssl-sqlserver.cnf    # TLS 1.0 兼容配置
│   ├── data/
│   ├── logs/
│   ├── reports/                      # 巡检和备份报告
│   ├── scripts/
│   │   ├── remote_full_backup_133_14.sh
│   │   └── sqlcmd-test.sh
│   └── sql/
│       ├── 01_check_version.sql
│       └── 02_check_databases.sql
├── powermem-cli-usage-guide.md        # PowerMem CLI 完整使用指南
├── LICENSE
└── README.md
```

---

## 安全注意事项

- **不要提交** `.env`、凭据、私钥、`.pem`、`*.key`、`*.bak`、`*.trn`、`*.mdf`、`*.ldf`、`reports/`、`logs/`、`data/`
- `.env` 文件在 Linux 上必须设置 `chmod 600`
- README 和文档中使用 RFC 5737 文档地址（如 `192.0.2.0/24`），不暴露真实内网 IP
- 如有凭据被误提交，立即轮换密码，并用 `git filter-repo` 或 BFG 清理 Git 历史

---

## 开源协议

Apache License 2.0 — 见 [LICENSE](LICENSE)

---

> 部分文档由 AI 辅助生成