# SQL Remote Operations

用于从 Linux / OpenClaw 主机远程管理 SQL Server 2012 的轻量级运维目录。当前重点覆盖 SQL Server 2012 RTM 的兼容连接、基础巡检 SQL，以及不依赖 SQL Server Agent 的远程逐库串行完整备份。

> ⚠️ 本目录面向内网运维场景。不要把 `.env`、日志中的敏感连接信息、数据库备份文件或真实内网拓扑直接发布到公网仓库。

## 功能概览

- **SQL Server 2012 兼容连接**：通过专用 `OPENSSL_CONF` 仅在当前进程放宽 TLS 配置，避免污染系统全局 OpenSSL 策略。
- **连接测试**：`scripts/sqlcmd-test.sh` 使用 `sqlcmd` 连接目标 SQL Server，并执行版本检查 SQL。
- **基础巡检 SQL**：`sql/01_check_version.sql`、`sql/02_check_databases.sql` 用于快速确认版本、数据库状态和恢复模式。
- **远程逐库完整备份**：`scripts/remote_full_backup_133_14.sh` 从本机发起 `BACKUP DATABASE`，备份文件写入 SQL Server 服务器本机路径。
- **备份校验**：支持每个库备份后执行 `RESTORE VERIFYONLY WITH CHECKSUM`。
- **串行执行**：逐库顺序备份，默认库间暂停，降低对生产 IO 的冲击。
- **运行留痕**：备份清单和执行日志统一写入 `reports/`。

## 目录结构

```text
sqlremote/
├── conf/
│   └── openssl-sqlserver.cnf       # sqlcmd 专用 OpenSSL 配置，兼容旧版 SQL Server TLS
├── data/
│   └── powermem_dev.db             # 本地数据文件；不建议纳入公开仓库
├── logs/                           # 临时日志目录
├── reports/                        # 巡检、优化、备份执行报告
├── scripts/
│   ├── remote_full_backup_133_14.sh # 远程逐库完整备份脚本
│   └── sqlcmd-test.sh              # SQL Server 连接测试脚本
├── sql/
│   ├── 01_check_version.sql         # SQL Server 版本检查
│   └── 02_check_databases.sql       # 数据库状态与恢复模式检查
├── .env                            # 本地凭据文件；必须忽略，不要提交
└── README.md
```

## 运行要求

- Linux / OpenClaw 主机
- Bash 4+
- Microsoft `sqlcmd`
  - 当前脚本默认使用 `/opt/mssql-tools18/bin/sqlcmd`
- 本地封装命令 `mssql`
  - 默认路径：`$HOME/.local/bin/mssql`
  - 作用：自动加载 SQL Server 连接参数和兼容 OpenSSL 配置
- 目标 SQL Server 账号具备相应权限
  - 连接测试：至少可执行基础查询
  - 完整备份：需要执行 `BACKUP DATABASE`
  - 校验：需要执行 `RESTORE VERIFYONLY`
- SQL Server 服务账号需要能写入备份目标目录，例如 `D:\backup`

## 配置

### 1. 凭据文件

在项目根目录创建 `.env`，不要提交到 Git：

```bash
cat > /home/tangzhiang/workspaces/sqlremote/.env <<'EOF'
msuser=YOUR_SQL_LOGIN
mskey=YOUR_SQL_PASSWORD
EOF
chmod 600 /home/tangzhiang/workspaces/sqlremote/.env
```

兼容变量名：

- `msuser` / `mskey`
- `SQLSERVER_USER` / `SQLSERVER_PASSWORD`

> 建议使用专用低权限运维账号，不要长期使用 `sa`。如果账号只负责备份，应尽量限制登录来源和授权范围。

### 2. OpenSSL 兼容配置

`conf/openssl-sqlserver.cnf` 是为旧版 SQL Server / TLS 1.0 兼容准备的专用配置。脚本只在当前进程里设置：

```bash
export OPENSSL_CONF=/home/tangzhiang/workspaces/sqlremote/conf/openssl-sqlserver.cnf
```

