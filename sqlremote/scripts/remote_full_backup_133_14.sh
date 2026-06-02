#!/usr/bin/env bash
set -u

# 192.168.133.14 SQL Server 远程逐库完整备份脚本
# 触发端：本机 Linux / OpenClaw 主机
# 执行端：通过 mssql(sqlcmd) 远程向 SQL Server 发送 BACKUP DATABASE 命令
# 备份文件实际写入 SQL Server 服务器本机路径，例如 D:\backup\yyyyMMdd\
# 注意：BACKUP DATABASE TO DISK 的路径是 SQL Server 服务器看到的路径，不是本机 Linux 路径。

ROOT_BACKUP_PATH="${ROOT_BACKUP_PATH:-D:\\backup}"
VERIFY_BACKUP="${VERIFY_BACKUP:-1}"          # 1=每个库备份后 RESTORE VERIFYONLY，0=不校验
INCLUDE_SYSTEM_DB="${INCLUDE_SYSTEM_DB:-1}"  # 1=备份 master/model/msdb，0=只备业务库
SQL_TIMEOUT="${SQL_TIMEOUT:-0}"              # 0=不限制 sqlcmd 查询超时
SLEEP_SECONDS="${SLEEP_SECONDS:-3}"          # 每个库之间暂停秒数，降低 IO 冲击
USE_DATE_SUBDIR="${USE_DATE_SUBDIR:-1}"      # 1=使用 D:\\backup\\yyyyMMdd，0=直接使用 D:\\backup
CREATE_BACKUP_DIR="${CREATE_BACKUP_DIR:-1}"  # 1=尝试用 xp_cmdshell 创建目录，0=不创建目录
MSSQL_BIN="${MSSQL_BIN:-$HOME/.local/bin/mssql}"

DATE_STR="$(date +%Y%m%d)"
TIME_STR="$(date +%H%M%S)"
RUN_ID="${DATE_STR}_${TIME_STR}"
LOCAL_BASE="$HOME/workspaces/sqlremote"
REPORT_DIR="$LOCAL_BASE/reports"
LOG_DIR="$LOCAL_BASE/logs"
mkdir -p "$REPORT_DIR" "$LOG_DIR"

LOG_FILE="$REPORT_DIR/remote-full-backup-133-14-${RUN_ID}.log"
DB_LIST_FILE="$REPORT_DIR/remote-full-backup-133-14-${RUN_ID}-db-list.txt"

log() {
  local msg="$*"
  printf '[%s] %s\n' "$(date '+%F %T')" "$msg" | tee -a "$LOG_FILE"
}

run_sql() {
  local sql="$1"
  "$MSSQL_BIN" -b -r1 -W -s "|" -l 30 -t "$SQL_TIMEOUT" -Q "$sql"
}

sql_quote() {
  # SQL N'...' 字符串转义
  printf "%s" "$1" | sed "s/'/''/g"
}

bracket_name() {
  # SQL Server QUOTENAME 简化版：[abc]]def]
  printf "%s" "$1" | sed 's/]/]]/g; s/^/[/; s/$/]/'
}

log "开始远程逐库完整备份：192.168.133.14"
log "ROOT_BACKUP_PATH=${ROOT_BACKUP_PATH}"
log "VERIFY_BACKUP=${VERIFY_BACKUP}, INCLUDE_SYSTEM_DB=${INCLUDE_SYSTEM_DB}, SLEEP_SECONDS=${SLEEP_SECONDS}, USE_DATE_SUBDIR=${USE_DATE_SUBDIR}, CREATE_BACKUP_DIR=${CREATE_BACKUP_DIR}"

if [[ ! -x "$MSSQL_BIN" ]]; then
  log "失败：找不到可执行 mssql：$MSSQL_BIN"
  exit 2
fi

# 1. 读取数据库列表：只取 ONLINE，排除 tempdb；是否包含系统库由 INCLUDE_SYSTEM_DB 控制。
if [[ "$INCLUDE_SYSTEM_DB" == "1" ]]; then
  DB_QUERY="SET NOCOUNT ON; SELECT name FROM sys.databases WHERE state_desc='ONLINE' AND name <> 'tempdb' ORDER BY CASE WHEN database_id <= 4 THEN 0 ELSE 1 END, name;"
else
  DB_QUERY="SET NOCOUNT ON; SELECT name FROM sys.databases WHERE state_desc='ONLINE' AND database_id > 4 ORDER BY name;"
fi

log "获取数据库列表..."
if ! run_sql "$DB_QUERY" | sed '/^$/d; /^[[:space:]]*name[[:space:]]*$/d; /^name|/d; /^----/d; /rows affected/d; s/^[[:space:]]*//; s/[[:space:]]*$//' > "$DB_LIST_FILE"; then
  log "失败：获取数据库列表失败"
  exit 3
fi

DB_COUNT=$(grep -cve '^$' "$DB_LIST_FILE" || true)
log "待备份数据库数量：${DB_COUNT}"
sed 's/^/  - /' "$DB_LIST_FILE" | tee -a "$LOG_FILE"

