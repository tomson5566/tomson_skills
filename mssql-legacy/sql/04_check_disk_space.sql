-- 04_check_disk_space.sql
-- 查询磁盘剩余空间和数据文件占用
PRINT '===== 磁盘剩余空间 (MB) =====';
EXEC xp_fixeddrives;
GO

PRINT '===== 数据文件 Top 20 =====';
SELECT TOP 20
  DB_NAME(database_id) AS db,
  type_desc,
  name AS logical_name,
  size * 8 / 1024 AS size_mb,
  physical_name
FROM sys.master_files
WHERE database_id > 4   -- 排除系统库
ORDER BY size DESC;
GO
