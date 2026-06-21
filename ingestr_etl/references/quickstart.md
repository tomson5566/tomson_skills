# ingestr 5 分钟上手

> 目标：5 分钟内跑通一次真实数据搬运，建立"我能让它工作"的信心。
> 不需要任何外部数据库——用本地 SQLite + DuckDB 即可。

## 0. 前置：确认 ingestr 已装

```bash
ingestr --version
# 预期：ingestr version v1.0.21
```

如果没装，跑一次 skill 里的 wrapper：

```bash
~/.copaw/workspaces/data_etl_agent/skills/ingestr_etl/scripts/ingestr.sh --version
# 第一次会从 docs/ingestr_Linux_x86_64.tar.gz 自动装到 ~/.local/bin/ingestr
```

## 1. 准备 SQLite 源数据

```bash
mkdir -p /tmp/ingestr-quickstart && cd /tmp/ingestr-quickstart

# 用 python3 生成一个 SQLite 测试库（不需要额外工具）
python3 <<'PY'
import sqlite3, datetime
con = sqlite3.connect("source.db")
con.executescript("""
CREATE TABLE users (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  email TEXT,
  created_at TEXT
);
""")
con.executemany(
    "INSERT INTO users VALUES (?,?,?,?)",
    [
        (1, "Alice", "alice@example.com", "2026-01-01 10:00:00"),
        (2, "Bob",   "bob@example.com",   "2026-01-02 11:00:00"),
        (3, "Carol", "carol@example.com", "2026-01-03 12:00:00"),
    ],
)
con.commit()
con.close()
print("source.db created with 3 users")
PY
```

## 2. 跑第一次 ingest（默认 replace 策略）

```bash
ingestr ingest \
  --source-uri "sqlite:////tmp/ingestr-quickstart/source.db" \
  --source-table "users" \
  --dest-uri "duckdb:////tmp/ingestr-quickstart/dest.db" \
  --dest-table "users" \
  --yes
```

> 注意 SQLite/DuckDB 是文件型 URI，**三个斜杠**：`sqlite:///path`（前两个是 `://`，第三个是路径起点）。

输出（简化）：

```
[15:04:05] [STRATEGY] Using staging table: ...
[15:04:05] Detected primary keys: [id]
[15:04:05] Wrote 3 rows to users
```

## 3. 验证结果

```bash
python3 -c "
import duckdb
con = duckdb.connect('/tmp/ingestr-quickstart/dest.db', read_only=True)
print(con.execute('SELECT * FROM users').fetchall())
"
# 预期：[(1, 'Alice', ...), (2, 'Bob', ...), (3, 'Carol', ...)]
```

🎉 成功！数据从 SQLite 搬到了 DuckDB。

## 4. 试试增量（append）

加几行再跑，**这次用 append**：

```bash
python3 -c "
import sqlite3
con = sqlite3.connect('/tmp/ingestr-quickstart/source.db')
con.execute(\"INSERT INTO users VALUES (4, 'Dave', 'dave@x.com', '2026-02-01 10:00:00')\")
con.execute(\"INSERT INTO users VALUES (5, 'Eve',  'eve@x.com',  '2026-02-02 10:00:00')\")
con.commit()
"

ingestr ingest \
  --source-uri "sqlite:////tmp/ingestr-quickstart/source.db" \
  --source-table "users" \
  --dest-uri "duckdb:////tmp/ingestr-quickstart/dest.db" \
  --dest-table "users" \
  --incremental-strategy append \
  --incremental-key created_at \
  --interval-start "2026-02-01 00:00:00" \
  --interval-end "2026-12-31 00:00:00" \
  --yes

python3 -c "
import duckdb
con = duckdb.connect('/tmp/ingestr-quickstart/dest.db', read_only=True)
print('rows:', con.execute('SELECT COUNT(*) FROM users').fetchone())
"
# 预期：rows: 5
```

> ⚠️ **重要**：ingestr 不会自动从 dest 算 `max(incremental_key)`，你必须显式传 `--interval-start` 和 `--interval-end`。
> 不传 = 全表扫描（很危险，append 会全表插入，触发重复键冲突）。

