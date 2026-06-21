#!/usr/bin/env bash
# first_run.sh — 5 分钟跑通 ingestr 的 demo
# 用法：scripts/first_run.sh [/path/to/workdir]
# 默认 workdir：/tmp/ingestr-quickstart

set -euo pipefail

WORKDIR="${1:-/tmp/ingestr-quickstart}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WRAPPER="$SCRIPT_DIR/ingestr.sh"

mkdir -p "$WORKDIR" && cd "$WORKDIR"

# 颜色
G="\033[1;32m"; Y="\033[1;33m"; C="\033[1;36m"; R="\033[0m"

step() { printf "\n${C}==> %s${R}\n" "$*"; }
ok()   { printf "${G}✓${R} %s\n" "$*"; }
warn() { printf "${Y}!${R} %s\n" "$*"; }

# 默认用 SQLite↔SQLite（不依赖 ADBC 下载）
# 想用 DuckDB 把 DEST 改成 duckdb:///$PWD/dest.db 并把 verify 工具换成 duckdb
SRC="sqlite:///$PWD/source.db"
DEST="sqlite:///$PWD/dest.db"

# 0. 确认 ingestr
step "0. 确认 ingestr 已装"
"$WRAPPER" --version

# 1. 建 SQLite 源
step "1. 建 SQLite 源（3 行测试数据）"
python3 - <<'PY'
import sqlite3, os
db = "source.db"
if os.path.exists(db):
    os.remove(db)
con = sqlite3.connect(db)
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
print("source.db ready")
PY
ok "source.db 建好（3 users）"

# 2. 第一次 ingest（replace）
step "2. 第一次 ingest（默认 replace 策略）"
"$WRAPPER" ingest \
  --source-uri "$SRC" \
  --source-table "users" \
  --dest-uri "$DEST" \
  --dest-table "users" \
  --yes
ok "第一次 ingest 完成"

# 3. 验证
step "3. 验证目标表"
python3 - <<'PY'
import sqlite3
con = sqlite3.connect("dest.db")
rows = con.execute("SELECT * FROM users ORDER BY id").fetchall()
for r in rows:
    print("  ", r)
assert len(rows) == 3, f"expected 3, got {len(rows)}"
print(f"OK: {len(rows)} rows")
PY
ok "SQLite 目标表 3 行 ✓"

# 4. 加 2 行 + append（带 interval 窗口）
step "4. 源加 2 行 + 用 append 增量（带 interval-start/end）"
python3 - <<'PY'
import sqlite3
con = sqlite3.connect("source.db")
con.execute("INSERT INTO users VALUES (4, 'Dave', 'dave@x.com', '2026-02-01 10:00:00')")
con.execute("INSERT INTO users VALUES (5, 'Eve',  'eve@x.com',  '2026-02-02 10:00:00')")
con.commit()
print("added 2 rows")
PY
"$WRAPPER" ingest \
  --source-uri "$SRC" \
  --source-table "users" \
  --dest-uri "$DEST" \
  --dest-table "users" \
  --incremental-strategy append \
  --incremental-key created_at \
  --interval-start "2026-01-04 00:00:00" \
  --interval-end "2026-12-31 00:00:00" \
  --yes
python3 -c "
import sqlite3
con = sqlite3.connect('dest.db')
n = con.execute('SELECT COUNT(*) FROM users').fetchone()[0]
print(f'rows: {n}')
assert n == 5, f'expected 5, got {n}'
"
ok "append 后 5 行 ✓（注意：必须配 --interval-start/end）"

# 5. 改 1 行 + merge（带 interval 窗口）
step "5. 源改 1 行 + 用 merge 按 PK upsert（带 interval 窗口）"
python3 - <<'PY'
import sqlite3
con = sqlite3.connect("source.db")
con.execute("UPDATE users SET name='Alice 2.0', created_at='2026-03-01' WHERE id=1")
con.commit()
print("updated id=1")
PY
"$WRAPPER" ingest \
  --source-uri "$SRC" \
  --source-table "users" \
  --dest-uri "$DEST" \
  --dest-table "users" \
  --incremental-strategy merge \
  --incremental-key created_at \
  --interval-start "2026-02-15 00:00:00" \
  --interval-end "2026-12-31 00:00:00" \
  --primary-key id \
  --yes
python3 -c "
import sqlite3
con = sqlite3.connect('dest.db')
rows = con.execute('SELECT id, name FROM users ORDER BY id').fetchall()
for r in rows:
    print('  ', r)
assert rows[0][1] == 'Alice 2.0', f'expected Alice 2.0, got {rows[0][1]}'
"
ok "merge 后 id=1 变成 'Alice 2.0' ✓"

# 6. 自定义 SQL
step "6. 自定义 SQL：只取前 3 个用户"
"$WRAPPER" ingest \
  --source-uri "$SRC" \
  --source-table "query:SELECT id, name, email FROM users WHERE id <= 3" \
  --dest-uri "$DEST" \
  --dest-table "first_three" \
  --yes
python3 -c "
import sqlite3
con = sqlite3.connect('dest.db')
rows = con.execute('SELECT id, name FROM first_three ORDER BY id').fetchall()
for r in rows:
    print('  ', r)
"
ok "自定义 SQL 跑通 ✓"

step "🎉 全部跑完！"
echo "工作目录：$WORKDIR"
ls -la "$WORKDIR"
echo ""
echo "下一步："
echo "  1. 看 references/INDEX.md 知道还有什么 reference"
echo "  2. 看 references/quickstart.md 自己手动跑一遍（体会参数）"
echo "  3. 看 references/internals.md 理解 ingestr 内部架构"
