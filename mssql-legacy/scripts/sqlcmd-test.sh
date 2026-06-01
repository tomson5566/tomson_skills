#!/usr/bin/env bash
# sqlcmd-test.sh - SQL Server 远程连接测试脚本
# 使用专用 OpenSSL 配置兼容 SQL Server 2012 RTM 的 TLS 1.0
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="${SQLREMOTE_DIR:-$HOME/workspaces/sqlremote}"

# 加载凭据
if [[ -f "$ROOT_DIR/.env" ]]; then
  set -a
  . "$ROOT_DIR/.env"
  set +a
fi

SERVER="${1:-${MSSQL_SERVER:-192.0.2.10}}"
USER_NAME="${msuser:-${MSSQL_USER:-sql_backup_operator}}"
PASSWORD="${mskey:-${MSSQL_PASSWORD:-}}"

if [[ -z "$PASSWORD" ]]; then
  echo "❌ 缺少密码：请配置 $ROOT_DIR/.env" >&2
  echo "   示例内容：" >&2
  echo "     msuser=sql_backup_operator" >&2
  echo "     mskey=你的密码" >&2
  exit 2
fi

# 使用 sqlcmd 专用 OpenSSL 配置（兼容 TLS 1.0，仅本进程生效）
export OPENSSL_CONF="$ROOT_DIR/conf/openssl-sqlserver.cnf"

if [[ ! -f "$OPENSSL_CONF" ]]; then
  echo "❌ 专用 OpenSSL 配置不存在：$OPENSSL_CONF" >&2
  exit 3
fi

SQL_FILE="${ROOT_DIR}/sql/01_check_version.sql"
if [[ ! -f "$SQL_FILE" ]]; then
  SQL_FILE=/dev/stdin
  SQL_QUERY="SELECT @@VERSION;"
fi

echo "🔧 OPENSSL_CONF=$OPENSSL_CONF"
echo "🌐 Server: $SERVER"
echo "👤 User: $USER_NAME"
echo "📄 SQL: $SQL_FILE"
echo

if [[ "$SQL_FILE" = /dev/stdin ]]; then
  echo "$SQL_QUERY" | /opt/mssql-tools18/bin/sqlcmd \
    -S "$SERVER" -U "$USER_NAME" -P "$PASSWORD" -C
else
  /opt/mssql-tools18/bin/sqlcmd \
    -S "$SERVER" -U "$USER_NAME" -P "$PASSWORD" -C \
    -i "$SQL_FILE"
fi
