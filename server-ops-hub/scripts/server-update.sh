#!/usr/bin/env bash
#===============================================================================
# server-update.sh — 迭代更新服务器巡检档案（agent 回写知识的主入口）
#
# 子命令:
#   service    <host> [--user U] --name N [--path P] [--config C] [--port N]
#              [--start-cmd C] [--status S] [--notes T]
#   database   <host> [--user U] --name N [--type T] [--version V] [--port N]
#              [--data-dir D] [--config C] [--notes T]
#   middleware <host> [--user U] --name N [--version V] [--port N] [--config C] [--notes T]
#   cred       <host> [--user U] os <账号> <密码> [--purpose T]
#   cred       <host> [--user U] (service|database|middleware) <目标名> <账号> <密码> [--purpose T]
#   devport    <host> [--user U] --port N [--service S] [--notes T]
#   note       <host> [--user U] <备注文本...>
#   category   <host> [--user U] <分类>
#   watch      <host> [--user U] --name N --match M [--start-cmd C] [--auto-restart]
#
# 所有子命令均为 upsert（同名字段合并更新），凭证类自动打 updated_at 时间戳，
# 支持不断迭代记录（改密码后重跑 cred 即可，时间戳保留最新记录时间）。
#===============================================================================
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/lib-common.sh"

# ---------- 公共参数解析 ----------
HOST="" USER=""
REST=()
parse_host_user() {  # 从当前剩余参数中取出 host 和 --user，其余存入 REST
  [[ $# -ge 1 ]] || rsc_die "缺少 <host> 参数"
  HOST="$1"; shift
  REST=()
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --user|--username) USER="$2"; shift 2;;
      *) REST+=("$1"); shift 1;;
    esac
  done
  if [[ -z "$USER" ]]; then
    USER=$(rsc_server_json "$HOST" "" "" | jq -r '.auth.username') \
      || rsc_die "无法唯一定位 $HOST，请用 --user 指定账号"
  fi
}

# 注意：set -- 必须在各分支内联执行（函数内 set -- 只影响函数自身的 $@）
# ${REST[@]+"${REST[@]}"} 写法兼容 bash3/4 空数组 + set -u

# upsert 通用 jq 片段：对 inspection.<field> 数组按 key 字段合并/新增
upsert_jq() {  # $1=field $2=key
  cat <<JQ
.servers |= map(
  if .host == \$h and .auth.username == \$u then
    .inspection.$1 |= (
      (map(select(.$2 == \$key)) | length) as \$n
      | if \$n > 0 then map(if .$2 == \$key then . + \$obj else . end)
        else . + [\$obj] end
    ) | .updated_at = \$now
  else . end)
JQ
}

ACTION="${1:-}"; shift || true
case "$ACTION" in

