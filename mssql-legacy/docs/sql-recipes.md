# 常用运维 SQL 速查

> 📌 本文档收集 SQL Server 2012 远程管理常用 SQL，可直接用 `mssql -Q "..."` 或 `mssql -i xxx.sql` 执行。

## 1. 健康检查

### 1.1 查询版本

```sql
SELECT @@VERSION AS version_info;
```

### 1.2 查询所有数据库及恢复模式

```sql
SELECT name, recovery_model_desc, state_desc
FROM sys.databases
ORDER BY name;
```

### 1.3 查询所有数据文件和日志文件大小

```sql
SELECT
  DB_NAME(database_id) AS db,
  name,
  type_desc,
  size * 8 / 1024 AS size_mb,
  CASE WHEN max_size = -1 THEN 'UNLIMITED'
       ELSE CAST(max_size * 8 / 1024 AS VARCHAR(20)) + ' MB'
  END AS max_size,
  physical_name
FROM sys.master_files
ORDER BY size DESC;
```

### 1.4 查询连接数

```sql
SELECT
  DB_NAME(dbid) AS db,
  COUNT(*) AS connections,
  loginame
FROM sys.sysprocesses
WHERE dbid > 0
GROUP BY dbid, loginame
ORDER BY connections DESC;
```

### 1.5 查询正在运行的查询

```sql
SELECT
  r.session_id,
  r.start_time,
  r.status,
  r.command,
  DB_NAME(r.database_id) AS db,
  r.wait_type,
  r.wait_time,
  SUBSTRING(t.text, r.statement_start_offset/2+1,
    (CASE WHEN r.statement_end_offset = -1
          THEN LEN(CONVERT(NVARCHAR(MAX), t.text)) * 2
          ELSE r.statement_end_offset END - r.statement_start_offset)/2+1) AS sql_text
FROM sys.dm_exec_requests r
CROSS APPLY sys.dm_exec_sql_text(r.sql_handle) t
WHERE r.session_id > 50;
```

## 2. 日志治理

### 2.1 FULL 恢复模式日志截断

> ⚠️ 必须先做日志备份，才能让 .ldf 空间被复用。

```sql
USE [HR];
GO
-- 1. 备份日志（实际写到磁盘，做完整 LSN 链）
BACKUP LOG [HR]
TO DISK = N'D:\backup\HR_log_20260529.trn'
WITH INIT, COMPRESSION;
GO
-- 2. 备份完后，空间会被自动标记可复用
-- 此时 .ldf 物理文件大小不变，只是内部空间被释放
```

### 2.2 SIMPLE 恢复模式日志清理

SIMPLE 模式不需要 BACKUP LOG，定期 CHECKPOINT 即可：

```sql
USE [XCERP];
GO
CHECKPOINT;
GO
```

### 2.3 收缩日志文件（仅治理异常膨胀）

> ⚠️ DBCC SHRINKFILE 会引起索引碎片，**不应日常化**。仅当日志文件异常膨胀时使用。

```sql
USE [XCERP];
GO
-- 收缩到 2048 MB（不要直接收到 0）
DBCC SHRINKFILE (XCERP_log, 2048);
GO
-- 查询收缩后大小
SELECT name, size * 8 / 1024 AS size_mb
FROM sys.database_files
WHERE type_desc = 'LOG';
GO
```

### 2.4 查询日志使用率

```sql
DBCC SQLPERF(LOGSPACE);
```

输出列：`Database Name`、`Log Size (MB)`、`Log Space Used (%)`、`Status`

## 3. 备份触发

### 3.1 完整备份（FULL）

```sql
BACKUP DATABASE [HR]
TO DISK = N'D:\backup\20260529\HR_full.bak'
WITH
  INIT,                         -- 覆盖已有文件
  COMPRESSION,                  -- 压缩备份（节省 60%+ 空间）
  CHECKSUM,                     -- 校验和
  STATS = 10,                   -- 每 10% 输出进度
  NAME = N'HR-Full-20260529',
  DESCRIPTION = N'Weekly full backup';
GO
```

### 3.2 差异备份（DIFF）

```sql
BACKUP DATABASE [HR]
TO DISK = N'D:\backup\20260529\HR_diff.bak'
WITH DIFFERENTIAL, INIT, COMPRESSION, CHECKSUM, STATS = 10;
GO
```

### 3.3 日志备份（LOG）

```sql
BACKUP LOG [HR]
TO DISK = N'D:\backup\20260529\HR_log.trn'
WITH INIT, COMPRESSION, CHECKSUM;
GO
```

### 3.4 验证备份有效性

```sql
-- 列出备份头信息
RESTORE HEADERONLY FROM DISK = N'D:\backup\20260529\HR_full.bak';

-- 验证备份可恢复性（不实际还原）
RESTORE VERIFYONLY FROM DISK = N'D:\backup\20260529\HR_full.bak'
WITH CHECKSUM;
```

### 3.5 查询备份历史

