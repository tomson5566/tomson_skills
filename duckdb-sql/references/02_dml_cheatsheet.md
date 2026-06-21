# DuckDB DML 速查 — INSERT / UPDATE / DELETE / MERGE / COPY

数据修改 + 数据导入导出。完整文档：https://duckdb.org/docs/current/sql/statements/

---

## INSERT — 插入

```sql
-- 多行 VALUES
INSERT INTO tbl VALUES (1, 'a'), (2, 'b'), (3, 'c');

-- 从查询插入
INSERT INTO tbl SELECT * FROM other_tbl;

-- 指定列（其他列填 DEFAULT）
INSERT INTO tbl (i) VALUES (1), (2), (3);
INSERT INTO tbl (i) VALUES (1), (DEFAULT), (3);  -- 显式 DEFAULT

-- 列名重排 + BY NAME（按名字匹配，不按位置）
INSERT INTO tbl BY NAME
SELECT 1 AS j, 2 AS i;  -- 即使 j, i 顺序与表相反
```

### 冲突处理（ON CONFLICT）

需要 UNIQUE / PRIMARY KEY 约束才生效：

```sql
-- 冲突时忽略（最常用）
INSERT INTO tbl (id, name) VALUES (1, 'a')
ON CONFLICT DO NOTHING;

-- 简写：INSERT OR IGNORE
INSERT OR IGNORE INTO tbl (id, name) VALUES (1, 'a');

-- 冲突时更新（upsert）
INSERT INTO tbl (id, name, count) VALUES (1, 'a', 10)
ON CONFLICT (id) DO UPDATE SET
  name = EXCLUDED.name,
  count = EXCLUDED.count;  -- EXCLUDED = 待插入行

-- 条件性 upsert
ON CONFLICT (id) DO UPDATE SET
  count = tbl.count + EXCLUDED.count
WHERE EXCLUDED.count > 0;

-- RETURNING 拿刚插入的行
INSERT INTO tbl VALUES (1, 'a') RETURNING *;
INSERT INTO tbl VALUES (1, 'a') RETURNING id, created_at;
```

---

## UPDATE — 更新

```sql
-- 单列
UPDATE tbl SET name = 'new' WHERE id = 1;

-- 多列
UPDATE tbl SET name = 'new', updated_at = current_timestamp WHERE id = 1;

-- 从其他表更新（UPDATE ... FROM）
UPDATE tbl
SET name = src.name
FROM other_tbl AS src
WHERE tbl.id = src.id;

-- 条件性更新
UPDATE orders SET status = 'archived'
WHERE created_at < current_date - INTERVAL '1 year'
  AND status != 'archived';

-- RETURNING
UPDATE tbl SET name = 'x' WHERE id = 1 RETURNING id, name;
```

---

## DELETE — 删除

```sql
-- 按条件删
DELETE FROM tbl WHERE status = 'cancelled' AND created_at < '2024-01-01';

-- 全删（慎用）
DELETE FROM tbl;

-- RETURNING
DELETE FROM tbl WHERE id = 1 RETURNING *;

-- 从另一表驱动删除
DELETE FROM tbl
USING other_tbl AS src
WHERE tbl.id = src.id AND src.to_delete = true;
```

---

## MERGE INTO — 复杂 upsert

**比 ON CONFLICT 更灵活**：不依赖主键，可自定义匹配条件，支持 WHEN MATCHED THEN UPDATE/DELETE + WHEN NOT MATCHED THEN INSERT：

```sql
-- 经典 upsert（按 id 匹配）
MERGE INTO target AS t
USING source AS s
  ON t.id = s.id
WHEN MATCHED THEN
  UPDATE SET name = s.name, updated_at = current_timestamp
WHEN NOT MATCHED THEN
  INSERT (id, name) VALUES (s.id, s.name);

-- 多动作：match 时按条件 delete or update
MERGE INTO people
USING (SELECT 3 AS id) AS deletes
USING (id)
WHEN MATCHED AND people.salary >= 100_000 THEN DELETE
WHEN MATCHED THEN UPDATE SET salary = salary * 1.1;

-- 整个 source 行的 update（无需 SET 逐列）
MERGE INTO target
USING source
ON target.id = source.id
WHEN MATCHED THEN UPDATE  -- 整行替换
WHEN NOT MATCHED THEN INSERT;
```

**用 MERGE 的场景**：
- 目标表无主键（ON CONFLICT 用不了）
- 需要按业务字段匹配（如 email、ts 范围）
- 一条 SQL 里既要 update 又要 delete 又要 insert

---

## COPY — 导入导出（**极重要**）

DuckDB 的招牌功能：直接 SQL 读写 CSV / Parquet / JSON，**零代码**。

### 导入 (FROM)

