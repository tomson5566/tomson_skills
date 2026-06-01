-- 02_check_databases.sql
-- 列出所有数据库及恢复模式
SELECT name, recovery_model_desc, state_desc
FROM sys.databases
ORDER BY name;
GO