# ---------------- service ----------------
service)
  parse_host_user "$@"; set -- ${REST[@]+"${REST[@]}"}
  NAME="" PATH_="" CONFIG="" SPORT="" STARTCMD="" STATUS="" NOTES=""
  while [[ $# -gt 0 ]]; do case "$1" in
    --name) NAME="$2"; shift 2;; --path) PATH_="$2"; shift 2;;
    --config) CONFIG="$2"; shift 2;; --port) SPORT="$2"; shift 2;;
    --start-cmd) STARTCMD="$2"; shift 2;; --status) STATUS="$2"; shift 2;;
    --notes) NOTES="$2"; shift 2;; *) rsc_die "未知参数: $1";; esac; done
  [[ -n "$NAME" ]] || rsc_die "service 需要 --name"
  OBJ=$(jq -cn --arg n "$NAME" --arg p "$PATH_" --arg c "$CONFIG" --arg po "$SPORT" \
    --arg s "$STARTCMD" --arg st "$STATUS" --arg no "$NOTES" --arg now "$(rsc_now)" '
    {name:$n, updated_at:$now}
    + (if $p=="" then {} else {path:$p} end)
    + (if $c=="" then {} else {config:$c} end)
    + (if $po=="" then {} else {port:($po|tonumber)} end)
    + (if $s=="" then {} else {start_cmd:$s} end)
    + (if $st=="" then {} else {status:$st} end)
    + (if $no=="" then {} else {notes:$no} end)')
  rsc_jq_update "$(upsert_jq services name)" \
    --arg h "$HOST" --arg u "$USER" --arg key "$NAME" --argjson obj "$OBJ"
  rsc_info "已回写服务档案: $HOST/$NAME"
  ;;

# ---------------- database ----------------
database)
  parse_host_user "$@"; set -- ${REST[@]+"${REST[@]}"}
  NAME="" TYPE="" VER="" DPORT="" DATADIR="" CONFIG="" NOTES=""
  while [[ $# -gt 0 ]]; do case "$1" in
    --name) NAME="$2"; shift 2;; --type) TYPE="$2"; shift 2;;
    --version) VER="$2"; shift 2;; --port) DPORT="$2"; shift 2;;
    --data-dir) DATADIR="$2"; shift 2;; --config) CONFIG="$2"; shift 2;;
    --notes) NOTES="$2"; shift 2;; *) rsc_die "未知参数: $1";; esac; done
  [[ -n "$NAME" ]] || rsc_die "database 需要 --name"
  OBJ=$(jq -cn --arg n "$NAME" --arg t "$TYPE" --arg v "$VER" --arg po "$DPORT" \
    --arg d "$DATADIR" --arg c "$CONFIG" --arg no "$NOTES" --arg now "$(rsc_now)" '
    {name:$n, updated_at:$now}
    + (if $t=="" then {} else {type:$t} end)
    + (if $v=="" then {} else {version:$v} end)
    + (if $po=="" then {} else {port:($po|tonumber)} end)
    + (if $d=="" then {} else {data_dir:$d} end)
    + (if $c=="" then {} else {config:$c} end)
    + (if $no=="" then {} else {notes:$no} end)')
  rsc_jq_update "$(upsert_jq databases name)" \
    --arg h "$HOST" --arg u "$USER" --arg key "$NAME" --argjson obj "$OBJ"
  rsc_info "已回写数据库档案: $HOST/$NAME（凭证用 cred 子命令追加）"
  ;;

# ---------------- middleware ----------------
middleware)
  parse_host_user "$@"; set -- ${REST[@]+"${REST[@]}"}
  NAME="" VER="" MPORT="" CONFIG="" NOTES=""
  while [[ $# -gt 0 ]]; do case "$1" in
    --name) NAME="$2"; shift 2;; --version) VER="$2"; shift 2;;
    --port) MPORT="$2"; shift 2;; --config) CONFIG="$2"; shift 2;;
    --notes) NOTES="$2"; shift 2;; *) rsc_die "未知参数: $1";; esac; done
  [[ -n "$NAME" ]] || rsc_die "middleware 需要 --name"
  OBJ=$(jq -cn --arg n "$NAME" --arg v "$VER" --arg po "$MPORT" --arg c "$CONFIG" \
    --arg no "$NOTES" --arg now "$(rsc_now)" '
    {name:$n, updated_at:$now}
    + (if $v=="" then {} else {version:$v} end)
    + (if $po=="" then {} else {port:($po|tonumber)} end)
    + (if $c=="" then {} else {config:$c} end)
    + (if $no=="" then {} else {notes:$no} end)')
  rsc_jq_update "$(upsert_jq middleware name)" \
    --arg h "$HOST" --arg u "$USER" --arg key "$NAME" --argjson obj "$OBJ"
  rsc_info "已回写中间件档案: $HOST/$NAME"
  ;;

# ---------------- cred ----------------
cred)
  parse_host_user "$@"; set -- ${REST[@]+"${REST[@]}"}
  # 位置参数与标志分离，兼容标志出现在任意位置
  POS=(); PURPOSE=""
  while [[ $# -gt 0 ]]; do case "$1" in
    --purpose|--notes) PURPOSE="$2"; shift 2;;
    *) POS+=("$1"); shift 1;; esac; done
  [[ ${#POS[@]} -ge 1 ]] || rsc_die "用法: cred <host> [--user U] (os|service|database|middleware) [目标名] <账号> <密码> [--purpose T]"
  TARGET_TYPE="${POS[0]}"
  case "$TARGET_TYPE" in
    os)
      [[ ${#POS[@]} -ge 3 ]] || rsc_die "cred os 需要: <账号> <密码>"
      TARGET="os"; CUSER="${POS[1]}"; CPASS="${POS[2]}";;
    service|database|middleware)
      [[ ${#POS[@]} -ge 4 ]] || rsc_die "cred $TARGET_TYPE 需要: <目标名> <账号> <密码>"
      TARGET="${POS[1]}"; CUSER="${POS[2]}"; CPASS="${POS[3]}";;
    *) rsc_die "cred 目标类型只支持 os/service/database/middleware";;
  esac
  NOW="$(rsc_now)"
  CRED=$(jq -cn --arg u "$CUSER" --arg p "$CPASS" --arg no "$PURPOSE" --arg now "$NOW" '
    {username:$u, password:$p, updated_at:$now} + (if $no=="" then {} else {notes:$no} end)')
  case "$TARGET_TYPE" in
    os)
      rsc_jq_update '
        .servers |= map(
          if .host == $h and .auth.username == $u then
            .inspection.accounts |= (
              (map(select(.username == $cu)) | length) as $n
              | if $n > 0 then map(if .username == $cu then . + $cred else . end)
                else . + [$cred] end
            ) | .updated_at = $now
          else . end)
      ' --arg h "$HOST" --arg u "$USER" --arg cu "$CUSER" --argjson cred "$CRED"
      ;;
    service|database|middleware)
      FIELD="${TARGET_TYPE}s"
      [[ "$TARGET_TYPE" == "database" ]] && FIELD="databases"
      rsc_jq_update '
        .servers |= map(
          if .host == $h and .auth.username == $u then
            .inspection[$f] |= map(
              if .name == $t then
                .credentials |= (
                  (. // []) |
                  (map(select(.username == $cu)) | length) as $n
                  | if $n > 0 then map(if .username == $cu then . + $cred else . end)
                    else . + [$cred] end
                ) | .updated_at = $now
              else . end
            ) | .updated_at = $now
          else . end)
      ' --arg h "$HOST" --arg u "$USER" --arg f "$FIELD" --arg t "$TARGET" \
        --arg cu "$CUSER" --argjson cred "$CRED"
      ;;
    *) rsc_die "cred 目标类型只支持 os/service/database/middleware";;
  esac
  rsc_info "已记录凭证: $HOST [$TARGET_TYPE/$TARGET] $CUSER（如需改密，重跑本命令即迭代）"
  ;;

# ---------------- devport ----------------
devport)
  parse_host_user "$@"; set -- ${REST[@]+"${REST[@]}"}
  DPORT="" SVC="" NOTES=""
  while [[ $# -gt 0 ]]; do case "$1" in
    --port) DPORT="$2"; shift 2;; --service) SVC="$2"; shift 2;;
    --notes) NOTES="$2"; shift 2;; *) rsc_die "未知参数: $1";; esac; done
  [[ -n "$DPORT" ]] || rsc_die "devport 需要 --port"
  OBJ=$(jq -cn --arg po "$DPORT" --arg s "$SVC" --arg no "$NOTES" --arg now "$(rsc_now)" '
    {port:($po|tonumber), updated_at:$now}
    + (if $s=="" then {} else {service:$s} end)
    + (if $no=="" then {} else {notes:$no} end)')
  rsc_jq_update "$(upsert_jq dev_ports port)" \
    --arg h "$HOST" --arg u "$USER" --argjson key "$DPORT" --argjson obj "$OBJ"
  rsc_info "已记录开发端口: $HOST:$DPORT"
  ;;

# ---------------- note ----------------
note)
  parse_host_user "$@"; set -- ${REST[@]+"${REST[@]}"}
  TEXT="$*"
  [[ -n "$TEXT" ]] || rsc_die "note 需要备注文本"
  rsc_jq_update '
    .servers |= map(
      if .host == $h and .auth.username == $u then
        .inspection.notes |= ((. // []) + [{time: $now, text: $t}])
        | .updated_at = $now
      else . end)
  ' --arg h "$HOST" --arg u "$USER" --arg t "$TEXT"
  rsc_info "已追加备注: $HOST"
  ;;

# ---------------- category ----------------
category)
  parse_host_user "$@"; set -- ${REST[@]+"${REST[@]}"}
  CAT="$*"
  [[ -n "$CAT" ]] || rsc_die "category 需要分类名，如: 生产/测试/数据库/NAS"
  rsc_jq_update '
    .servers |= map(
      if .host == $h and .auth.username == $u then .category = $c | .updated_at = $now
      else . end)
  ' --arg h "$HOST" --arg u "$USER" --arg c "$CAT"
  rsc_info "已更新分类: $HOST → $CAT"
  ;;

# ---------------- watch ----------------
watch)
  parse_host_user "$@"; set -- ${REST[@]+"${REST[@]}"}
  NAME="" MATCH="" STARTCMD="" AUTO="false"
  while [[ $# -gt 0 ]]; do case "$1" in
    --name) NAME="$2"; shift 2;; --match) MATCH="$2"; shift 2;;
    --start-cmd) STARTCMD="$2"; shift 2;; --auto-restart) AUTO="true"; shift 1;;
    *) rsc_die "未知参数: $1";; esac; done
  [[ -n "$NAME" && -n "$MATCH" ]] || rsc_die "watch 需要 --name 和 --match（进程匹配串）"
  OBJ=$(jq -cn --arg n "$NAME" --arg m "$MATCH" --arg s "$STARTCMD" --arg a "$AUTO" '
    {name:$n, match:$m, auto_restart:($a=="true")}
    + (if $s=="" then {} else {start_cmd:$s} end)')
  rsc_jq_update '
    .servers |= map(
      if .host == $h and .auth.username == $u then
        .watch_services |= (
          (map(select(.name == $key)) | length) as $n
          | if $n > 0 then map(if .name == $key then . + $obj else . end)
            else . + [$obj] end
        ) | .updated_at = $now
      else . end)
  ' --arg h "$HOST" --arg u "$USER" --arg key "$NAME" --argjson obj "$OBJ"
  rsc_info "已配置关注服务: $HOST/$NAME (auto_restart=$AUTO)"
  ;;

-h|--help|"") sed -n '2,20p' "$0";;
*) rsc_die "未知子命令: $ACTION（用 --help 查看用法）";;
esac