```sql
-- CSV：自动检测格式
COPY tbl FROM 'data.csv';

-- 显式 CSV 选项
COPY tbl FROM 'data.csv' (HEADER, DELIMITER '|', NULL 'NA', QUOTE '"');
COPY tbl FROM 'data.csv' (AUTO_DETECT true);  -- 强制自动检测

-- Parquet（自动用 Parquet schema）
COPY tbl FROM 'data.parquet' (FORMAT parquet);

-- JSON / NDJSON
COPY tbl FROM 'data.json' (FORMAT json, ARRAY true);   -- 顶层是 JSON 数组
COPY tbl FROM 'data.ndjson' (FORMAT json);            -- 每行一个 JSON（推荐）

-- 从 glob 导入（多个文件合一）
COPY tbl FROM 'data/*.csv' (HEADER);
COPY tbl FROM 'logs/2024-*/part-*.parquet';

-- 从查询结果加载（生成视图后立刻用）
COPY (SELECT * FROM read_csv_auto('raw/*.csv')) TO 'cleaned.parquet' (FORMAT PARQUET);

-- 只导入部分列
COPY tbl(name) FROM 'names.csv';  -- 其他列填 DEFAULT
```

### 导出 (TO)

```sql
-- CSV
COPY tbl TO 'out.csv' (HEADER, DELIMITER ',');

-- Parquet（带压缩）
COPY tbl TO 'out.parquet' (FORMAT PARQUET, COMPRESSION zstd);  -- zstd / snappy / gzip

-- NDJSON
COPY tbl TO 'out.ndjson' (FORMAT json);

-- 从查询结果导出
COPY (SELECT col1, col2 FROM tbl WHERE status = 'active')
TO 'active.parquet' (FORMAT PARQUET);

-- 按分区导出（Hive 风格目录）
COPY tbl TO 'out/year=2024/' (FORMAT PARQUET, PARTITION_BY (year));
```

### 跨数据库拷贝

```sql
-- 把 db1 整个拷到 db2
COPY FROM DATABASE db1 TO db2;

-- 只拷 schema 不拷数据
COPY FROM DATABASE db1 TO db2 (SCHEMA);
```

### COPY 选项速查（CSV）

| 选项 | 说明 | 默认 |
|---|---|---|
| `HEADER` / `HEADER false` | 首行是否列名 | 自动检测 |
| `DELIMITER` | 分隔符 | 自动检测 |
| `QUOTE` | 引号字符 | `"` |
| `ESCAPE` | 转义字符 | `\` |
| `NULL` / `NULLSTR` | NULL 字面量 | 空串 |
| `SKIP` | 跳过前 N 行 | 0 |
| `AUTO_DETECT` | 自动推断类型/schema | true |
| `SAMPLE_SIZE` | 自动检测时采样行数 | 20480 |
| `COMPRESSION` | 压缩 (gzip/zstd) | 自动 |
| `FORCE_NOT_NULL` | 强制某列不转 NULL | `[]` |

---

## ATTACH / DETACH — 挂载外部数据库

跨数据库查询是 DuckDB 一大杀器：

```sql
-- 挂载其他 .ddb 文件
ATTACH 'other.db' AS other;
ATTACH 'other.db' AS other (READ_ONLY);          -- 只读
ATTACH 'other.db' AS other (BLOCK_SIZE 16384);   -- 自定义块大小

-- 跨库查询
SELECT * FROM other.users WHERE active = true;

-- 跨库 JOIN
SELECT o.*, u.email
FROM local.orders o
JOIN other.users u ON o.user_id = u.id;

-- 跨库 COPY
COPY other.users TO 'users.csv' (HEADER);

-- 卸载
DETACH other;
```

**应用场景**：
- 大表冷热分离（热数据在主库，冷数据在归档 .ddb）
- 不改代码就接入新数据源
- 数据交换（临时挂一个 db 取数）

---

## EXPORT / IMPORT — 完整数据库导出为 SQL

```sql
-- 导出整个数据库为 SQL 脚本（含 schema + data）
EXPORT DATABASE 'dump_dir/';
-- 生成：dump_dir/schema.sql + dump_dir/load.sql

-- 指定格式
EXPORT DATABASE 'dump/' (FORMAT csv);
EXPORT DATABASE 'dump/' (FORMAT parquet);

-- 从 dump 恢复
IMPORT DATABASE 'dump_dir/';
```

**应用场景**：
- 备份小型 DuckDB
- 跨机器迁移数据
- 把数据打包发给同事

---

## 事务

DuckDB 默认自动 commit（每个 statement 一个事务）：

```sql
-- 显式事务
BEGIN;
INSERT INTO tbl VALUES (1, 2);
UPDATE tbl SET name = 'x' WHERE id = 1;
COMMIT;   -- 或 ROLLBACK;

-- 检查点
CHECKPOINT;
```

**注意**：DuckDB 的事务是**乐观并发**（optimistic），适合读多写少。写多并发场景考虑用 Postgres。
