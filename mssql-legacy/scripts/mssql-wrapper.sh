#!/usr/bin/env bash
# mssql - sqlcmd 包装命令，自动加载 OPENSSL_CONF 和凭据
#
# 安装：
#   cp mssql-wrapper.sh ~/.local/bin/mssql
#   chmod +x ~/.local/bin/mssql
#
# 用法：
#   mssql -Q "SELECT @@VERSION"
#   mssql -i some.sql
#   mssql -d HR -Q "SELECT TOP 10 * FROM sys.tables"
#
# 环境变量覆盖：
#   MSSQL_SERVER    目标服务器（默认 192.0.2.10）
#   MSSQL_USER      用户名（默认从 .env 的 msuser，建议使用专用账号）
#   MSSQL_PASSWORD  密码（默认从 .env 的 mskey）
set -euo pipefail

ROOT_DIR="$HOME/workspaces/sqlremote"

# 加载凭据
if [[ -f "$ROOT_DIR/.env" ]]; then
  set -a
  . "$ROOT_DIR/.env"
  set +a
fi

SERVER="${MSSQL_SERVER:-192.0.2.10}"
USER_NAME="${msuser:-${MSSQL_USER:-sql_backup_operator}}"
PASSWORD="${mskey:-${MSSQL_PASSWORD:-}}"

if [[ -z "$PASSWORD" ]]; then
  echo "❌ 缺少密码：请配置 $ROOT_DIR/.env 或环境变量 mskey/MSSQL_PASSWORD" >&2
  exit 2
fi

export OPENSSL_CONF="$ROOT_DIR/conf/openssl-sqlserver.cnf"

if [[ ! -f "$OPENSSL_CONF" ]]; then
  echo "❌ 专用 OpenSSL 配置不存在：$OPENSSL_CONF" >&2
  echo "   参考 ~/workspaces/skills/mssql-legacy/prerequisites.md 第 4 节" >&2
  exit 3
fi

exec /opt/mssql-tools18/bin/sqlcmd \
  -S "$SERVER" \
  -U "$USER_NAME" \
  -P "$PASSWORD" \
  -C \
  "$@"