```sql
SELECT TOP 50
  bs.database_name,
  bs.backup_start_date,
  bs.backup_finish_date,
  bs.type,                    -- D=Full, I=Diff, L=Log
  bs.backup_size / 1024 / 1024 AS size_mb,
  bs.compressed_backup_size / 1024 / 1024 AS compressed_mb,
  bmf.physical_device_name
FROM msdb.dbo.backupset bs
JOIN msdb.dbo.backupmediafamily bmf ON bs.media_set_id = bmf.media_set_id
ORDER BY bs.backup_start_date DESC;
```

## 4. 磁盘空间

### 4.1 查询所有数据文件占用

```sql
SELECT
  DB_NAME(database_id) AS db,
  type_desc,
  name AS logical_name,
  physical_name,
  size * 8 / 1024 AS size_mb,
  FILEPROPERTY(name, 'SpaceUsed') * 8 / 1024 AS used_mb,
  (size - FILEPROPERTY(name, 'SpaceUsed')) * 8 / 1024 AS free_mb
FROM sys.master_files
WHERE database_id > 4  -- 排除系统库
ORDER BY size DESC;
```

> ⚠️ `FILEPROPERTY` 仅对当前数据库的文件返回有效值，跨库查会返回 NULL。

### 4.2 查询磁盘剩余空间（SQL 2012+）

```sql
EXEC xp_fixeddrives;
-- 返回每个盘符的剩余 MB
```

### 4.3 查询表空间占用 Top 20

```sql
USE [HR];
GO
SELECT TOP 20
  t.name AS table_name,
  s.name AS schema_name,
  p.rows AS row_count,
  SUM(a.total_pages) * 8 / 1024 AS total_mb,
  SUM(a.used_pages) * 8 / 1024 AS used_mb
FROM sys.tables t
JOIN sys.schemas s ON t.schema_id = s.schema_id
JOIN sys.indexes i ON t.object_id = i.object_id
JOIN sys.partitions p ON i.object_id = p.object_id AND i.index_id = p.index_id
JOIN sys.allocation_units a ON p.partition_id = a.container_id
WHERE i.index_id <= 1
GROUP BY t.name, s.name, p.rows
ORDER BY total_mb DESC;
```

## 5. 安全管理

### 5.1 创建专用备份账号

```sql
USE [master];
GO
-- 创建登录
CREATE LOGIN [sql_backup_operator]
WITH PASSWORD = N'强密码',
     CHECK_POLICY = ON,
     CHECK_EXPIRATION = OFF;
GO

-- 对每个目标库授予 db_backupoperator
USE [HR];
GO
CREATE USER [sql_backup_operator] FOR LOGIN [sql_backup_operator];
EXEC sp_addrolemember 'db_backupoperator', 'sql_backup_operator';
GO
```

### 5.2 查询所有登录账号

```sql
SELECT name, type_desc, is_disabled, create_date, modify_date
FROM sys.server_principals
WHERE type IN ('S', 'U')  -- S=SQL Login, U=Windows User
ORDER BY name;
```

### 5.3 查询账号权限

```sql
-- 服务器级别角色
SELECT sp.name AS login_name, srm.role_principal_id, sr.name AS role_name
FROM sys.server_principals sp
LEFT JOIN sys.server_role_members srm ON sp.principal_id = srm.member_principal_id
LEFT JOIN sys.server_principals sr ON srm.role_principal_id = sr.principal_id
WHERE sp.type IN ('S', 'U');

-- 数据库级别角色
USE [HR];
GO
SELECT dp.name AS user_name, drm.role_principal_id, dr.name AS role_name
FROM sys.database_principals dp
LEFT JOIN sys.database_role_members drm ON dp.principal_id = drm.member_principal_id
LEFT JOIN sys.database_principals dr ON drm.role_principal_id = dr.principal_id
WHERE dp.type IN ('S', 'U');
```

## 6. 一键巡检脚本

将下面这段保存为 `~/workspaces/sqlremote/sql/99_full_health_check.sql`，用 `mssql -i ... -o report.log` 跑：

```sql
PRINT '===== 1. 版本信息 =====';
SELECT @@VERSION;
GO

PRINT '===== 2. 数据库列表 =====';
SELECT name, recovery_model_desc, state_desc FROM sys.databases ORDER BY name;
GO

PRINT '===== 3. 数据文件 Top 20 =====';
SELECT TOP 20
  DB_NAME(database_id) AS db, name, type_desc,
  size * 8 / 1024 AS size_mb, physical_name
FROM sys.master_files
ORDER BY size DESC;
GO

PRINT '===== 4. 日志使用率 =====';
DBCC SQLPERF(LOGSPACE);
GO

PRINT '===== 5. 磁盘剩余空间 =====';
EXEC xp_fixeddrives;
GO

PRINT '===== 6. 最近 10 次备份 =====';
SELECT TOP 10
  database_name, backup_start_date, type,
  backup_size / 1024 / 1024 AS size_mb
FROM msdb.dbo.backupset
ORDER BY backup_start_date DESC;
GO
```
