#!/usr/bin/env bash
# sqlcmd-test.sh - SQL Server 远程连接测试脚本
# 使用专用 OpenSSL 配置兼容 SQL Server 2012 RTM 的 TLS 1.0
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

# 加载凭据
if [[ -f "$ROOT_DIR/.env" ]]; then
  set -a
  . "$ROOT_DIR/.env"
  set +a
fi

SERVER="${1:-192.168.133.14}"
USER_NAME="${msuser:-${SQLSERVER_USER:-sa}}"
PASSWORD="${mskey:-${SQLSERVER_PASSWORD:-}}"

if [[ -z "$PASSWORD" ]]; then
  echo "❌ 缺少密码：请配置 ~/workspaces/sqlremote/.env" >&2
  echo "   示例内容：" >&2
  echo "     msuser=sa" >&2
  echo "     mskey=你的密码" >&2
  exit 2
fi

# 使用 sqlcmd 专用 OpenSSL 配置（兼容 TLS 1.0，仅本进程生效）
export OPENSSL_CONF="$ROOT_DIR/conf/openssl-sqlserver.cnf"

if [[ ! -f "$OPENSSL_CONF" ]]; then
  echo "❌ 专用 OpenSSL 配置不存在：$OPENSSL_CONF" >&2
  exit 3
fi

echo "🔧 OPENSSL_CONF=$OPENSSL_CONF"
echo "🌐 Server: $SERVER"
echo "👤 User: $USER_NAME"
echo

/opt/mssql-tools18/bin/sqlcmd \
  -S "$SERVER" \
  -U "$USER_NAME" \
  -P "$PASSWORD" \
  -C \
  -i "$ROOT_DIR/sql/01_check_version.sql"
