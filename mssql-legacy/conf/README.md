# openssl-sqlserver.cnf 模板说明

> 📌 此文件不应直接复制使用，而是在目标机器上从系统 `/etc/ssl/openssl.cnf` 复制后修改。

## 生成步骤

```bash
# 1. 从系统配置复制
cp /etc/ssl/openssl.cnf ~/workspaces/sqlremote/conf/openssl-sqlserver.cnf

# 2. 在 [openssl_init] 段下追加 ssl_conf 引用
sed -i '/^providers = provider_sect/a ssl_conf = ssl_sect' \
  ~/workspaces/sqlremote/conf/openssl-sqlserver.cnf

# 3. 在文件末尾追加 TLS 1.0 兼容段
cat >> ~/workspaces/sqlremote/conf/openssl-sqlserver.cnf <<'CFG'

# === Allow legacy TLSv1 for SQL Server 2012 RTM ===
[ssl_sect]
system_default = system_default_sect

[system_default_sect]
MinProtocol = TLSv1
CipherString = DEFAULT@SECLEVEL=0
CFG
```

## 追加内容解析

```ini
[ssl_sect]
system_default = system_default_sect
# 指定系统默认 SSL 配置段

[system_default_sect]
MinProtocol = TLSv1
# 允许 TLS 1.0 及以上（默认是 TLSv1.2，这里降到 1.0）

CipherString = DEFAULT@SECLEVEL=0
# SECLEVEL=0 允许所有密码套件（包括 SHA1、短密钥等）
# 默认 SECLEVEL=2 会拒绝这些弱算法
```

## 为什么不直接分发此文件

1. 系统 `openssl.cnf` 在不同 Ubuntu 版本间格式不同
2. 内置 provider 段、引擎段等可能与目标系统不匹配
3. 从当前系统复制能保证基础配置一致，只需追加 TLS 兼容段

## 清理方法

SQL Server 升级到支持 TLS 1.2 后，删除此文件并从 `mssql` 包装脚本中移除 `OPENSSL_CONF` 行即可。

```bash
rm ~/workspaces/sqlremote/conf/openssl-sqlserver.cnf
```
