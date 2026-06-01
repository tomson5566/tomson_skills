# 故障排查

## 1. SSL/TLS 错误

### 1.1 `SSL Provider: [error:0A000102:SSL routines::unsupported protocol]`

**原因**：未加载 `OPENSSL_CONF`，OpenSSL 3 拒绝 TLS 1.0。

**排查**：
```bash
# 确认 OPENSSL_CONF 是否设置
env | grep OPENSSL_CONF

# 确认配置文件存在
ls -l ~/workspaces/sqlremote/conf/openssl-sqlserver.cnf

# 确认 ssl_conf 行在正确位置
grep -A3 '^\[openssl_init\]' ~/workspaces/sqlremote/conf/openssl-sqlserver.cnf
```

**修复**：使用 `mssql` 包装命令，或在 sqlcmd 前显式设置：
```bash
OPENSSL_CONF=~/workspaces/sqlremote/conf/openssl-sqlserver.cnf sqlcmd ...
```

### 1.2 `SSL Provider: [error:1416F086:SSL routines:tls_process_server_certificate:certificate verify failed]`

**原因**：服务器证书不受信任，缺少 `-C` 参数。

**修复**：sqlcmd 加 `-C` 参数（mssql 包装已内置）。

## 2. 连接错误

### 2.1 `Login timeout expired`

**排查**：
```bash
# 端口可达性
nc -vz 192.0.2.10 1433

# 服务器是否在线
ping 192.0.2.10
```

**修复**：
- 检查 Windows 防火墙
- 检查 SQL Server 是否启用 TCP/IP（SQL Server Configuration Manager）
- 增加超时：sqlcmd 加 `-l 30`

### 2.2 `Login failed for user 'xxx'`

**排查**：
```bash
# 确认 .env 凭据
cat ~/workspaces/sqlremote/.env

# 手动测试
sqlcmd -S 192.0.2.10 -U sql_backup_operator -P '密码' -C -Q "SELECT 1"
```

**修复**：
- 确认密码无特殊字符引号问题
- 确认账号未被锁定/禁用
- 在 Windows 端 SSMS 用同样账号测试

### 2.3 `Cannot generate SSPI context`

**原因**：使用 Windows 集成认证但环境不支持。

**修复**：明确用 SQL Server 账号 + `-U` `-P`，不使用集成认证。

## 3. 权限错误

### 3.1 `Cannot open database "XXX" requested by the login`

**修复**：账号无该库访问权限。在 SSMS 端授权：
```sql
USE [XXX];
CREATE USER [sql_backup_operator] FOR LOGIN [sql_backup_operator];
EXEC sp_addrolemember 'db_backupoperator', 'sql_backup_operator';
```

### 3.2 `BACKUP DATABASE permission denied`

**修复**：授予备份权限：
```sql
USE [XXX];
EXEC sp_addrolemember 'db_backupoperator', 'sql_backup_operator';
```

### 3.3 `Operating system error 5(Access is denied.)` 备份时

**原因**：SQL Server 服务账号对备份目录无写权限。

**修复**：在 Windows 端给 SQL Server 服务账号（NT SERVICE\MSSQLSERVER 或 SYSTEM）授予备份目录的读写权限。

## 4. 性能问题

### 4.1 备份特别慢

**排查**：
```sql
-- 查看当前备份进度
SELECT
  r.session_id,
  r.command,
  r.percent_complete,
  r.estimated_completion_time / 1000 / 60 AS eta_minutes
FROM sys.dm_exec_requests r
WHERE r.command LIKE 'BACKUP%' OR r.command LIKE 'RESTORE%';
```

**修复**：
- 加 `COMPRESSION` 减少 I/O
- 用 `MAXTRANSFERSIZE = 4194304, BUFFERCOUNT = 50` 调优
- 检查目标盘 I/O 性能

### 4.2 SHRINKFILE 卡住

**原因**：SHRINKFILE 期间会阻塞写入，且性能较差。

**建议**：
- 不在业务高峰执行
- 分批小步收缩：`DBCC SHRINKFILE (xxx, 4096)`、`DBCC SHRINKFILE (xxx, 2048)`
- 收缩后建议执行 `ALTER INDEX ALL ON [table] REBUILD` 重建索引（消除碎片）

## 5. mssql 包装命令问题

### 5.1 `command not found: mssql`

```bash
# 检查文件存在
ls -l ~/.local/bin/mssql

# 检查 PATH
echo $PATH | tr ':' '\n' | grep -i local

# 重新加载
source ~/.bashrc
```

### 5.2 包装命令报 `❌ 缺少密码`

```bash
# 检查 .env
ls -l ~/workspaces/sqlremote/.env
cat ~/workspaces/sqlremote/.env

# 应该有：
# msuser=sql_backup_operator
# mskey=你的密码
```

### 5.3 包装命令报 `❌ 专用 OpenSSL 配置不存在`

按 [prerequisites.md](prerequisites.md) 第 4 节重新生成 `openssl-sqlserver.cnf`。

## 6. 日志与审计

### 6.1 查看 sqlcmd 详细错误

加 `-r0` 让错误也输出到 stderr：
```bash
mssql -r0 -Q "SELECT 1" 2> /tmp/sqlcmd_error.log
```

### 6.2 启用 ODBC trace（极端调试）

```bash
sudo tee -a /etc/odbcinst.ini <<'EOF'
[ODBC]
Trace=Yes
TraceFile=/tmp/odbc_trace.log
EOF

# 跑一次 mssql 命令后查看
tail -100 /tmp/odbc_trace.log

# 调试完关闭 trace
sudo sed -i '/^Trace=Yes/d;/^TraceFile=/d' /etc/odbcinst.ini
```
