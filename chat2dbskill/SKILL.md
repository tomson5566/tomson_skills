---
name: chat2db
description: "Operate Chat2DB Local through its Electron GUI, built-in MCP endpoint (port 11924), and web API. Covers RPM installation and troubleshooting, MCP tools (list/get/execute_sql), AI-guard write restrictions, and when to switch to SQLX for full CRUD. For OtterMind's Rust CLI (chat2db CLI), use the chat2db-cli skill instead."
metadata:
  version: "1.0"
---

# Chat2DB Local

Operate Chat2DB Local through its Electron GUI, built-in MCP endpoint, and web API.

## First Step: Check GUI and MCP Availability

Before any operation, check whether the GUI and its MCP endpoint are available:

```bash
# Is the GUI running?
pgrep -fa chat2db-local

# Is port 11924 listening?
ss -tln | grep 11924

# If not running, start it:
chat2db-local
```

If the GUI is not installed, read `references/install.md` for RPM installation and startup instructions.

## MCP Endpoint

Chat2DB Local exposes an MCP endpoint at `http://127.0.0.1:11924/mcp` with token authentication. The QwenPaw MCP client is configured in `drivers/mcp/chat2db.yaml` (already set up with token `xxxxxxxxxxxxxxxxxxxxxxxxx`).

The MCP endpoint is available whenever the GUI is running. It provides **read-only** access to all configured datasources through 7 tools.

## MCP Tools

| Tool | Required Args | What It Does |
|---|---|---|
| `list_all_datasources` | — | List all Chat2DB datasources. Returns `dataSourceId` (integer). |
| `list_all_databases` | `dataSourceId` (int) | List databases in one datasource. |
| `list_all_schemas` | `targetDatabaseName`, `dataSourceId` | List schemas (MySQL usually returns "No schemas found"). |
| `list_all_tables` | `dataSourceId`, `databaseName` | List tables in one database. |
| `get_tables_schema` | `tableNames[]`, `dataSourceId`, `databaseName` | Get CREATE TABLE DDL for specified tables. |
| `text2sql` | `question` (string) | Convert natural language to SQL. Returns SQL only — does **not** execute. |
| `execute_sql` | `sql`, `dataSourceId`, `databaseName` | Execute SQL and return results. |

### dataSourceId Is an Integer

`dataSourceId` is a **large integer**, not a UUID or string. Example: `1782398519075536`.

### Typical Discovery Workflow

```
list_all_datasources
  → note the dataSourceId for the target datasource
    → list_all_databases(dataSourceId)
      → note the databaseName
        → list_all_tables(dataSourceId, databaseName)
          → note the tableName
            → get_tables_schema(tableNames=["<table>"], dataSourceId, databaseName)
              → review the DDL
                → execute_sql(sql="SELECT ...", dataSourceId, databaseName)
```

### execute_sql Returns

```json
{
  "success": true,
  "sqlType": "SELECT",
  "durationMs": 7,
  "rows": 10,
  "hasNextPage": false,
  "columns": [...],
  "data": [...]
}
```

Pagination: pass `pageSize` (default 200, max 500). If `hasNextPage: true`, there are more rows.

## Write Restriction (Critical)

The MCP endpoint has an **AI guard** that blocks all non-SELECT operations. Any `execute_sql` call with INSERT, UPDATE, DELETE, CREATE, DROP, TRUNCATE, ALTER, GRANT, etc. returns:

```
Non-query SQL cannot be auto-executed by AI and requires manual confirmation.
Detected SQL type(s): INSERT
Return the SQL to the user for manual review:
```

**SELECT-only through MCP.** For write operations, switch to SQLX.

## When to Use Chat2DB MCP vs SQLX

| Situation | Use |
|---|---|
| Read from an already-configured datasource | Chat2DB MCP (no re-configuration needed) |
| Write operations (INSERT/UPDATE/DELETE/CREATE/DROP) | **SQLX** (Chat2DB MCP blocks them) |
| Datasource not yet in Chat2DB GUI | SQLX (`sqlx datasource add`) |
| Headless Linux without GUI | **SQLX** (Chat2DB MCP requires GUI running) |
| You have DB password only in Chat2DB GUI | Chat2DB MCP (reuses GUI-stored credentials) |
| 38 database types needed | SQLX |

See `references/comparison.md` for the full comparison matrix.

## MCP Configuration

The MCP client configuration is at `drivers/mcp/chat2db.yaml`:

```yaml
name: chat2db
protocol: mcp
endpoint:
  transport: streamable_http
  url: http://127.0.0.1:11924/mcp
  headers:
    X-Chat2DB-MCP-Token: xxxxxxxxxxxxxxxxxxxxxxxx
enabled: true
policy:
  default_effect: deny      # ask before every call
  rules:
  - effect: ask
    target: { kind: tool, name: '*' }
    subject: '*'
    principal: { source_type: '*', source_value: '*', subject_type: '*', subject_value: '*' }
```

QwenPaw loads MCP configurations from `drivers/mcp/*.yaml` on session start. A new session is required after any configuration change.

## Known Datasources (Current Environment)

| dataSourceId | Name | Type |
|---|---|---|
| `1775489845640536` | `mysql-3.99` | MYSQL |
| `1782398519075536` | `@192.168.0.15` | MYSQL |

## Troubleshooting

For GUI startup issues (JVM not found, Chromium SingletonLock, cfg file missing), read `references/troubleshooting.md`.

For MCP connectivity issues (token errors, session errors), read `references/mcp.md`.

For the full tool comparison with SQLX, read `references/comparison.md`.
