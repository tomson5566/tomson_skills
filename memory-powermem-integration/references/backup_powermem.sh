#!/bin/bash
# PowerMem 记忆备份脚本
# 每周日 1:00 执行，备份数据库 + 导出记忆到 JSON
# 保存位置: /root/memory

set -e

BACKUP_DIR="/root/memory"
DB_PATH="/root/data/powermem_dev.db"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

mkdir -p "$BACKUP_DIR"

# 备份数据库文件
cp "$DB_PATH" "$BACKUP_DIR/powermem_$TIMESTAMP.db"

# 导出记忆列表到 JSON
sqlite3 -json "$DB_PATH" "SELECT id, payload FROM memories;" > "$BACKUP_DIR/memories_$TIMESTAMP.json"

# 保留最近 4 周备份
find "$BACKUP_DIR" -name "powermem_*.db" -type f -mtime +28 -delete
find "$BACKUP_DIR" -name "memories_*.json" -type f -mtime +28 -delete

echo "[$(date '+%Y-%m-%d %H:%M:%S')] PowerMem backup completed: $TIMESTAMP" >> "$BACKUP_DIR/backup.log"