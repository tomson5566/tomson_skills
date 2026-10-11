# Chat2DB Local — AI Agent Skill

> Operate Chat2DB Local through its Electron GUI, built-in MCP endpoint, and web API — for AI Agents running on Linux servers.

[![Platform](https://img.shields.io/badge/platform-Linux%20x64-blue)](#requirements)
[![Verified on](https://img.shields.io/badge/verified%20on-Rocky%2010%20%2F%20RHEL-brightgreen)](#requirements)
[![Chat2DB](https://img.shields.io/badge/chat2db--local-5.3.899-orange)](#environment)
[![License](https://img.shields.io/badge/license-Apache--2.0-lightgrey)](#license)

---

## Why this skill exists

Chat2DB Local is the AI-driven SQL client from OtterMind. When it runs on a Linux server, an AI Agent can either talk to it through the built-in **MCP HTTP endpoint on port 11924**, or use the **SQLX CLI** for full CRUD. This skill packages both:

- the **operational knowledge** — how to start the GUI, fix the two well-known RPM bugs (JVM path / Chromium SingletonLock on VNC), and read the runtime logs;
- the **protocol knowledge** — the 7 MCP tools, the AI-Guard write restrictions, and the discovery workflow;
- the **tool-selection knowledge** — when to stay on MCP, when to switch to SQLX, and when neither fits (use `chat2db-cli`, a separate skill).

Everything in this repo was verified on a real Rocky Linux 10 / OpenJDK 21 / VNC cloud-desktop environment before being checked in.

---

## ✨ Features

- 🚀 **Start Chat2DB Local on Linux** — including the two RPM packaging defects (`lib/app/runtime` not pointing to the embedded JRE; Chromium Profile lock on shared `$HOME`)
- 🔌 **MCP integration** — 7 read-only tools exposed at `http://127.0.0.1:11924/mcp`, with token auth
- 🤖 **AI-Guard aware** — knows when to refuse writes and switch to SQLX for safety
- 📊 **Three-tool decision matrix** — Chat2DB MCP vs SQLX CLI vs chat2db CLI
- 🧰 **Real-environment validated** — every command, dataSourceId, and fix script was executed on a real DB before being committed
- 🧠 **Skill-aware** — clearly states when to delegate to the sibling `sqlx` and `chat2db-cli` skills

---

## 📦 Requirements

| Item | Version |
|---|---|
| OS | Linux x86_64 (RHEL/Rocky family, OpenNebula / VNC cloud-desktop tested) |
| JDK | OpenJDK 21 (`/usr/lib/jvm/java-21-openjdk`) |
| Chat2DB Local | `chat2db-local-5.3.899-1.x86_64` (RPM) |
| Optional | `sqlx` ≥ 0.1.18 (for writes and headless Linux) |
| Optional | `chat2db-cli` (macOS / Windows GUI management only) |

---

## 🚀 Quick start

### 1. Make sure the GUI and MCP endpoint are alive

```bash
pgrep -fa chat2db-local || chat2db-local
ss -tln | grep 11924   # should show the listener
```

If the GUI is not installed, see [`references/install.md`](references/install.md) for the full RPM recipe.

### 2. Wire the MCP client

The MCP client reads its config on session start. A typical entry:

```yaml
# drivers/mcp/chat2db.yaml
name: chat2db
protocol: mcp
endpoint:
  transport: streamable_http
  url: http://127.0.0.1:11924/mcp
  headers:
    X-Chat2DB-MCP-Token: <YOUR_TOKEN>
enabled: true
policy:
  default_effect: deny      # ask before every call
  rules:
    - effect: ask
      target: { kind: tool, name: '*' }
      subject: '*'
      principal: { source_type: '*', source_value: '*', subject_type: '*', subject_value: '*' }
```

> Restart the agent session after any change to `drivers/mcp/*.yaml` — configs are read once on boot.

### 3. Follow the standard discovery workflow

```
list_all_datasources
  → note the dataSourceId (large integer, e.g. 1782398519075536)
    → list_all_databases(dataSourceId)
      → note the databaseName
        → list_all_tables(dataSourceId, databaseName)
          → note the tableName
            → get_tables_schema(tableNames=["<table>"], dataSourceId, databaseName)
              → review the DDL
                → execute_sql(sql="SELECT ...", dataSourceId, databaseName)
```

For a one-call natural-language alternative, use `text2sql(question=...)` first — it returns SQL only and **does not execute**. Then run it through `execute_sql` once you have reviewed it.

---

## 🛠️ The 7 MCP tools

| Tool | Required args | Returns / notes |
|---|---|---|
| `list_all_datasources` | — | List of `{id, name, type}`; `id` is a **large integer** |
| `list_all_databases` | `dataSourceId` (int) | Databases inside one datasource |
| `list_all_schemas` | `targetDatabaseName`, `dataSourceId` | Schemas — MySQL usually returns `No schemas found` |
| `list_all_tables` | `dataSourceId`, `databaseName` | Tables with Chinese-name comments when present |
| `get_tables_schema` | `tableNames[]`, `dataSourceId`, `databaseName` | Full `CREATE TABLE` DDL |
| `text2sql` | `question` (string) | Generates SQL; **does not execute** |
| `execute_sql` | `sql`, `dataSourceId`, `databaseName`, `schemaName?`, `pageSize?` | Result rows + columns; paginated at 200 (max 500) |

Full reference with examples: [`references/mcp.md`](references/mcp.md).

---

## ⚠️ Critical: AI-Guard blocks all writes

The MCP endpoint has a built-in **AI guard** that refuses any non-SELECT statement. Inserting, updating, deleting, or any DDL through `execute_sql` returns:

```
Non-query SQL cannot be auto-executed by AI and requires manual confirmation.
Detected SQL type(s): INSERT
```

| Operation | Allowed via MCP? |
|---|---|
| `SELECT` / `SHOW` / `DESCRIBE` / `EXPLAIN` | ✅ |
| `INSERT` / `UPDATE` / `DELETE` | ❌ AI guard |
| `CREATE` / `DROP` / `ALTER` / `TRUNCATE` | ❌ AI guard |
| `GRANT` / `REVOKE` | ❌ AI guard |

**For any write or DDL work, switch to the [`sqlx`](../sqlx/) skill** — it has no AI guard and supports 38 database engines.

---

## 🔀 When to use what

| Situation | Use |
|---|---|
| Read from a datasource already configured in the GUI | **chat2db MCP** — reuses stored credentials, no re-config |
| Write / DDL needed | **SQLX** — MCP blocks it |
| Datasource not yet in Chat2DB GUI | **SQLX** — `sqlx datasource add` |
| Headless Linux, no GUI | **SQLX** — MCP needs the GUI running |
| Password only lives in Chat2DB GUI | **chat2db MCP** — can't easily extract it |
| Need 38+ database engines | **SQLX** |
| macOS / Windows GUI lifecycle (install / update / launch) | **chat2db-cli** (separate skill) |

Full matrix and decision tree: [`references/comparison.md`](references/comparison.md).

---

## 🗂️ Project structure

```
chat2db/
├── SKILL.md                 # Main entry — read this first
└── references/
    ├── install.md           # RPM install, paths, startup, ops commands
    ├── troubleshooting.md   # JVM, Chromium lock, cfg-file, log-reading recipes
    ├── mcp.md               # Detailed 7-tool reference with request/response samples
    └── comparison.md        # Chat2DB MCP vs SQLX vs chat2db-cli decision matrix
```

---

## 🔧 Environment reference

| Item | Value |
|---|---|
| RPM package | `chat2db-local-5.3.899-1.x86_64` |
| Install root | `/opt/chat2db-local/chat2db-local/` |
| Startup binary | `bin/chat2db` (renamed from `Chat2DB Local` — see troubleshooting) |
| Embedded JRE (key!) | `lib/runtime/bin/` (the `lib/app/runtime/` referenced by the launcher is empty) |
| System Java fallback | `/usr/lib/jvm/java-21-openjdk` |
| JCEF profile lock (Local) | `~/.chat2db_local_edition/chat2db_cache_local/` |
| JCEF profile lock (Community) | `~/.chat2db-community/chat2db_cache_community/` |
| MCP endpoint | `http://127.0.0.1:11924/mcp` |
| MCP client config | `drivers/mcp/chat2db.yaml` |
| Run log | `/opt/chat2db-local/chat2db-local/bin/debug.log` |

---

## ⚠️ Common pitfalls on Linux

1. **`Failed to find JVM in .../lib/app/runtime`** — the RPM does **not** embed a JRE under `lib/app/runtime/` (that directory holds the application's `chat2db-studio.jar`, `dist/`, and `lib/`). Either patch the launcher's JVM path to `/usr/lib/jvm/java-21-openjdk`, or wrap the binary in a script that `export JAVA_HOME=...` and `exec chat2db`. Do **not** try `sed -i` on the binary itself — it's an ELF.
2. **`其他计算机 (openNebula) ... CefApp: N_Initialize failed`** — Chromium on VNC sees the cloud-desktop hostname (`openNebula`, `qwenpaw`, etc.) as a different machine and refuses the cached profile. Kill residual processes, delete **only** `~/.chat2db_local_edition/chat2db_cache_local/Singleton*` (don't touch `~/.local/share/browseract/` or `~/.copaw/...`), and start with an isolated `HOME=~/chat2db-home`.
3. **`Error opening .../chat2db.cfg`** — the original binary name contains a space (`Chat2DB Local`) and the launcher trims on whitespace to compute the cfg path. Either rename the binary to `chat2db` / `chat2db-local`, or copy `Chat2DB Local.cfg` to `chat2db.cfg` in `lib/app/`.
4. **`dataSourceId` is an integer**, not a UUID or string. Example: `1782398519075536`. Pass it bare — quotes will be rejected with a type-mismatch error.
5. **`MCP access requires a valid desktop MCP token`** — the token rotates when you reset it in *Settings → MCP service*. Update `drivers/mcp/chat2db.yaml` and start a new agent session.

Full troubleshooting recipes and a one-shot verify script: [`references/troubleshooting.md`](references/troubleshooting.md).

---

## 🧭 Related skills

| Skill | Covers |
|---|---|
| `chat2db` (this repo) | Chat2DB Local GUI + MCP (read-only) |
| `sqlx` | SQLX CLI — full CRUD, 38 DB engines, headless Linux |
| `chat2db-cli` | OtterMind Rust CLI for Chat2DB GUI lifecycle (macOS / Windows full, Linux / portable) |

---

## 🤝 Contributing

Issues and PRs welcome. Please attach the output of `verify_chat2db.sh` from `references/troubleshooting.md` for any startup-related bug report, plus the contents of `bin/debug.log` filtered for `ERROR|Singleton|JCEF`.

## 📄 License

Apache-2.0. See `LICENSE` (add before pushing).

## 🙏 Acknowledgements

- **OtterMind** — for Chat2DB Local, SQLX, and the chat2db-cli.
- **QwenPaw / MiniMax Code** — the agent platform where this skill was first deployed.
- **tangtianspeed.ai** — the Linux installation and debugging that produced the troubleshooting recipes.