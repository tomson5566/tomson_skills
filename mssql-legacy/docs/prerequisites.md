# 前提依赖环境

> 📌 本文档列出 `mssql-legacy` 技能所需的全部依赖项。迁移到新机器时，按顺序检查。

## 1. 操作系统

| 项目 | 要求 | 说明 |
|---|---|---|
| 发行版 | Ubuntu 22.04 / 24.04 LTS | 本技能在 Ubuntu 24.04 noble 实测通过 |
| 架构 | x86_64 / amd64 | mssql-tools18 暂不支持 ARM64 |
| 内核 | Linux 5.15+ | 任意现代发行版都满足 |

验证：

```bash
uname -m && cat /etc/os-release | grep -E 'PRETTY_NAME|VERSION_ID'
```

## 2. 系统软件包

### 2.1 必装

| 软件包 | 版本 | 来源 | 用途 |
|---|---|---|---|
| `msodbcsql18` | 18.6.2.1+ | Microsoft prod 源 | ODBC Driver 18 |
| `mssql-tools18` | 18.6.2.1+ | Microsoft prod 源 | sqlcmd + bcp |
| `unixodbc` | 2.3.12+ | Ubuntu 官方源 | ODBC 运行时 |
| `unixodbc-dev` | 2.3.12+ | Ubuntu 官方源 | ODBC 开发头文件 |
| `curl` | 8+ | 系统自带 | 下载 Microsoft 源 |
| `gnupg` | 系统自带 | Ubuntu 官方源 | 验证软件源签名 |

### 2.2 选装（推荐）

| 软件包 | 用途 |
|---|---|
| `smbclient` | 访问 Windows SMB 共享备份目录 |
| `cifs-utils` | 挂载 Windows 共享到 Linux |
| `pandoc` | 文档转换（halo-rest 集成）|

### 2.3 验证已安装

```bash
dpkg -l | grep -iE 'msodbc|mssql-tools|unixodbc|smbclient|cifs-utils' \
  | awk '{print $1, $2, $3}'
```

期望输出（全 `ii` 状态）：

```text
ii cifs-utils                 2:7.0-2ubuntu0.2
ii libsmbclient0:amd64        2:4.19.5+dfsg-4ubuntu9.6
ii msodbcsql18                18.6.2.1-1
ii mssql-tools18              18.6.2.1-1
ii smbclient                  2:4.19.5+dfsg-4ubuntu9.6
ii unixodbc                   2.3.12-1ubuntu0.24.04.1
ii unixodbc-common            2.3.12-1ubuntu0.24.04.1
ii unixodbc-dev:amd64         2.3.12-1ubuntu0.24.04.1
```

## 3. 安装步骤（从零）

### 3.1 配置 Microsoft 软件源

```bash
mkdir -p ~/workspaces/download && cd ~/workspaces/download

# 适配 24.04
curl -fsSLO https://packages.microsoft.com/config/ubuntu/24.04/packages-microsoft-prod.deb

sudo dpkg -i packages-microsoft-prod.deb
sudo apt-get update
```

> 💡 22.04 把 URL 中的 `24.04` 改成 `22.04`。

### 3.2 安装核心包

```bash
sudo ACCEPT_EULA=Y apt-get install -y \
  msodbcsql18 \
  mssql-tools18 \
  unixodbc \
  unixodbc-dev \
  smbclient \
  cifs-utils
```

`ACCEPT_EULA=Y` 用于自动同意 Microsoft EULA。

### 3.3 将 sqlcmd 加入 PATH

```bash
echo 'export PATH="$PATH:/opt/mssql-tools18/bin"' >> ~/.bashrc
source ~/.bashrc
```

或者直接使用本技能提供的 `mssql` 包装命令（详见 commands.md），无需配 PATH。

### 3.4 验证安装

```bash
/opt/mssql-tools18/bin/sqlcmd -? | head -3
# Microsoft (R) SQL Server Command Line Tool
# Version 18.6.0002.1 Linux
# Copyright (C) 2017 Microsoft Corporation. All rights reserved.

odbcinst -q -d
# [ODBC Driver 18 for SQL Server]
```

## 4. OpenSSL 配置依赖（核心难点）

### 4.1 问题背景

- Ubuntu 24.04 自带 OpenSSL 3.x，默认 `MinProtocol = TLSv1.2`、`SECLEVEL = 2`
- SQL Server 2012 RTM 最高仅支持 TLS 1.0
- 直接连接会报 `SSL Provider: [error:0A000102:SSL routines::unsupported protocol]`

### 4.2 解决方案：OPENSSL_CONF 隔离

**绝对不要修改 `/etc/ssl/openssl.cnf`**，那是系统全局配置，改了 curl/git/apt 等全部受影响。

创建专用配置文件：

