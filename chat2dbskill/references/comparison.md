# Chat2DB Local vs SQLX vs chat2db-cli 选型参考

> 基于本机实际验证（2026-10-10）

## 三工具能力矩阵

| | Chat2DB Local GUI + MCP | SQLX CLI | chat2db CLI |
|---|---|---|---|
| **启动方式** | Electron 桌面，VNC/云桌面可用 | 原生 CLI，headless 可用 | 原生 CLI，headless 可用 |
| **平台** | Linux ✅（Electron） | Linux ✅ 全功能 | Linux ⚠️ **阉割版** |
| **安装来源** | rpm：`chat2db-local-5.3.899` | zip：`sqlx 0.1.18` | CDN install script |
| **写操作（INSERT/UPDATE/DELETE）** | ❌ 被 AI guard 拦 | ✅ 完整支持 | ❌ unsupported_platform |
| **DDL（CREATE/DROP/ALTER）** | ❌ | ✅ | ❌ |
| **读操作（SELECT）** | ✅ | ✅ | ❌ |
| **数据源复用 GUI 配置** | ✅ | ❌ 需重新配 | ❌ |
| **38 种数据库** | ❌ 取决于 GUI 配置数 | ✅ | ❌ |
| **MCP 暴露** | ✅ 7 工具 | ✅ stdio MCP | ❌ |
| **预下载 worker** | N/A | `sqlx prefetch` | N/A |
| **Skill 名称** | `chat2db` | `sqlx` | `chat2db-cli` |

## Linux x64 平台实际验证结果

### chat2db CLI（OtterMind Rust CLI）

```bash
chat2db version --json      # ✅ 正常
chat2db status --json      # ✅ 正常（但 app: not_installed 误报）
chat2db db datasources      # ❌ unsupported_platform
chat2db sql query          # ❌ unsupported_platform
chat2db runtime start      # ❌ unsupported_platform
chat2db mcp enable        # ❌ unsupported_platform
```

**结论**：Linux 上只剩 status/version/update 等本地操作，数据库操作全不支持。OtterMind 未给 Linux 实现 backend 通信层。

### SQLX CLI（OtterMind 数据库 CLI）

```bash
sqlx datasource add --name test --type sqlite --database /tmp/test.db  # ✅
sqlx sql execute --datasource test --command "SELECT 1"               # ✅
sqlx prefetch sqlite                                                      # ✅
```

**结论**：Linux 全功能，跟 macOS/Windows 等价。

### Chat2DB Local MCP

```bash
# 模拟 MCP 调用（session init → tools/list）
curl -X POST http://127.0.0.1:11924/mcp \
  -H "X-Chat2DB-MCP-Token: xxxxxxxxxxxxxxxxxxxxxx" \
  -d '{"jsonrpc":"2.0","method":"initialize",...}'
# ✅ 200，返回 session id

# 实际工具调用
execute_sql SELECT...  # ✅ 返回结果
execute_sql INSERT...  # ❌ AI guard 拦截
```

**结论**：SELECT 完整，写操作被拦。

## 决策树

```
需要数据库操作？
├── 只读（SELECT/DESCRIBE/SHOW）
│   ├── Chat2DB GUI 里已配置数据源？
│   │   ├── 是 → 用 Chat2DB MCP（直接复用凭据，无须重配）
│   │   └── 否 → 用 SQLX（datasource add）
│   └── 是否需要 MCP 工具集成？
│       ├── 是 → Chat2DB MCP（新会话生效）
│       └── 否 → SQLX
│
└── 写操作（INSERT/UPDATE/DELETE/DDL）
    ├── 知道数据库密码？
    │   ├── 是 → 用 SQLX（完整 CRUD + approval 安全确认）
    │   └── 否，只有 Chat2DB GUI 里存着
    │       ├── 临时改 → 直接在 GUI 里跑
    │       └── 频繁改 → 把密码导出到 SQLX
    └── Headless Linux，无 GUI？
        └── 只能 SQLX
```

## 三者关系图

```
┌──────────────────────────────────────────┐
│         QwenPaw Agent                     │
│                                          │
│  ┌──────────────┐    ┌───────────────┐ │
│  │  chat2db MCP  │    │  sqlx CLI     │ │
│  │ (port 11924)  │    │ (native)      │ │
│  └──────┬───────┘    └──────┬────────┘ │
│          │                      │         │
│          ▼                      ▼         │
│  Chat2DB GUI        SQLX headless          │
│  Java Backend        worker               │
│  (SELECT only)      (full CRUD)          │
└──────────┬───────────────────────────────┘
            │
            ▼
      MySQL / PG / Redis / ...
```

## 凭据复用

Chat2DB GUI 存储的数据库密码可以通过 **datasource import** 导出给 SQLX 用：

1. 在 Chat2DB GUI → 连接管理 → 导出连接 JSON
2. SQLX import 格式（注意 `connection` 嵌套）：

```json
{
  "version": 1,
  "mode": "merge",
  "datasources": [{
    "name": "myds",
    "connection": {
      "database_type": "mysql",
      "host": "192.168.0.15",
      "port": 3306,
      "database": "db_sgcc_fj",
      "username": "your_user",
      "password": "your_pass"
    }
  }]
}
```

## 本机当前配置

| 数据源 | 在 Chat2DB GUI | 在 SQLX | MCP dataSourceId |
|---|---|---|---|
| `mysql-3.99` | ✅ | ❌ | `1775489845640536` |
| `@192.168.0.15` | ✅ | ❌ | `1782398519075536` |
| 本地 SQLite | ❌ | ✅（test-sqlite） | — |
