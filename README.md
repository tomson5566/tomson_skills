# tomson_skills

Collection of AI Agent Skills and database automation tools for personal devops and LLM memory management workflows.

## 📂 Subprojects

| Directory | Description |
|---|---|
| `memory-powermem-integration/` | AI memory persistence via PowerMem — auto-sync, semantic search, scheduled backup |
| `sqlremote/` | Remote SQL Server 2012 management from Linux — backup, inspection, TLS compatibility |
| `mssql-legacy/` | Legacy mssql skill for SQL Server remote operations via `mssql` wrapper |
| `github-readme-creator/` | Mavis skill for generating project README files |
| `mssql-tools18/` | Microsoft SQL Server command-line tools (sqlcmd, bcp) for Linux |

---

## memory-powermem-integration

AI memory integration tool that automatically persists session memory to PowerMem (LLM memory database) with semantic search, tagging, and scheduled backup.

### Key Features

- **On-demand retrieval** — AI searches PowerMem history when needed, no polling required
- **Auto-sync** — Scheduled memory sedimentation via Cron (default: daily at 01:00)
- **10-dimension tagging** — Each memory entry auto-tagged across time, topic, keywords, project, action, status, priority, and more
- **Idempotent writes** — Built-in similarity dedup; no manual content hash required
- **Auto database backup** — PowerMem SQLite backup every Sunday, 4-week retention
- **Remote Ollama Embedding** — Works with remote Embedding services via `OLLAMA_EMBEDDING_BASE_URL`
- **Production-stable** — Uses `--no-infer` to skip LLM inference; write time drops from 35–90s to 3–6s

### Quick Start

```bash
# Configure Ollama Embedding (PowerMem only recognizes these two variable names)
export OLLAMA_EMBEDDING_BASE_URL=http://target-host:11434
# or
export ollama_base_url=http://target-host:11434

# Verify PowerMem connectivity
pmem config test

# Manual memory search
pmem memory search "deployment"

# Manual memory add (fast mode)
pmem memory add "your memory summary" --metadata '{"tag1_time":"2025-05-24"}' --no-infer
```

### Environment

- Linux (CentOS / Ubuntu / Debian)
- Python 3.10+
- PowerMem CLI (`/root/miniconda3/bin/pmem`)
- Optional: Cron for scheduled tasks

---

## sqlremote

Lightweight remote management toolkit for SQL Server 2012 from Linux / OpenClaw hosts. Covers connection testing, health inspection, and serial-per-database full backup — without depending on SQL Server Agent.

### Key Features

- **SQL Server 2012 TLS 1.0 compatibility** — Isolated `OPENSSL_CONF` per process; no system-wide TLS downgrade
- **Connection test** — `scripts/sqlcmd-test.sh` validates connectivity and version
- **Health inspection SQL** — Check version, database state, recovery model
- **Remote serial full backup** — Initiate `BACKUP DATABASE` from Linux; files land on the SQL Server host
- **Backup verification** — Optional `RESTORE VERIFYONLY WITH CHECKSUM` after each database
- **Run audit trail** — Backup manifests and execution logs written to `reports/`

### Quick Start

```bash
# Create local .env (do NOT commit to Git)
cat > ~/workspaces/sqlremote/.env <<'EOF'
msuser=YOUR_SQL_LOGIN
mskey=YOUR_SQL_PASSWORD
EOF
chmod 600 ~/workspaces/sqlremote/.env

# Test connection
~/workspaces/sqlremote/scripts/sqlcmd-test.sh 192.0.2.10

# Check database state
mssql -Q "SELECT name, recovery_model_desc, state_desc FROM sys.databases ORDER BY name;"

# Remote full backup (serial, per-database)
~/workspaces/sqlremote/scripts/remote_full_backup_133_14.sh
```

### Environment Variables

| Variable | Default | Description |
|---|---:|---|
| `ROOT_BACKUP_PATH` | `D:\backup` | Backup root path as seen by SQL Server |
| `VERIFY_BACKUP` | `1` | Run `RESTORE VERIFYONLY` after each backup |
| `INCLUDE_SYSTEM_DB` | `1` | Include master/model/msdb |
| `SLEEP_SECONDS` | `3` | Pause between databases |
| `USE_DATE_SUBDIR` | `1` | Append `yyyyMMdd` subdirectory |
| `CREATE_BACKUP_DIR` | `1` | Use `xp_cmdshell` to create dirs |

