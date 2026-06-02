# Microsoft SQL Server Command Line Tools 18

本目录保存 Microsoft SQL Server Command Line Tools 18 及本机自定义的 `mssql` 包装命令，用于在 Linux / OpenClaw 主机上远程连接和运维 SQL Server，尤其是兼容 SQL Server 2012 这类旧版本实例。

> ⚠️ 这是系统级工具目录，不建议存放业务凭据、数据库备份文件或运行日志。凭据应放在受权限保护的 `.env` 或密钥管理系统中。

## 目录结构

```text
/opt/mssql-tools18/
├── bin/
│   ├── bcp      # SQL Server 批量导入/导出工具
│   ├── mssql    # 本机自定义 sqlcmd 包装脚本
│   └── sqlcmd   # Microsoft SQL Server 命令行查询工具
└── share/
    └── resources/
        └── en_US/
            ├── BatchParserGrammar.dfa
            ├── BatchParserGrammar.llr
            ├── bcp.rll
            └── SQLCMD.rll
```

## 工具版本

当前环境检查到：

```text
Microsoft SQL Server Command Line Tool
Version 18.6.0002.1 Linux
```

核心文件类型：

- `bin/sqlcmd`：ELF 64-bit Linux 可执行文件
- `bin/bcp`：ELF 64-bit Linux 可执行文件
- `bin/mssql`：Bash 包装脚本

## 工具说明

### sqlcmd

`sqlcmd` 是 SQL Server 官方命令行查询工具，适合执行 SQL 查询、批处理脚本、巡检 SQL 和维护命令。

常用示例：

```bash
/opt/mssql-tools18/bin/sqlcmd -S YOUR_SQLSERVER_HOST -U YOUR_SQL_LOGIN -P 'YOUR_SQL_PASSWORD' -C -Q "SELECT @@VERSION;"
```

执行 SQL 文件：

```bash
/opt/mssql-tools18/bin/sqlcmd -S YOUR_SQLSERVER_HOST -U YOUR_SQL_LOGIN -P 'YOUR_SQL_PASSWORD' -C -i /path/to/check.sql
```

常用参数：

| 参数 | 说明 |
|---|---|
| `-S` | SQL Server 地址或 DSN |
| `-U` | 登录用户名 |
| `-P` | 登录密码；建议避免直接写在命令历史中 |
| `-d` | 指定数据库 |
| `-Q` | 执行查询后退出 |
| `-i` | 执行 SQL 文件 |
| `-o` | 输出到文件 |
| `-C` | 信任服务器证书 |
| `-N` | 加密连接选项 |
| `-l` | 登录超时时间 |
| `-t` | 查询超时时间 |
| `-b` | SQL 出错时返回非 0 退出码，适合脚本自动化 |
| `-W` | 移除列尾空格 |
| `-s` | 指定列分隔符 |
| `-r1` | 将错误消息输出到 stderr |

### bcp

`bcp` 是 SQL Server 批量复制工具，适合大批量导入、导出表数据或查询结果。

导出查询结果：

```bash
/opt/mssql-tools18/bin/bcp "SELECT name FROM sys.databases" queryout databases.txt \
  -S YOUR_SQLSERVER_HOST \
  -U YOUR_SQL_LOGIN \
  -P 'YOUR_SQL_PASSWORD' \
  -C \
  -c \
  -t ','
```

常用参数：

| 参数 | 说明 |
|---|---|
| `in` | 从文件导入到表 |
| `out` | 从表导出到文件 |
| `queryout` | 导出查询结果 |
| `format` | 生成格式文件 |
| `-c` | 字符模式 |
| `-n` | Native 类型模式 |
| `-w` | Unicode 字符模式 |
| `-t` | 字段分隔符 |
| `-r` | 行分隔符 |
| `-b` | 批大小 |
| `-e` | 错误文件 |
| `-F` / `-L` | 起始行 / 结束行 |

### mssql

`/opt/mssql-tools18/bin/mssql` 是本机自定义 Bash 包装脚本，不是 Microsoft 官方二进制。它的作用是减少每次手写连接参数，并隔离旧版 SQL Server 所需的 OpenSSL 兼容配置。

当前包装逻辑：

1. 加载 `/home/tangzhiang/workspaces/sqlremote/.env` 中的连接变量。
2. 设置 `OPENSSL_CONF=/home/tangzhiang/workspaces/sqlremote/conf/openssl-sqlserver.cnf`。
3. 调用 `/opt/mssql-tools18/bin/sqlcmd`。
4. 默认添加 `-C` 信任服务器证书。
5. 将额外参数原样传递给 `sqlcmd`。

推荐用法：

```bash
/opt/mssql-tools18/bin/mssql -Q "SELECT @@VERSION;"
```

执行 SQL 文件：

```bash
/opt/mssql-tools18/bin/mssql -i /home/tangzhiang/workspaces/sqlremote/sql/01_check_version.sql
```

指定数据库：

```bash
/opt/mssql-tools18/bin/mssql -d YOUR_DATABASE -Q "SELECT TOP 10 name FROM sys.tables;"
```

