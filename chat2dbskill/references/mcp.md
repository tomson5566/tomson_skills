# Chat2DB Local MCP 工具参考

> MCP endpoint：`http://127.0.0.1:11924/mcp`
> Token：`efb7577ec7c344688dcabe267abea9ea`
> 配置文件：`drivers/mcp/chat2db.yaml`（QwenPaw MCP client）
> 前提：Chat2DB Local GUI 在运行

## 7 个 MCP 工具

### list_all_datasources

**输入**：无参数

**用途**：列出 Chat2DB 里所有已配置的数据源，返回 `dataSourceId`。

```json
// 返回示例
{
  "id": 1775489845640536, "name": "mysql-3.99", "type": "MYSQL"
}
{
  "id": 1782398519075536, "name": "@192.168.0.15", "type": "MYSQL"
}
```

---

### list_all_databases

**输入**：`dataSourceId`（integer，必填）

**用途**：列某数据源下的所有库。

```json
// 参数
{ "dataSourceId": 1782398519075536 }
```

MySQL 返回约 44 个库，包括 `db_sgcc_fj`、`tangzhiang`、`test`、`information_schema [SYSTEM]` 等。

---

### list_all_tables

**输入**：`dataSourceId`（int）、`databaseName`（string）

**用途**：列某库下所有表（含注释）。

```json
// 参数
{ "dataSourceId": 1782398519075536, "databaseName": "db_sgcc_fj" }

// 返回示例
app_service_r [TABLE] - 应用服务与能力关系表
app_service_role [TABLE] - 应用服务权限表
app_service_log [TABLE] - 服务能力访问日志表
```

---

### get_tables_schema

**输入**：`tableNames[]`、`dataSourceId`、`databaseName`

**用途**：获取指定表的完整 DDL。

```json
// 参数
{
  "tableNames": ["app_service_r"],
  "dataSourceId": 1782398519075536,
  "databaseName": "db_sgcc_fj"
}

// 返回
CREATE TABLE `app_service_r` (
  `ID` varchar(50) NOT NULL COMMENT '主键id',
  `APP_ID` varchar(50) DEFAULT NULL COMMENT '应用服务ID',
  `ABILITY_ID` varchar(500) DEFAULT NULL COMMENT '能力ID',
  PRIMARY KEY (`ID`) USING BTREE
) ENGINE=InnoDB DEFAULT CHARSET=utf8 ROW_FORMAT=COMPACT COMMENT='应用服务与能力关系表';
```

---

### execute_sql

**输入**：`sql`、`dataSourceId`、`databaseName`、`schemaName?`、`pageSize?`

**用途**：执行 SQL，返回结构化结果。

```json
// 参数
{
  "sql": "SELECT * FROM app_service_r LIMIT 3",
  "dataSourceId": 1782398519075536,
  "databaseName": "db_sgcc_fj"
}

// 返回
{
  "success": true,
  "sqlType": "SELECT",
  "durationMs": 7,
  "rows": 3,
  "hasNextPage": false,
  "columns": [["id","integer"], ["APP_ID","varchar"], ["ABILITY_ID","varchar"]],
  "data": [["1","app001","ability-001"], ...]
}
```

**写操作拦截**：INSERT/UPDATE/DELETE/CREATE/DROP 等全部被 AI guard 拦截，返回"需要人工确认"。

---

### text2sql

**输入**：`question`（string，必填）、`dataSourceId?`、`databaseName?`、`schemaName?`

**用途**：用 Chat2DB 内置 AI 把自然语言转成 SQL。**只返回 SQL，不执行**。

```json
// 参数
{
  "question": "list top 10 users ordered by created_at desc",
  "dataSourceId": 1782398519075536,
  "databaseName": "tangzhiang"
}
```

拿到 SQL 后，用 `execute_sql` 真正执行。

---

### list_all_schemas

**输入**：`targetDatabaseName`（string）、`dataSourceId`（int）

**用途**：列某库下的所有 schema（MySQL 通常返回 "No schemas found"，正常现象）。

---

## write 限制

| 操作 | 通过 MCP 能执行？ |
|---|---|
| SELECT | ✅ |
| SHOW / DESCRIBE / EXPLAIN | ✅ |
| INSERT / UPDATE / DELETE | ❌ 被 AI guard 拦 |
| CREATE / DROP / ALTER / TRUNCATE | ❌ 被 AI guard 拦 |
| GRANT / REVOKE | ❌ 被 AI guard 拦 |

需要写操作时用 **SQLX**（`sqlx sql execute`），详见 `references/comparison.md`。

## 常见错误

| 错误 | 原因 | 修复 |
|---|---|---|
| `MCP access requires a valid desktop MCP token` | 没带 token 或 token 过期 | GUI 重置 token，更新 `drivers/mcp/chat2db.yaml` |
| `Session ID missing` | 调工具前没先 initialize | QwenPaw MCP 客户端自动处理 |
| `No database selected` | `execute_sql` 缺 `databaseName` | 必填参数 |
| `Non-query SQL cannot be auto-executed` | 写了 INSERT 等 | 改数据走 SQLX |
| `dataSourceId is not an integer` | 传了 string | `dataSourceId` 是大整数如 `1782398519075536` |