不要把 TLS 1.0 放宽配置写入系统全局 OpenSSL 配置，否则会降低整台机器的安全基线。

## 快速开始

### 测试 SQL Server 连接

默认连接脚本内置目标地址，也可以通过第一个参数覆盖：

```bash
/home/tangzhiang/workspaces/sqlremote/scripts/sqlcmd-test.sh 192.0.2.10
```

输出中应能看到 SQL Server 版本信息。

### 查看数据库状态

如果已经配置好 `mssql` 包装命令：

```bash
mssql -i /home/tangzhiang/workspaces/sqlremote/sql/02_check_databases.sql
```

或直接执行查询：

```bash
mssql -Q "SELECT name, recovery_model_desc, state_desc FROM sys.databases ORDER BY name;"
```

## 远程逐库完整备份

核心脚本：

```bash
/home/tangzhiang/workspaces/sqlremote/scripts/remote_full_backup_133_14.sh
```

它会完成以下流程：

1. 从目标 SQL Server 获取所有 `ONLINE` 数据库列表。
2. 排除 `tempdb`。
3. 根据配置决定是否包含系统库 `master`、`model`、`msdb`。
4. 逐库串行执行 `BACKUP DATABASE ... WITH INIT, COMPRESSION, CHECKSUM, STATS = 10`。
5. 可选执行 `RESTORE VERIFYONLY ... WITH CHECKSUM`。
6. 将日志和数据库清单写入 `reports/`。

### 推荐执行方式

如果目标服务器上 `D:\backup` 已经存在，且不希望启用 `xp_cmdshell` 创建目录：

```bash
USE_DATE_SUBDIR=0 \
CREATE_BACKUP_DIR=0 \
SLEEP_SECONDS=3 \
/home/tangzhiang/workspaces/sqlremote/scripts/remote_full_backup_133_14.sh
```

说明：

- `USE_DATE_SUBDIR=0`：直接使用 `D:\backup`，不追加日期子目录。
- `CREATE_BACKUP_DIR=0`：不尝试用 `xp_cmdshell` 创建目录。
- `SLEEP_SECONDS=3`：每个数据库之间暂停 3 秒，降低 IO 冲击。

### 常用环境变量

| 变量 | 默认值 | 说明 |
|---|---:|---|
| `ROOT_BACKUP_PATH` | `D:\backup` | SQL Server 服务器本机看到的备份根路径 |
| `VERIFY_BACKUP` | `1` | `1` 表示备份后执行 `RESTORE VERIFYONLY`，`0` 表示跳过 |
| `INCLUDE_SYSTEM_DB` | `1` | `1` 包含 `master/model/msdb`，`0` 只备业务库 |
| `SQL_TIMEOUT` | `0` | `sqlcmd` 查询超时；`0` 表示不限制 |
| `SLEEP_SECONDS` | `3` | 每个库之间暂停秒数 |
| `USE_DATE_SUBDIR` | `1` | `1` 使用 `D:\backup\yyyyMMdd`，`0` 直接使用根目录 |
| `CREATE_BACKUP_DIR` | `1` | `1` 尝试通过 `xp_cmdshell` 建目录，`0` 跳过 |
| `MSSQL_BIN` | `$HOME/.local/bin/mssql` | `mssql` 包装命令路径 |

### 输出文件

每次执行会生成两类文件：

```text
reports/remote-full-backup-133-14-YYYYMMDD_HHMMSS.log
reports/remote-full-backup-133-14-YYYYMMDD_HHMMSS-db-list.txt
```

示例查看最新日志：

```bash
ls -lt /home/tangzhiang/workspaces/sqlremote/reports | head
less /home/tangzhiang/workspaces/sqlremote/reports/remote-full-backup-133-14-YYYYMMDD_HHMMSS.log
```

## 注意事项

### 备份路径在 SQL Server 服务器上

