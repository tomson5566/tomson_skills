# ----- Conda Initialize -----
import sqlite3, json
conn = sqlite3.connect('/root/memory/powermem_20260531_164253.db')
for row in conn.execute("SELECT id, payload FROM memories"):
    payload = json.loads(row[1])
    print(f"ID: {row[0]}")
    print(f"内容: {payload['data']}")
    print(f"标签: {payload['metadata']}")
    print("---")