## 5. 试试 merge（按主键更新）

把 id=1 的 name 改一下，跑 merge：

```bash
python3 -c "
import sqlite3
con = sqlite3.connect('/tmp/ingestr-quickstart/source.db')
con.execute(\"UPDATE users SET name='Alice 2.0' WHERE id=1\")
con.execute(\"UPDATE users SET created_at='2026-03-01' WHERE id=1\")
con.commit()
"

ingestr ingest \
  --source-uri "sqlite:////tmp/ingestr-quickstart/source.db" \
  --source-table "users" \
  --dest-uri "duckdb:////tmp/ingestr-quickstart/dest.db" \
  --dest-table "users" \
  --incremental-strategy merge \
  --incremental-key created_at \
  --interval-start "2026-02-15 00:00:00" \
  --interval-end "2026-12-31 00:00:00" \
  --primary-key id \
  --yes

python3 -c "
import duckdb
con = duckdb.connect('/tmp/ingestr-quickstart/dest.db', read_only=True)
for r in con.execute('SELECT id, name FROM users ORDER BY id').fetchall():
    print(r)
"
# 预期：(1, 'Alice 2.0')  ← 被更新
#      (2, 'Bob')
#      (3, 'Carol')
#      (4, 'Dave')
#      (5, 'Eve')
```

## 6. 试试自定义 SQL

只取活跃用户：

```bash
ingestr ingest \
  --source-uri "sqlite:////tmp/ingestr-quickstart/source.db" \
  --source-table "query:SELECT id, name, email FROM users WHERE id <= 3" \
  --dest-uri "duckdb:////tmp/ingestr-quickstart/dest.db" \
  --dest-table "first_three" \
  --yes
```

## 7. 跑 server（Web UI）

```bash
ingestr server --port 8080 &
# 浏览器开 http://localhost:8080
# 看完 Ctrl+C
```

## 8. 跑 plan_ingest.py 帮你拼命令

```bash
python3 ~/.copaw/workspaces/data_etl_agent/skills/ingestr_etl/scripts/plan_ingest.py \
  --source-uri "sqlite:////tmp/ingestr-quickstart/source.db" \
  --source-table "users" \
  --dest-uri "duckdb:////tmp/ingestr-quickstart/dest.db" \
  --dest-table "users" \
  --strategy merge \
  --primary-key id \
  --incremental-key created_at
```

输出：

```
ingestr ingest --source-uri sqlite:////tmp/ingestr-quickstart/source.db --dest-uri duckdb:////tmp/ingestr-quickstart/dest.db --source-table users --dest-table users --incremental-strategy merge --incremental-key created_at --primary-key id --yes
```

## 9. 跑 validate_uri.py 帮你校 URI

```bash
python3 ~/.copaw/workspaces/data_etl_agent/skills/ingestr_etl/scripts/validate_uri.py \
  "sqlite:////tmp/ingestr-quickstart/source.db"
# OK    sqlite:////tmp/ingestr-quickstart/source.db
```

## 5 分钟能学到什么

✅ ingestr 的"端到端流程"（不用懂源码就能用）
✅ 5 个核心 flag：`--source-uri`, `--source-table`, `--dest-uri`, `--dest-table`, `--incremental-strategy`
✅ URI 三斜杠的细节
✅ 3 个策略的语义差异：replace / append / merge
✅ 自定义 SQL 的 `query:` 前缀

## 下一步该看什么

| 你想 | 看 |
|------|----|
| 搞懂"为什么"（架构/设计）| `references/internals.md` |
| 选对策略 | `references/strategy_guide.md` |
| URI 不知道怎么写 | `references/uri_formats.md` |
| 加复杂 flag（mask/partition/cluster）| `references/flag_reference.md` |
| 跑批/性能调优 | `references/performance.md` |
| 翻车了 | `references/troubleshooting.md` |
| 一键看所有 reference | `references/INDEX.md` |
