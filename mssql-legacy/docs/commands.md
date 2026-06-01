# 命令使用方法

> 📌 本文档包含 `mssql` 包装命令源码、参数说明和常用示例。也包含原始 `sqlcmd` 的常用参数速查。

## 1. mssql 包装命令

### 1.1 安装

将 `scripts/mssql-wrapper.sh` 复制到 `~/.local/bin/mssql` 并赋可执行权限：

```bash
cp ~/workspaces/skills/mssql-legacy/scripts/mssql-wrapper.sh ~/.local/bin/mssql
chmod +x ~/.local/bin/mssql
```

确保 `~/.local/bin` 在 PATH 中：

```bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

### 1.2 功能说明

`mssql` 是 sqlcmd 的薄包装，自动完成以下三件事：

1. 从 `~/workspaces/sqlremote/.env` 加载凭据（`msuser` / `mskey`）
2. 设置 `OPENSSL_CONF` 为专用 TLS 兼容配置（不污染系统全局）
3. 自动加 `-C` 参数信任服务器证书

其余参数原样透传给 sqlcmd。

### 1.3 源码

```bash
#!/usr/bin/env bash
# mssql - sqlcmd 包装命令，自动加载 OPENSSL_CONF 和凭据
# 用法：
#   mssql -Q "SELECT @@VERSION"
#   mssql -i some.sql
#   mssql -d HR -Q "SELECT TOP 10 * FROM sys.tables"
set -euo pipefail

ROOT_DIR="$HOME/workspaces/sqlremote"

# 加载凭据
if [[ -f "$ROOT_DIR/.env" ]]; then
  set -a
  . "$ROOT_DIR/.env"
  set +a
fi

SERVER="${MSSQL_SERVER:-192.0.2.10}"
USER_NAME="${msuser:-${MSSQL_USER:-sql_backup_operator}}"
PASSWORD="${mskey:-${MSSQL_PASSWORD:-}}"

if [[ -z "$PASSWORD" ]]; then
  echo "❌ 缺少密码：请配置 $ROOT_DIR/.env 或环境变量 mskey/MSSQL_PASSWORD" >&2
  exit 2
fi

export OPENSSL_CONF="$ROOT_DIR/conf/openssl-sqlserver.cnf"

if [[ ! -f "$OPENSSL_CONF" ]]; then
  echo "❌ 专用 OpenSSL 配置不存在：$OPENSSL_CONF" >&2
  exit 3
fi

exec /opt/mssql-tools18/bin/sqlcmd \
  -S "$SERVER" \
  -U "$USER_NAME" \
  -P "$PASSWORD" \
  -C \
  "$@"
```

### 1.4 环境变量覆盖

| 变量 | 默认值 | 说明 |
|---|---|---|
| `MSSQL_SERVER` | `192.0.2.10` | 目标 SQL Server 地址 |
| `MSSQL_USER` | 从 `.env` 的 `msuser` | SQL 登录用户名 |
| `MSSQL_PASSWORD` | 从 `.env` 的 `mskey` | SQL 登录密码 |
| `OPENSSL_CONF` | 自动设置 | 不建议手动覆盖 |

临时切换服务器：

```bash
MSSQL_SERVER=192.0.2.11 mssql -Q "SELECT @@VERSION"
```

### 1.5 常用示例

```bash
# 查询版本
mssql -Q "SELECT @@VERSION"

# 紧凑输出（去尾部空格 + 去列标题）
mssql -Q "SELECT @@VERSION" -h -1 -W

# 列出所有数据库及恢复模式
mssql -Q "SELECT name, recovery_model_desc FROM sys.databases ORDER BY name"

# 切换默认数据库
mssql -d HR -Q "SELECT TOP 10 * FROM sys.tables"

# 执行 SQL 文件
mssql -i ~/workspaces/sqlremote/sql/02_check_databases.sql

# 输出到日志
mssql -i backup.sql -o ~/workspaces/sqlremote/logs/backup.log

# 查询日志文件大小（降序）
mssql -Q "SELECT DB_NAME(database_id) AS db, name, size*8/1024 AS size_mb FROM sys.master_files WHERE type_desc='LOG' ORDER BY size DESC"

# 查询数据文件大小
mssql -Q "SELECT DB_NAME(database_id) AS db, name, size*8/1024 AS size_mb FROM sys.master_files WHERE type_desc='ROWS' ORDER BY size DESC"