if [[ "$DB_COUNT" -eq 0 ]]; then
  log "失败：数据库列表为空"
  exit 4
fi

# 2. 准备 SQL Server 服务器本机备份目录。
#    如果 USE_DATE_SUBDIR=1，则使用 D:\backup\yyyyMMdd；否则直接使用 D:\backup。
#    如果 CREATE_BACKUP_DIR=1，则尝试用 xp_cmdshell 创建目录；安全策略禁用时可设置 CREATE_BACKUP_DIR=0。
if [[ "$USE_DATE_SUBDIR" == "1" ]]; then
  SERVER_BACKUP_DIR="${ROOT_BACKUP_PATH}\\${DATE_STR}"
else
  SERVER_BACKUP_DIR="${ROOT_BACKUP_PATH}"
fi
SERVER_BACKUP_DIR_SQL=$(sql_quote "$SERVER_BACKUP_DIR")

if [[ "$CREATE_BACKUP_DIR" == "1" ]]; then
  MKDIR_SQL="
SET NOCOUNT ON;
DECLARE @dir nvarchar(4000)=N'${SERVER_BACKUP_DIR_SQL}';
DECLARE @cmd nvarchar(4000)=N'IF NOT EXIST "' + @dir + N'" MKDIR "' + @dir + N'"';
EXEC master.dbo.xp_cmdshell @cmd, NO_OUTPUT;
"

  log "创建服务器备份目录：${SERVER_BACKUP_DIR}"
  if ! run_sql "$MKDIR_SQL" >> "$LOG_FILE" 2>&1; then
    log "警告：创建目录失败。可能 xp_cmdshell 未启用，或 SQL Server 服务账号无权限。"
    log "请先在 192.168.133.14 上人工创建目录：${SERVER_BACKUP_DIR}，或设置 USE_DATE_SUBDIR=0 CREATE_BACKUP_DIR=0 使用已存在根目录。"
    exit 5
  fi
else
  log "跳过创建目录，直接使用服务器备份目录：${SERVER_BACKUP_DIR}"
fi

# 3. 逐库串行备份。
SUCCESS=0
FAILED=0
FAILED_DBS=()

# 先把数据库列表读入数组，避免循环内 sqlcmd/mssql 子进程抢占 while-read 的标准输入。
mapfile -t DB_ARRAY < "$DB_LIST_FILE"

for DB_NAME in "${DB_ARRAY[@]}"; do
  [[ -z "$DB_NAME" ]] && continue

  SAFE_DB_FILE=$(printf "%s" "$DB_NAME" | tr -c 'A-Za-z0-9_.-' '_')
  BAK_FILE="${SERVER_BACKUP_DIR}\\${SAFE_DB_FILE}_FullBackup_${RUN_ID}.bak"
  DB_BRACKET=$(bracket_name "$DB_NAME")
  BAK_FILE_SQL=$(sql_quote "$BAK_FILE")
  BACKUP_NAME_SQL=$(sql_quote "${DB_NAME}_FullBackup_${RUN_ID}")

  log "开始备份数据库：${DB_NAME} -> ${BAK_FILE}"

  BACKUP_SQL="
SET NOCOUNT ON;
BACKUP DATABASE ${DB_BRACKET}
TO DISK = N'${BAK_FILE_SQL}'
WITH INIT, COMPRESSION, CHECKSUM, STATS = 10, NAME = N'${BACKUP_NAME_SQL}';
"

  if run_sql "$BACKUP_SQL" >> "$LOG_FILE" 2>&1; then
    log "完整备份成功：${DB_NAME}"

    if [[ "$VERIFY_BACKUP" == "1" ]]; then
      log "开始校验备份文件：${DB_NAME}"
      VERIFY_SQL="RESTORE VERIFYONLY FROM DISK = N'${BAK_FILE_SQL}' WITH CHECKSUM;"
      if run_sql "$VERIFY_SQL" >> "$LOG_FILE" 2>&1; then
        log "备份校验成功：${DB_NAME}"
        SUCCESS=$((SUCCESS + 1))
      else
        log "备份校验失败：${DB_NAME}"
        FAILED=$((FAILED + 1))
        FAILED_DBS+=("${DB_NAME}:VERIFY_FAILED")
      fi
    else
      SUCCESS=$((SUCCESS + 1))
    fi
  else
    log "完整备份失败：${DB_NAME}"
    FAILED=$((FAILED + 1))
    FAILED_DBS+=("${DB_NAME}:BACKUP_FAILED")
  fi

  if [[ "$SLEEP_SECONDS" =~ ^[0-9]+$ ]] && [[ "$SLEEP_SECONDS" -gt 0 ]]; then
    sleep "$SLEEP_SECONDS"
  fi
done

log "远程逐库完整备份结束。成功：${SUCCESS}，失败：${FAILED}，总数：${DB_COUNT}"

if [[ "$FAILED" -gt 0 ]]; then
  log "失败数据库："
  printf '  - %s\n' "${FAILED_DBS[@]}" | tee -a "$LOG_FILE"
  exit 10
fi

log "全部数据库备份与校验完成。日志文件：${LOG_FILE}"
exit 0
