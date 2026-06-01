# mssql-legacy

Linux 远程管理旧版 SQL Server 的实战工具集，重点解决 **Ubuntu 22.04/24.04 + OpenSSL 3** 连接 **SQL Server 2012 RTM / TLS 1.0** 时的兼容性问题。

这个项目来自真实运维场景：新版 Linux 客户端安全策略默认禁用 TLS 1.0，而 SQL Server 2012 RTM 只能使用旧 TLS 协议，直接连接会出现 `unsupported protocol`。`mssql-legacy` 通过 **进程级 `OPENSSL_CONF` 隔离方案**，只让 `sqlcmd` 兼容旧协议，不降低系统全局 TLS 安全等级。

## 核心价值

- **兼容旧系统**：在 Ubuntu 24.04 / OpenSSL 3 环境下连接 SQL Server 2012 RTM。
- **不污染系统安全策略**：不修改 `/etc/ssl/openssl.cnf`，仅对 `sqlcmd` 进程临时启用 TLS 1.0。
- **一条命令管理 SQL Server**：提供 `mssql` 包装命令，自动加载凭据、OpenSSL 配置和 `-C` 证书信任参数。
- **内置巡检 SQL**：包含版本检查、数据库恢复模式、日志大小、磁盘空间等常用 SQL 脚本。
- **适合自动化运维**：支持 `mssql -Q`、`mssql -i`、日志输出、环境变量覆盖和脚本化调用。
- **附带迁移文档**：从依赖安装、配置 TLS 隔离、部署包装命令到故障排查均有说明。

## 适用场景

- Linux 服务器需要远程管理 SQL Server 2012。
- `sqlcmd` 连接 SQL Server 2012 RTM 报 TLS / SSL 协议错误。
- 不能为了连接旧数据库而降低整台 Linux 机器的 OpenSSL 安全级别。
- 需要在自动化脚本中执行 SQL Server 巡检、备份、日志治理等任务。
- 需要把 SQL Server 2012 RTM 平稳过渡到 SP4 或更高版本前做临时运维支撑。

## 兼容性

| 组件 | 支持情况 |
|---|---|
| 操作系统 | Ubuntu 22.04 / 24.04 LTS，x86_64 / amd64 |
| SQL Server | 重点适配 SQL Server 2012 RTM；2012 SP4、2014+ 通常不再需要 TLS 1.0 隔离 |
| 客户端工具 | Microsoft ODBC Driver 18、mssql-tools18、sqlcmd、bcp |
| OpenSSL | OpenSSL 3.x 环境下实测可用 |
| 架构 | x86_64 / amd64；mssql-tools18 暂不支持 ARM64 |

## 目录结构

```text
mssql-legacy/
├── SKILL.md                    # AgentSkill 入口说明
├── README.md                   # 项目说明文档
├── prerequisites.md            # 依赖环境与安装步骤
├── commands.md                 # mssql 包装命令与 sqlcmd 参数说明
├── sql-recipes.md              # 常用 SQL Server 运维 SQL
├── migration.md                # 迁移到新机器的完整步骤
├── conf/
│   └── README.md               # openssl-sqlserver.cnf 生成说明
├── docs/
│   └── troubleshooting.md      # 故障排查手册
├── scripts/
│   ├── check-prereqs.sh        # 前提依赖检查脚本
│   ├── mssql-wrapper.sh        # mssql 包装命令源码
│   └── sqlcmd-test.sh          # SQL Server 连接测试脚本
└── sql/
    ├── 01_check_version.sql    # 查询 SQL Server 版本
    ├── 02_check_databases.sql  # 查询数据库与恢复模式
    ├── 03_check_log_size.sql   # 查询日志文件大小与使用率
    └── 04_check_disk_space.sql # 查询磁盘空间与数据文件占用
```

## 工作原理

普通做法为了连接 SQL Server 2012 RTM，可能会修改系统级 OpenSSL 配置，允许 TLS 1.0：

```text
/etc/ssl/openssl.cnf
```

这会影响整台机器上的 `curl`、`git`、`apt` 等程序，存在安全风险。

`mssql-legacy` 的做法是复制一份专用配置：

```text
~/workspaces/sqlremote/conf/openssl-sqlserver.cnf
```

然后只在执行 `sqlcmd` 时设置：

```bash
OPENSSL_CONF=~/workspaces/sqlremote/conf/openssl-sqlserver.cnf
```

这样 TLS 1.0 兼容性只对当前 `sqlcmd` 进程生效，系统其他程序仍保持现代 TLS 策略。

## 快速开始

### 1. 安装 Microsoft SQL Server 客户端工具

Ubuntu 24.04：