```bash
mkdir -p ~/workspaces/sqlremote/conf
cp /etc/ssl/openssl.cnf ~/workspaces/sqlremote/conf/openssl-sqlserver.cnf

# 在 [openssl_init] 段下加 ssl_conf 引用
sed -i '/^providers = provider_sect/a ssl_conf = ssl_sect' \
  ~/workspaces/sqlremote/conf/openssl-sqlserver.cnf

# 在文件末尾追加 TLS 1.0 兼容配置
cat >> ~/workspaces/sqlremote/conf/openssl-sqlserver.cnf <<'CFG'

# === Allow legacy TLSv1 for SQL Server 2012 RTM ===
[ssl_sect]
system_default = system_default_sect

[system_default_sect]
MinProtocol = TLSv1
CipherString = DEFAULT@SECLEVEL=0
CFG
```

### 4.3 验证隔离效果

```bash
# 测试 1：系统默认仍然严格
echo | openssl s_client -connect packages.microsoft.com:443 -tls1 2>&1 | grep -E 'error|no protocols'
# 期望：no protocols available（拒绝 TLS 1.0）

# 测试 2：专用配置允许 TLS 1.0
OPENSSL_CONF=~/workspaces/sqlremote/conf/openssl-sqlserver.cnf \
  echo | openssl s_client -connect 192.0.2.10:1433 -tls1 2>&1 | grep CONNECTED
# 期望：CONNECTED(...)

# 测试 3：curl 等其他工具保持严格 TLS
curl -sI https://packages.microsoft.com/ | head -1
# 期望：HTTP/2 200
```

## 5. 凭据文件

### 5.1 .env 格式

文件位置：`~/workspaces/sqlremote/.env`

```text
msuser=sql_backup_operator
mskey=你的密码
```

### 5.2 权限

```bash
chmod 600 ~/workspaces/sqlremote/.env
ls -l ~/workspaces/sqlremote/.env
# -rw------- 1 user user ... .env
```

> ⚠️ 生产环境强烈建议建专用账号（如 `sql_backup_operator`），权限仅 `db_backupoperator` 或 `db_owner`，避免使用 `sa`。

## 6. 用户权限

### 6.1 sudo NOPASSWD（可选）

如果需要在自动化脚本里安装/升级软件包，配置 sudo NOPASSWD：

```bash
sudo tee /etc/sudoers.d/$(whoami)-mssql > /dev/null <<'EOF'
youruser ALL=(ALL) NOPASSWD: /usr/bin/apt-get, /usr/bin/dpkg
EOF
sudo chmod 0440 /etc/sudoers.d/$(whoami)-mssql
```

### 6.2 普通用户读写权限

确保用户对以下目录有读写权限：

- `~/workspaces/sqlremote/`（含子目录）
- `~/.local/bin/`（mssql 包装命令安装位置）

## 7. 网络连通性

### 7.1 出站规则

```bash
# 测试 TCP 1433 可达
nc -vz 192.0.2.10 1433
# 期望：Connection to 192.0.2.10 1433 port [tcp/*] succeeded!
```

如果不通：

- 检查 Windows 防火墙是否放行 1433
- 检查 SQL Server 是否启用 TCP/IP 协议（SQL Server Configuration Manager）
- 检查是否监听具体 IP 而不是仅 127.0.0.1

### 7.2 端口清单

| 端口 | 协议 | 用途 |
|---|---|---|
| 1433 | TCP | SQL Server 默认 |
| 1434 | UDP | SQL Browser（命名实例需要）|
| 445 | TCP | SMB/CIFS（备份文件同步用）|
| 139 | TCP | NetBIOS（老 Windows 共享）|

## 8. 磁盘空间

| 用途 | 建议预留 |
|---|---|
| msodbcsql18 + mssql-tools18 安装 | ~50 MB |
| `~/workspaces/sqlremote/logs/` | ≥ 1 GB（日志文件累积）|
| `~/workspaces/sqlremote/reports/` | ≥ 500 MB |
| 临时 SMB 挂载备份文件 | 视业务库大小决定 |

## 9. 一键检查脚本

参考 `scripts/check-prereqs.sh`，会依次检查：

1. OS 版本
2. 必装包是否齐全
3. sqlcmd 是否可执行
4. ODBC 驱动是否注册
5. `~/workspaces/sqlremote/` 目录结构
6. `.env` 文件存在且权限正确
7. `openssl-sqlserver.cnf` 存在
8. `mssql` 包装命令在 PATH
9. 网络 1433 端口可达

```bash
bash ~/workspaces/skills/mssql-legacy/scripts/check-prereqs.sh
```

## 10. 依赖关系图

```text
mssql 包装命令
    ├── ~/.local/bin/mssql      # 包装脚本
    ├── 读取 .env               # 凭据
    ├── 设置 OPENSSL_CONF       # 专用 TLS 配置
    │      └── openssl-sqlserver.cnf
    │             ├── 复制自 /etc/ssl/openssl.cnf
    │             └── 追加 TLS 1.0 兼容段
    └── 调用 sqlcmd
           └── /opt/mssql-tools18/bin/sqlcmd  # mssql-tools18 包提供
                  └── 依赖 ODBC Driver 18      # msodbcsql18 包提供
                         └── 依赖 unixODBC     # unixodbc 包提供
```
