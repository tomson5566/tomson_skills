# 迁移指南

> 📌 本文档是将 `mssql-legacy` 技能部署到新机器的完整步骤和避坑清单。

## 1. 迁移 5 步流程

### 步骤 1：安装客户端工具

按 [prerequisites.md](prerequisites.md) 第 3 节安装 msodbcsql18、mssql-tools18 等。

```bash
# 快速安装（Ubuntu 24.04）
curl -fsSLO https://packages.microsoft.com/config/ubuntu/24.04/packages-microsoft-prod.deb
sudo dpkg -i packages-microsoft-prod.deb
sudo apt-get update
sudo ACCEPT_EULA=Y apt-get install -y msodbcsql18 mssql-tools18 unixodbc unixodbc-dev smbclient cifs-utils
```

### 步骤 2：复制 skill 目录

```bash
# 从旧机器复制（或 git clone）
scp -r oldserver:~/workspaces/skills/mssql-legacy ~/workspaces/skills/

# 创建工作目录
mkdir -p ~/workspaces/sqlremote/{sql,scripts,conf,logs,reports}
```

### 步骤 3：创建凭据和 OpenSSL 配置

```bash
# 写入凭据
cat > ~/workspaces/sqlremote/.env <<'EOF'
msuser=sql_backup_operator
mskey=你的密码
EOF
chmod 600 ~/workspaces/sqlremote/.env

# 创建专用 OpenSSL 配置
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

### 步骤 4：安装 mssql 包装命令

```bash
cp ~/workspaces/skills/mssql-legacy/scripts/mssql-wrapper.sh ~/.local/bin/mssql
chmod +x ~/.local/bin/mssql

# 确保 PATH 包含 ~/.local/bin
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

### 步骤 5：验证

```bash
# 跑一键检查
bash ~/workspaces/skills/mssql-legacy/scripts/check-prereqs.sh

# 手动验证
mssql -Q "SELECT @@VERSION"
```

## 2. 避坑清单

| 坑 | 现象 | 解决 |
|---|---|---|
| 没改 `/etc/ssl/openssl.cnf` 但仍连不上 | 检查 `openssl-sqlserver.cnf` 的 `ssl_conf` 行是否在 `[openssl_init]` 段内 | `grep -A3 '^\[openssl_init\]' ~/workspaces/sqlremote/conf/openssl-sqlserver.cnf` |
| 修改了 `/etc/ssl/openssl.cnf` 导致系统 TLS 降级 | curl 能连不安全站点 | 回滚：`sudo cp -a /etc/ssl/openssl.cnf.bak /etc/ssl/openssl.cnf` |
| `.env` 权限太宽 | 其他用户可读密码 | `chmod 600 ~/workspaces/sqlremote/.env` |
| sqlcmd 报 `TrustServerCertificate` | ODBC Driver 18 默认强制加密 | 加 `-C` 参数（mssql 包装已内置）|
| 端口不通 | `Connection refused` 或超时 | 检查 Windows 防火墙 1433/TCP |
| 命名实例连不上 | 默认端口不是 1433 | 用 `-S 192.0.2.10\INSTANCENAME` 或指定端口 `-S 192.0.2.10,1434` |
| mssql 命令找不到 | `command not found` | 检查 `~/.local/bin` 是否在 PATH |
| OPENSSL_CONF 路径写错 | ssl 握手失败 | 用绝对路径，检查文件是否存在 |
| 备份路径不存在 | `Operating system error 3` | 在 SQL Server 端确保 `D:\backup\` 目录存在 |
| SHRINKFILE 报错 `File ID not found` | 逻辑名不对 | 先查 `SELECT name FROM sys.database_files WHERE type_desc='LOG'` |

## 3. 一键诊断脚本

```bash
#!/usr/bin/env bash
# mssql-legacy 诊断脚本
set -euo pipefail

PASS=0; FAIL=0