```bash
mkdir -p ~/workspaces/download
cd ~/workspaces/download

curl -fsSLO https://packages.microsoft.com/config/ubuntu/24.04/packages-microsoft-prod.deb
sudo dpkg -i packages-microsoft-prod.deb
sudo apt-get update

sudo ACCEPT_EULA=Y apt-get install -y \
  msodbcsql18 \
  mssql-tools18 \
  unixodbc \
  unixodbc-dev \
  smbclient \
  cifs-utils
```

Ubuntu 22.04 把下载地址中的 `24.04` 改为 `22.04`。

### 2. 创建工作目录

```bash
mkdir -p ~/workspaces/sqlremote/{sql,scripts,conf,logs,reports}
```

如果你希望使用本项目内置 SQL 脚本，可以复制：

```bash
cp sql/*.sql ~/workspaces/sqlremote/sql/
```

### 3. 配置凭据

创建：

```text
~/workspaces/sqlremote/.env
```

内容示例：

```text
msuser=sql_backup_operator
mskey=your_password_here
```

设置权限：

```bash
chmod 600 ~/workspaces/sqlremote/.env
```

生产环境建议创建专用低权限账号，不建议长期使用 `sa`。

### 4. 创建专用 OpenSSL 配置

```bash
cp /etc/ssl/openssl.cnf ~/workspaces/sqlremote/conf/openssl-sqlserver.cnf

sed -i '/^providers = provider_sect/a ssl_conf = ssl_sect' \
  ~/workspaces/sqlremote/conf/openssl-sqlserver.cnf

cat >> ~/workspaces/sqlremote/conf/openssl-sqlserver.cnf <<'CFG'

# === Allow legacy TLSv1 for SQL Server 2012 RTM ===
[ssl_sect]
system_default = system_default_sect

[system_default_sect]
MinProtocol = TLSv1
CipherString = DEFAULT@SECLEVEL=0
CFG
```

### 5. 安装 `mssql` 包装命令

```bash
mkdir -p ~/.local/bin
cp scripts/mssql-wrapper.sh ~/.local/bin/mssql
chmod +x ~/.local/bin/mssql
```

确保 `~/.local/bin` 在 PATH 中：

```bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

### 6. 测试连接

默认服务器地址可通过环境变量覆盖：

```bash
MSSQL_SERVER=192.0.2.10 mssql -Q "SELECT @@VERSION"
```

也可以直接运行测试脚本：

```bash
MSSQL_SERVER=192.0.2.10 bash scripts/sqlcmd-test.sh
```

## 常用命令

查询 SQL Server 版本：

```bash
mssql -Q "SELECT @@VERSION"
```

列出所有数据库及恢复模式：

```bash
mssql -Q "SELECT name, recovery_model_desc, state_desc FROM sys.databases ORDER BY name"
```

执行 SQL 文件：

```bash
mssql -i ~/workspaces/sqlremote/sql/02_check_databases.sql
```

切换默认数据库：

```bash
mssql -d HR -Q "SELECT TOP 10 * FROM sys.tables"
```

查询日志文件大小：

```bash
mssql -Q "SELECT DB_NAME(database_id) AS db, name, size * 8 / 1024 AS size_mb FROM sys.master_files WHERE type_desc = 'LOG' ORDER BY size DESC"
```

执行完整备份：

```bash
mssql -Q "BACKUP DATABASE [HR] TO DISK = N'D:\backup\HR_full.bak' WITH INIT, COMPRESSION, CHECKSUM, STATS = 10"
```

执行日志备份：

```bash
mssql -Q "BACKUP LOG [HR] TO DISK = N'D:\backup\HR_log.trn' WITH INIT, COMPRESSION, CHECKSUM"
```

## 环境变量

| 变量 | 说明 | 默认行为 |
|---|---|---|
| `MSSQL_SERVER` | SQL Server 地址或 `host,port` | 包装脚本内置默认值，建议显式指定 |
| `MSSQL_USER` | SQL 登录用户名 | 优先读取 `.env` 中的 `msuser` |
| `MSSQL_PASSWORD` | SQL 登录密码 | 优先读取 `.env` 中的 `mskey` |
| `SQLREMOTE_DIR` | 工作目录 | 部分脚本默认使用 `~/workspaces/sqlremote` |

示例：

```bash
MSSQL_SERVER=192.0.2.10 MSSQL_USER=readonly MSSQL_PASSWORD='your_password_here' \
  mssql -Q "SELECT name FROM sys.databases"
