#!/usr/bin/env bash
# check-prereqs.sh - mssql-legacy 前提依赖一键检查
# 注意：脚本不用 set -e，因为 check 内部允许失败
set -uo pipefail

PASS=0; FAIL=0; WARN=0
ROOT_DIR="${SQLREMOTE_DIR:-$HOME/workspaces/sqlremote}"
SQL_HOST="${MSSQL_SERVER:-192.0.2.10}"

pass_msg() { echo "✅ $1"; PASS=$((PASS+1)); }
fail_msg() { echo "❌ $1"; FAIL=$((FAIL+1)); }
warn_msg() { echo "⚠️  $1（选装）"; WARN=$((WARN+1)); }

ok_or_fail() { "$@" >/dev/null 2>&1 && pass_msg "$DESC" || fail_msg "$DESC"; }
ok_or_warn() { "$@" >/dev/null 2>&1 && pass_msg "$DESC" || warn_msg "$DESC"; }

echo "============================================"
echo "  mssql-legacy 前提依赖检查"
echo "============================================"

echo
echo "--- 1. 操作系统 ---"
DESC="OS = Linux x86_64"; ok_or_fail bash -c 'uname -m | grep -q x86_64'
DESC="Ubuntu 22.04+ 或 24.04+"; ok_or_warn bash -c 'grep -qE "VERSION_ID=\"(22|24)\.04" /etc/os-release'

echo
echo "--- 2. 必装软件包 ---"
DESC="msodbcsql18"; ok_or_fail bash -c "dpkg -s msodbcsql18 2>/dev/null | grep -q 'Status: install ok installed'"
DESC="mssql-tools18"; ok_or_fail bash -c "dpkg -s mssql-tools18 2>/dev/null | grep -q 'Status: install ok installed'"
DESC="unixodbc"; ok_or_fail bash -c "dpkg -s unixodbc 2>/dev/null | grep -q 'Status: install ok installed'"
DESC="unixodbc-dev"; ok_or_warn bash -c "dpkg -s unixodbc-dev 2>/dev/null | grep -q 'Status: install ok installed'"

echo
echo "--- 3. 选装软件包 ---"
DESC="smbclient"; ok_or_warn bash -c "dpkg -s smbclient 2>/dev/null | grep -q 'Status: install ok installed'"
DESC="cifs-utils"; ok_or_warn bash -c "dpkg -s cifs-utils 2>/dev/null | grep -q 'Status: install ok installed'"

echo
echo "--- 4. sqlcmd 二进制 ---"
DESC="sqlcmd 可执行"; ok_or_fail test -x /opt/mssql-tools18/bin/sqlcmd
DESC="ODBC Driver 18 已注册"; ok_or_fail bash -c "odbcinst -q -d 2>/dev/null | grep -q 'ODBC Driver 18'"

echo
echo "--- 5. 工作目录 ($ROOT_DIR) ---"
DESC="sqlremote 目录存在"; ok_or_fail test -d "$ROOT_DIR"
DESC="sqlremote/conf/ 存在"; ok_or_fail test -d "$ROOT_DIR/conf"
DESC="sqlremote/sql/ 存在"; ok_or_fail test -d "$ROOT_DIR/sql"
DESC="sqlremote/logs/ 存在"; ok_or_warn test -d "$ROOT_DIR/logs"
DESC="sqlremote/reports/ 存在"; ok_or_warn test -d "$ROOT_DIR/reports"

echo
echo "--- 6. 凭据文件 ---"
DESC=".env 文件存在"; ok_or_fail test -f "$ROOT_DIR/.env"
if [[ -f "$ROOT_DIR/.env" ]]; then
  PERM=$(stat -c %a "$ROOT_DIR/.env" 2>/dev/null || echo "")
  DESC=".env 权限 600 (当前=$PERM)"; ok_or_warn test "$PERM" = "600"
fi

echo
echo "--- 7. OpenSSL 隔离配置 ---"
CONF="$ROOT_DIR/conf/openssl-sqlserver.cnf"
DESC="openssl-sqlserver.cnf 存在"; ok_or_fail test -f "$CONF"
if [[ -f "$CONF" ]]; then
  DESC="openssl-sqlserver.cnf 含 ssl_conf"; ok_or_warn grep -q 'ssl_conf = ssl_sect' "$CONF"
  DESC="openssl-sqlserver.cnf 含 MinProtocol"; ok_or_warn grep -q 'MinProtocol = TLSv1' "$CONF"
fi

echo
echo "--- 8. mssql 包装命令 ---"
DESC="mssql 命令可用"; ok_or_warn bash -c "command -v mssql >/dev/null 2>&1 || test -x \"$HOME/.local/bin/mssql\""
if [[ -x "$HOME/.local/bin/mssql" ]]; then
  DESC="mssql 含 OPENSSL_CONF"; ok_or_warn grep -q 'OPENSSL_CONF' "$HOME/.local/bin/mssql"
fi

echo
echo "--- 9. 网络连通性 ---"
DESC="TCP $SQL_HOST:1433 可达"; ok_or_warn bash -c "command -v nc >/dev/null 2>&1 && nc -z -w 5 \"$SQL_HOST\" 1433"

echo
echo "============================================"
echo "  结果：$PASS 通过，$FAIL 失败，$WARN 警告"
echo "============================================"
[ $FAIL -eq 0 ] && echo "🎉 所有必须项通过！" || echo "⚠️  有 $FAIL 项必须项需要修复"
exit $FAIL
