-- 03_check_log_size.sql
-- 查询所有数据库的日志文件大小（按大小降序）
SELECT
  DB_NAME(database_id) AS db,
  name AS logical_name,
  size * 8 / 1024 AS size_mb,
  physical_name
FROM sys.master_files
WHERE type_desc = 'LOG'
ORDER BY size DESC;
GO

-- 同时查询日志使用率
DBCC SQLPERF(LOGSPACE);
GO
