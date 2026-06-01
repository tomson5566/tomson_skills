---
name: "mssql-legacy"
description: "Linux 远程管理 SQL Server 2012 RTM 的完整技能。包含客户端安装、OPENSSL_CONF 隔离方案、mssql 封装命令、常用运维 SQL 和自动化脚本。当用户提到 SQL Server 远程管理、sqlcmd、mssql 命令、SQL 2012 连接、TLS 兼容、数据库备份触发时使用此技能。"
agent_created: true
---

# mssql-legacy — Linux 远程管理 SQL Server 2012 RTM

> 📌 本技能解决的核心问题：在 Ubuntu 24.04 (OpenSSL 3) 上远程连接 **仅支持 TLS 1.0** 的 SQL Server 2012 RTM，并通过 `OPENSSL_CONF` 隔离方案避免污染系统全局 TLS 安全策略。

## 快速开始

```bash
# 查询版本
mssql -Q "SELECT @@VERSION"

# 列出所有数据库及恢复模式
mssql -Q "SELECT name, recovery_model_desc FROM sys.databases ORDER BY name"

# 执行 SQL 文件
mssql -i ~/workspaces/sqlremote/sql/02_check_databases.sql

# 切换默认数据库
mssql -d HR -Q "SELECT TOP 10 * FROM sys.tables"
```

## 环境要求

详见 **[prerequisites.md](prerequisites.md)**，包含操作系统、软件包、OpenSSL 配置等完整依赖清单和安装步骤。

## 核心组件

| 组件 | 路径 | 用途 |
|---|---|---|
| `mssql` 包装命令 | `~/.local/bin/mssql` | 自动加载凭据 + OPENSSL_CONF，一行命令即连 |
| 专用 OpenSSL 配置 | `~/workspaces/sqlremote/conf/openssl-sqlserver.cnf` | 仅 sqlcmd 进程允许 TLS 1.0 |
| 凭据文件 | `~/workspaces/sqlremote/.env` | msuser + mskey（chmod 600）|
| sqlcmd 二进制 | `/opt/mssql-tools18/bin/sqlcmd` | v18.6.0002.1 Linux |
| bcp 二进制 | `/opt/mssql-tools18/bin/bcp` | 批量导入导出 |

## 目录结构

```text
~/workspaces/sqlremote/
├── .env                          # 凭据（msuser=sql_backup_operator, mskey=密码）
├── conf/
│   └── openssl-sqlserver.cnf    # 专用 TLS 1.0 兼容配置
├── sql/
│   ├── 01_check_version.sql     # 查询版本
│   ├── 02_check_databases.sql   # 查询数据库列表
│   ├── 03_check_log_size.sql    # 查询日志文件大小
│   └── 04_check_disk_space.sql  # 查询磁盘空间
├── scripts/
│   ├── sqlcmd-test.sh           # 连接测试脚本
│   └── mssql-wrapper.sh         # mssql 包装命令源码
├── reports/                      # 检查报告输出
└── logs/                         # 运行日志
```

## mssql 命令详解

详见 **[commands.md](commands.md)**，包含 mssql 包装命令源码、所有参数说明和常用示例。

## 常用运维 SQL

详见 **[sql-recipes.md](sql-recipes.md)**，包含版本查询、日志截断、备份触发、SHRINKFILE 等运维常用 SQL。

## 迁移指南

详见 **[migration.md](migration.md)**，包含从零部署到新机器的完整步骤、避坑清单和一键诊断脚本。

## 安全说明

1. **不要修改 `/etc/ssl/openssl.cnf`** — 那是系统全局配置，会影响 curl/git/apt 等所有 TLS 客户端
2. 本技能通过 `OPENSSL_CONF` 环境变量仅在 sqlcmd 进程内加载专用配置，其他程序不受影响
3. `.env` 凭据文件必须 `chmod 600`
4. 生产环境建议创建 `sql_backup_operator` 专用账号，替代 `sa`
5. SQL Server 2012 升级到 SP4 后支持 TLS 1.2，届时可删除专用 OpenSSL 配置

## 关键经验

| 问题 | 原因 | 解决方案 |
|---|---|---|
| `SSL routines::unsupported protocol` | SQL 2012 RTM 仅 TLS 1.0，OpenSSL 3 默认禁用 | OPENSSL_CONF 隔离加载 |
| XCERP 日志膨胀 508 GB | SIMPLE 模式 .ldf 不自动缩小 | 业务低峰 `DBCC SHRINKFILE` |
| `sudo: 需要密码` | 非交互环境 | 配置 NOPASSWD |