```

## 一键检查

运行前提依赖检查：

```bash
bash scripts/check-prereqs.sh
```

检查内容包括：

- 系统架构和 Ubuntu 版本
- `msodbcsql18` / `mssql-tools18` / `unixodbc` 是否安装
- `sqlcmd` 是否可执行
- ODBC Driver 18 是否注册
- `~/workspaces/sqlremote` 工作目录是否存在
- `.env` 是否存在且权限是否安全
- `openssl-sqlserver.cnf` 是否包含 TLS 兼容配置
- `mssql` 包装命令是否可用
- SQL Server 1433 端口是否可达

## 文档导航

| 文档 | 内容 |
|---|---|
| [prerequisites.md](prerequisites.md) | 操作系统、软件包、OpenSSL、凭据、网络连通性要求 |
| [commands.md](commands.md) | `mssql` 包装命令、`sqlcmd` 参数、`bcp` 使用示例 |
| [sql-recipes.md](sql-recipes.md) | 健康检查、日志治理、备份、磁盘空间、性能排查 SQL |
| [migration.md](migration.md) | 迁移到新机器的 5 步流程、避坑清单和清理方法 |
| [docs/troubleshooting.md](docs/troubleshooting.md) | TLS、连接、权限、备份、性能、ODBC trace 故障排查 |
| [conf/README.md](conf/README.md) | 专用 `openssl-sqlserver.cnf` 的生成和清理说明 |

## 安全注意事项

1. **不要修改系统全局 OpenSSL 配置**  
   不要为了连接 SQL Server 2012 RTM 修改 `/etc/ssl/openssl.cnf`，否则会影响整台机器的 TLS 安全策略。

2. **保护 `.env` 凭据文件**  
   `.env` 必须设置为 `chmod 600`，不要提交到 GitHub。

3. **不要长期使用 `sa` 账号**  
   生产环境建议创建专用账号，例如只授予 `db_backupoperator`、只读查询或特定数据库权限。

4. **TLS 1.0 只是兼容手段，不是长期方案**  
   推荐尽快升级 SQL Server 2012 到 SP4，或迁移到更新版本，以获得 TLS 1.2 支持。

5. **谨慎执行日志收缩**  
   `DBCC SHRINKFILE` 只适合处理异常膨胀，不应作为日常维护任务。

## 发布到 GitHub 前建议

当前仓库不应包含任何真实生产凭据。发布前建议检查：

```bash
grep -RInE 'password|passwd|pwd|mskey|secret|token|apikey|api_key' . \
  --exclude-dir=.git
```

建议添加 `.gitignore`：

```gitignore
.env
*.log
logs/
reports/
*.bak
*.trn
```

本仓库已提供 `LICENSE` 文件，默认采用 MIT License。

## 常见问题

### `SSL Provider: unsupported protocol`

原因通常是未加载专用 `OPENSSL_CONF`，OpenSSL 3 默认拒绝 TLS 1.0。

处理：

```bash
export OPENSSL_CONF=~/workspaces/sqlremote/conf/openssl-sqlserver.cnf
```

更推荐使用本项目的 `mssql` 包装命令，它会自动设置。

### `certificate verify failed`

ODBC Driver 18 默认启用加密并校验证书，旧 SQL Server 通常没有可信证书。

处理：使用 `-C` 信任服务器证书。`mssql` 包装命令已内置 `-C`。

### `Login timeout expired`

检查网络和 SQL Server 配置：

```bash
nc -vz 192.0.2.10 1433
```

同时确认：

- Windows 防火墙放行 1433/TCP
- SQL Server 已启用 TCP/IP
- SQL Server Browser 或固定端口配置正确
- 命名实例使用了正确端口

### 备份时报 `Operating system error 5`

这是 SQL Server 服务账号没有目标目录权限。需要在 Windows 服务器上给 SQL Server 服务账号授予备份目录读写权限。

## 限制

- 本项目主要面向 SQL Server 2012 RTM 的临时兼容和运维场景。
- `mssql-tools18` 官方不支持 ARM64 Linux。
- 专用 OpenSSL 配置允许 TLS 1.0，只应该被 `sqlcmd` 这类兼容进程使用，不应该作为系统全局安全策略。
- 项目不包含真实生产配置、真实密码、真实备份路径或任何私有业务数据。
- SQL Server 2012 已经过官方生命周期，长期方案应该是升级数据库版本或迁移业务系统。

## Roadmap

- [x] 增加 `.gitignore` 示例文件
- [x] 增加 `LICENSE`
- [ ] 增加 GitHub Actions Markdown lint
- [ ] 增加更多 SQL Server 2012 健康检查 SQL
- [ ] 增加备份策略模板和 SQL Agent Job 示例
- [ ] 增加升级到 SQL Server 2012 SP4 后的清理指南

## 贡献

欢迎提交 Issue 或 Pull Request，尤其是以下内容：

- 不同 Linux 发行版的兼容性验证
- SQL Server 2012 SP4 / 2014 / 2016 的连接测试结果
- 更完整的巡检 SQL
- 备份、恢复、日志治理案例
- 文档修正和故障排查补充

提交前请确认没有提交任何生产密码、内网地址、客户数据或备份文件。

## 许可证

本项目基于 MIT License 开源。详见 [LICENSE](LICENSE)。

## 致谢

这个项目来自旧版数据库系统的真实运维经验。它的目标不是鼓励继续使用过时系统，而是在升级完成之前，为遗留系统提供一个安全、可控、可审计的 Linux 远程管理方案。