# 执行备份
mssql -Q "BACKUP DATABASE [HR] TO DISK = N'D:\backup\HR_test.bak' WITH INIT, COMPRESSION, STATS = 10"

# 日志截断（FULL 恢复模式）
mssql -Q "BACKUP LOG [HR] TO DISK = N'D:\backup\HR_log.trn' WITH INIT"

# 收缩日志文件
mssql -Q "USE [XCERP]; DBCC SHRINKFILE (XCERP_log, 2048)"
```

## 2. sqlcmd 原始命令参数速查

当不使用 `mssql` 包装时，需手动指定完整路径和参数：

```bash
OPENSSL_CONF=~/workspaces/sqlremote/conf/openssl-sqlserver.cnf \
  /opt/mssql-tools18/bin/sqlcmd \
  -S 192.0.2.10 \
  -U sql_backup_operator \
  -P '密码' \
  -C \
  -Q "SELECT @@VERSION"
```

### 2.1 常用参数

| 参数 | 作用 | 示例 |
|---|---|---|
| `-S` | 服务器地址 | `-S 192.0.2.10` |
| `-U` | SQL 登录用户 | `-U sql_backup_operator` |
| `-P` | SQL 登录密码 | `-P '密码'` |
| `-C` | 信任服务器证书 | `-C`（SQL 2012 RTM 必需）|
| `-d` | 默认数据库 | `-d HR` |
| `-Q` | 执行一条查询后退出 | `-Q "SELECT 1"` |
| `-i` | 从文件读 SQL | `-i backup.sql` |
| `-o` | 输出到文件 | `-o result.log` |
| `-W` | 去除输出尾部空格 | `-W` |
| `-h -1` | 去掉列标题 | `-h -1` |
| `-s` | 列分隔符 | `-s ","` |
| `-b` | 出错时返回非 0 | `-b` |
| `-t` | 查询超时秒数 | `-t 300` |
| `-l` | 登录超时秒数 | `-l 10` |
| `-v` | 传脚本变量 | `-v DBNAME=HR` |

### 2.2 不常用但有用的参数

| 参数 | 作用 |
|---|---|
| `-k1` | 转义控制字符 |
| `-r0` | 错误消息也输出到 stderr |
| `-m-1` | 不显示错误消息头 |
| `-u` | Unicode 输出 |
| `-Y` | 固定列宽 |

## 3. bcp 批量工具

`/opt/mssql-tools18/bin/bcp` 随 mssql-tools18 安装，用于批量导入导出数据。

```bash
# 导出查询结果到 CSV
OPENSSL_CONF=~/workspaces/sqlremote/conf/openssl-sqlserver.cnf \
  /opt/mssql-tools18/bin/bcp \
  "SELECT TOP 100 * FROM HR.dbo.Employee" queryout /tmp/employee.csv \
  -S 192.0.2.10 -U sql_backup_operator -P '密码' -C -c -t ","

# 导入 CSV 到表
OPENSSL_CONF=~/workspaces/sqlremote/conf/openssl-sqlserver.cnf \
  /opt/mssql-tools18/bin/bcp HR.dbo.Employee in /tmp/employee.csv \
  -S 192.0.2.10 -U sql_backup_operator -P '密码' -C -c -t ","
```

| 参数 | 作用 |
|---|---|
| `queryout` | 查询导出 |
| `in` | 导入 |
| `-c` | 字符模式（非 Unicode）|
| `-n` | 原生模式（保留类型）|
| `-t ","` | 字段分隔符 |
| `-r "\n"` | 行分隔符 |

## 4. 连接测试脚本

`scripts/sqlcmd-test.sh` 提供交互式连接测试：

```bash
# 默认测试 192.0.2.10
~/workspaces/sqlremote/scripts/sqlcmd-test.sh

# 指定其他服务器
~/workspaces/sqlremote/scripts/sqlcmd-test.sh 192.0.2.11
```

输出：

```text
🔧 OPENSSL_CONF=/home/user/workspaces/sqlremote/conf/openssl-sqlserver.cnf
🌐 Server: 192.0.2.10
👤 User: sql_backup_operator

version_info
--------------------------------------------------------------------
Microsoft SQL Server 2012 - 11.0.2100.60 (X64) ...
```