check() {
  local desc="$1" cmd="$2"
  if eval "$cmd" > /dev/null 2>&1; then
    echo "✅ $desc"
    ((PASS++))
  else
    echo "❌ $desc"
    ((FAIL++))
  fi
}

echo "=== mssql-legacy 诊断 ==="
echo

check "OS = Linux x86_64" "uname -m | grep -q x86_64"
check "msodbcsql18 已安装" "dpkg -s msodbcsql18 | grep -q 'Status: install ok installed'"
check "mssql-tools18 已安装" "dpkg -s mssql-tools18 | grep -q 'Status: install ok installed'"
check "sqlcmd 可执行" "[ -x /opt/mssql-tools18/bin/sqlcmd ]"
check "ODBC Driver 18 已注册" "odbcinst -q -d | grep -q 'ODBC Driver 18'"
check "sqlremote 目录存在" "[ -d ~/workspaces/sqlremote/conf ]"
check ".env 文件存在" "[ -f ~/workspaces/sqlremote/.env ]"
check ".env 权限 600" "[ \$(stat -c %a ~/workspaces/sqlremote/.env) = '600' ]"
check "openssl-sqlserver.cnf 存在" "[ -f ~/workspaces/sqlremote/conf/openssl-sqlserver.cnf ]"
check "mssql 命令在 PATH" "which mssql > /dev/null 2>&1 || [ -x ~/.local/bin/mssql ]"

echo
echo "=== 结果：$PASS 通过，$FAIL 失败 ==="
[ $FAIL -eq 0 ] && echo "🎉 全部通过，可以开始使用！" || echo "⚠️ 有 $FAIL 项需要修复"
```

## 4. 不同 SQL Server 版本适配

| SQL Server 版本 | 最高 TLS | 是否需要 OPENSSL_CONF 隔离 | 备注 |
|---|---|---|---|
| 2012 RTM | TLS 1.0 | ✅ 需要 | 本技能主要适配对象 |
| 2012 SP3+CU / SP4 | TLS 1.2 | ❌ 不需要 | 升级后可删除专用配置 |
| 2014+ | TLS 1.2 | ❌ 不需要 | 直接连即可，仍需 `-C` |
| 2016+ | TLS 1.2 | ❌ 不需要 | ODBC 18 直连 |
| 2019+ | TLS 1.2 / 1.3 | ❌ 不需要 | 最佳兼容 |

> 💡 如果 SQL Server 升级后支持 TLS 1.2，删除 `openssl-sqlserver.cnf` 并修改 `mssql` 包装脚本移除 `OPENSSL_CONF` 即可。

## 5. 不同 Linux 发行版适配

| 发行版 | Microsoft 源 URL | 测试状态 |
|---|---|---|
| Ubuntu 24.04 (noble) | `.../ubuntu/24.04/...` | ✅ 实测通过 |
| Ubuntu 22.04 (jammy) | `.../ubuntu/22.04/...` | ✅ 理论兼容 |
| Debian 12 (bookworm) | `.../debian/12/...` | 未测试 |
| RHEL 9 | `.../rhel/9/...` | 未测试（需 yum/dnf）|

> ⚠️ 非 Ubuntu 系的发行版，`openssl.cnf` 路径和格式可能不同，需要对应调整 `OPENSSL_CONF` 配置。

## 6. 卸载/清理

```bash
# 卸载客户端工具
sudo apt-get remove -y msodbcsql18 mssql-tools18 unixodbc-dev
sudo apt-get autoremove -y

# 清理工作目录
# ⚠️ 确认不再需要后执行
rm -rf ~/workspaces/sqlremote/

# 清理包装命令
rm ~/.local/bin/mssql

# 清理 skill 目录（可选）
rm -rf ~/workspaces/skills/mssql-legacy/

# 恢复 PATH（如需）
# 从 ~/.bashrc 删掉 /opt/mssql-tools18/bin 那行
```