覆盖默认连接目标或账号：

```bash
MSSQL_SERVER=YOUR_SQLSERVER_HOST \
MSSQL_USER=YOUR_SQL_LOGIN \
MSSQL_PASSWORD='YOUR_SQL_PASSWORD' \
/opt/mssql-tools18/bin/mssql -Q "SELECT DB_NAME();"
```

也可以在 `/home/tangzhiang/workspaces/sqlremote/.env` 中配置：

```bash
msuser=YOUR_SQL_LOGIN
mskey=YOUR_SQL_PASSWORD
```

> 不要把真实 `.env` 内容写入 README、工单、聊天记录或公网仓库。

## 与 sqlremote 项目的关系

本目录只保存工具本体和包装命令；实际运维脚本、OpenSSL 兼容配置、SQL 文件、执行报告位于：

```text
/home/tangzhiang/workspaces/sqlremote/
```

相关路径：

| 路径 | 用途 |
|---|---|
| `/home/tangzhiang/workspaces/sqlremote/.env` | 本地 SQL Server 连接凭据；必须保护 |
| `/home/tangzhiang/workspaces/sqlremote/conf/openssl-sqlserver.cnf` | SQL Server 2012 / TLS 1.0 兼容配置 |
| `/home/tangzhiang/workspaces/sqlremote/scripts/` | 连接测试、远程备份等脚本 |
| `/home/tangzhiang/workspaces/sqlremote/sql/` | 巡检 SQL 文件 |
| `/home/tangzhiang/workspaces/sqlremote/reports/` | 巡检与备份报告 |

## SQL Server 2012 兼容说明

SQL Server 2012 RTM 等旧版本可能只支持较老的 TLS / 加密能力。当前环境采用“单进程隔离”的方式兼容：

- 不修改系统全局 OpenSSL 策略。
- 只在 `mssql` 包装命令或相关脚本进程中设置 `OPENSSL_CONF`。
- `sqlcmd` 调用时使用 `-C` 信任服务器证书。

这样可以兼顾旧系统可连接性和主机整体安全性。

## 安全建议

- 不要在命令行历史中长期保留 `-P '真实密码'`。
- 优先通过受权限保护的 `.env` 或环境变量传递密码。
- `.env` 权限建议设置为 `600`：

```bash
chmod 600 /home/tangzhiang/workspaces/sqlremote/.env
```

- 不要把 `/home/tangzhiang/workspaces/sqlremote/.env` 提交到 Git。
- 不要把 SQL Server 备份文件放在 `/opt/mssql-tools18`。
- 如果必须在脚本中使用账号，建议使用专用低权限账号，不要长期使用 `sa`。
- 面向公网发布文档时，使用 `YOUR_SQLSERVER_HOST`、`YOUR_SQL_LOGIN`、`YOUR_SQL_PASSWORD` 等占位符。

## 故障排查

### 1. `mssql` 提示缺少密码

现象：

```text
缺少密码：请配置 /home/tangzhiang/workspaces/sqlremote/.env 或环境变量 mskey/MSSQL_PASSWORD
```

处理：

```bash
cat > /home/tangzhiang/workspaces/sqlremote/.env <<'ENV'
msuser=YOUR_SQL_LOGIN
mskey=YOUR_SQL_PASSWORD
ENV
chmod 600 /home/tangzhiang/workspaces/sqlremote/.env
```

### 2. TLS / SSL 握手失败

检查专用 OpenSSL 配置是否存在：

```bash
ls -l /home/tangzhiang/workspaces/sqlremote/conf/openssl-sqlserver.cnf
```

使用包装命令测试：

```bash
/opt/mssql-tools18/bin/mssql -Q "SELECT @@VERSION;"
```

### 3. SQL 执行失败但脚本返回成功

自动化脚本建议加 `-b`，让 SQL 错误触发非 0 退出码：

```bash
/opt/mssql-tools18/bin/mssql -b -Q "SELECT 1;"
```

### 4. 输出列不好解析

脚本化输出建议组合使用：

```bash
/opt/mssql-tools18/bin/mssql -W -s '|' -h -1 -Q "SELECT name FROM sys.databases;"
```

含义：

- `-W`：去掉尾部空格
- `-s '|'`：使用竖线作为列分隔符
- `-h -1`：不输出表头

## 维护建议

- `/opt/mssql-tools18/bin/sqlcmd` 和 `/opt/mssql-tools18/bin/bcp` 属于 Microsoft 工具，升级时应整体替换工具包。
- `/opt/mssql-tools18/bin/mssql` 是本机自定义脚本，升级工具包前应先备份。
- 变更 `mssql` 包装逻辑后，应同步更新本文档和 `/home/tangzhiang/workspaces/sqlremote/README.md`。

## License

`sqlcmd`、`bcp` 及资源文件属于 Microsoft SQL Server Command Line Tools 组件，遵循 Microsoft 对应许可。`bin/mssql` 是本机自定义包装脚本，按本机/团队内部运维规范维护。