---

## mssql-legacy

Full skill for remote SQL Server 2012 RTM management from Linux. Includes client installation, `OPENSSL_CONF` isolation, `mssql` wrapper command, common ops SQL, and automation scripts.

### Key Features

- **`mssql` wrapper** — Auto-loads credentials + `OPENSSL_CONF`; one command to connect
- **TLS 1.0 isolation** — `OPENSSL_CONF` loads per sqlcmd process only; system-wide TLS policy untouched
- **sqlcmd + bcp** — Installed under `/opt/mssql-tools18/bin/`
- **Health checks** — Version check, database list, log size, disk space
- **Common ops SQL** — Log truncation, backup trigger, `SHRINKFILE`, etc.

### Quick Start

```bash
# Query version
mssql -Q "SELECT @@VERSION"

# List all databases
mssql -Q "SELECT name, recovery_model_desc FROM sys.databases ORDER BY name"

# Execute SQL file
mssql -i ~/workspaces/sqlremote/sql/02_check_databases.sql
```

---

## github-readme-creator

Mavis agent skill for generating practical, project-specific GitHub `README.md` files. Inspects the repository to produce accurate content — no generic marketing filler.

### Key Features

- **Repository inspection** — Reads `package.json`, `pyproject.toml`, `go.mod`, `Cargo.toml`, etc. to understand the project
- **Secret scanning** — Detects leaked credentials before README generation; surfaces findings for remediation
- **Accurate sections** — Title, overview, features, requirements, installation, usage, configuration, structure, contributing, license
- **No placeholder text** — All content reflects actual project state

---

## Project Structure

```
tomson_skills/
├── memory-powermem-integration/      # AI memory → PowerMem
│   ├── SKILL.md
│   ├── README_FLOW.md
│   ├── scripts/
│   │   ├── memory_sync.py            # Cron memory sync
│   │   ├── backup_powermem.sh       # Weekly DB backup
│   │   ├── tag_extractor.py
│   │   ├── read_memory.py
│   │   └── content_hash.py
│   └── references/
│       ├── pmem_cli_commands.md
│       ├── pmem_add_behavior.md
│       ├── pmem_troubleshooting.md
│       └── memory_schema.md
├── sqlremote/                         # SQL Server remote ops
│   ├── conf/
│   │   └── openssl-sqlserver.cnf    # TLS 1.0 compat config
│   ├── scripts/
│   │   ├── remote_full_backup_133_14.sh
│   │   └── sqlcmd-test.sh
│   ├── sql/
│   │   ├── 01_check_version.sql
│   │   └── 02_check_databases.sql
│   ├── reports/                      # Backup logs
│   └── .env                          # Credentials (gitignored)
├── mssql-legacy/                     # Legacy mssql skill
│   ├── SKILL.md
│   ├── sql/
│   │   ├── 01_check_version.sql
│   │   ├── 02_check_databases.sql
│   │   ├── 03_check_log_size.sql
│   │   └── 04_check_disk_space.sql
│   ├── scripts/
│   │   ├── sqlcmd-test.sh
│   │   └── mssql-wrapper.sh
│   └── docs/
│       └── sql-recipes.md
├── github-readme-creator/             # README generator skill
│   └── SKILL.md
├── mssql-tools18/                    # SQL Server CLI tools
│   ├── bin/
│   │   ├── sqlcmd
│   │   └── bcp
│   └── share/resources/
└── README.md
```

---

## Security

- **Never commit** `.env`, credentials, private keys, `.pem`, `*.key`, `*.bak`, `*.trn`, `*.mdf`, `*.ldf`, `reports/`, `logs/`, `data/`
- `.env` files must have `chmod 600` on Linux
- README and docs use RFC 5737 documentation IPs (e.g. `192.0.2.0/24`) instead of real internal addresses
- If credentials were ever committed, rotate passwords and clean git history with `git filter-repo` or BFG

---

## License

Apache License 2.0 — see [LICENSE](LICENSE)

---

> Parts of documentation generated with AI assistance