`BACKUP DATABASE TO DISK = N'D:\backup\xxx.bak'` 的路径不是 Linux 本机路径，而是 SQL Server 服务进程所在 Windows 服务器能访问的路径。

因此执行前要确认：

- 目标目录已经存在，或允许脚本通过 `xp_cmdshell` 创建。
- SQL Server 服务账号对该目录有写权限。
- 磁盘空间充足。

### 关于 `xp_cmdshell`

脚本支持 `CREATE_BACKUP_DIR=1` 通过 `xp_cmdshell` 创建目录，但生产环境通常会禁用它。更稳妥的做法是提前在 Windows 服务器上创建备份目录，然后执行：

```bash
USE_DATE_SUBDIR=0 CREATE_BACKUP_DIR=0 /home/tangzhiang/workspaces/sqlremote/scripts/remote_full_backup_133_14.sh
```

### 关于 SQL Server 2012 RTM

旧版 SQL Server 可能只能协商较旧的 TLS 协议。这里采用“单进程隔离”的方式兼容：

- 只对 `sqlcmd` / `mssql` 当前进程设置 `OPENSSL_CONF`。
- 不修改系统全局安全策略。
- 不建议把该兼容方案扩散给其他服务。

## 故障排查

### 缺少密码

现象：

```text
缺少密码：请配置 ~/workspaces/sqlremote/.env
```

处理：

```bash
cat > /home/tangzhiang/workspaces/sqlremote/.env <<'EOF'
msuser=YOUR_SQL_LOGIN
mskey=YOUR_SQL_PASSWORD
EOF
chmod 600 /home/tangzhiang/workspaces/sqlremote/.env
```

### TLS / SSL 握手失败

检查：

```bash
echo "$OPENSSL_CONF"
ls -l /home/tangzhiang/workspaces/sqlremote/conf/openssl-sqlserver.cnf
```

确认脚本使用的是专用 OpenSSL 配置，而不是系统全局配置。

### 备份失败：无法打开备份设备

常见原因：

- `D:\backup` 不存在。
- SQL Server 服务账号无写权限。
- 磁盘空间不足。
- 路径写到了 Linux 本机，但 SQL Server 实际在 Windows 服务器上。

处理建议：

1. 登录 SQL Server 所在服务器。
2. 手动创建备份目录。
3. 给 SQL Server 服务账号写权限。
4. 使用 `USE_DATE_SUBDIR=0 CREATE_BACKUP_DIR=0` 重试。

### 循环只备份了第一个库或重复备份同一个库

该问题通常是 Bash `while read` 循环被子进程抢占标准输入导致。当前脚本已使用 `mapfile` 先读入数组，再逐库遍历，避免该问题。

## 安全建议

- `.env` 必须设置为 `600` 权限，并加入 `.gitignore`。
- 不要提交 `reports/`、`logs/`、`data/`、`*.bak`、`*.trn`、`*.mdf`、`*.ldf`。
- README、示例脚本、公开文档中使用 `192.0.2.0/24` 这类 RFC 5737 文档地址，不暴露真实内网 IP。
- 备份账号应使用专用账号，最小授权，不建议长期使用 `sa`。
- 如果 `.env` 或日志曾被提交到 Git，需要立即轮换密码，并用 `git filter-repo` 或 BFG 清理历史。

## 建议的 `.gitignore`

```gitignore
.env
.env.*
*.key
*.pem
id_rsa*
credentials*
secrets.*
logs/
reports/
data/
*.bak
*.trn
*.mdf
*.ndf
*.ldf
```

## 相关文档

- 运维归档：`/home/tangzhiang/workspaces/ai_agent_self_upgrade/mssql-legacy-share/`
- SQL Server 2012 远程逐库备份实战文档：`sqlserver-2012-remote-serial-backup-20260601.md`
- mssql-legacy 技能目录：`/home/tangzhiang/workspaces/skills/mssql-legacy/`

## License

当前目录未发现独立许可证文件。若准备发布为公开仓库，建议补充 `LICENSE`，例如 MIT License；内部运维目录则按团队内部规范管理。
