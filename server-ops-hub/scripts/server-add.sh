#!/usr/bin/env bash
#===============================================================================
# server-add.sh — 登记/更新服务器连接信息
#
# 用法:
#   server-add.sh --host <ip> [--port 22] --user <name>
#                 (--key <key_name> | --password <ssh密码>)
#                 [--category <分类>] [--tags tag1,tag2]
#                 [--root-password <root密码>] [--become-root]
#                 [--note "备注"]
#
# 说明:
#   - 唯一键 = host + port + username；已存在则更新提供的字段（upsert）
#   - --key NAME     使用 keys/NAME 私钥做免密登录（密钥先用 key-manage.sh 准备）
#   - --password P   使用用户名+密码登录（需要本机安装 sshpass）
#   - --root-password 与 --become-root: 巡检脚本自动 su - root 提权
#
# 示例:
#   server-add.sh --host 10.0.0.5 --user root --password 'YourPass@123' --category 生产
#   server-add.sh --host 10.0.0.6 --user ops --key default --root-password 'xxx' --become-root
#===============================================================================
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/lib-common.sh"

HOST="" PORT=22 USER="" KEY="" PASS="" CATEGORY="" TAGS="" ROOT_PASS="" BECOME="" NOTE=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --host) HOST="$2"; shift 2;;
    --port) PORT="$2"; shift 2;;
    --user|--username) USER="$2"; shift 2;;
    --key) KEY="$2"; shift 2;;
    --password) PASS="$2"; shift 2;;
    --category) CATEGORY="$2"; shift 2;;
    --tags) TAGS="$2"; shift 2;;
    --root-password) ROOT_PASS="$2"; shift 2;;
    --become-root) BECOME="true"; shift 1;;
    --note) NOTE="$2"; shift 2;;
    -h|--help) sed -n '2,20p' "$0"; exit 0;;
    *) rsc_die "未知参数: $1（用 --help 查看用法）";;
  esac
done

[[ -n "$HOST" && -n "$USER" ]] || rsc_die "必须提供 --host 和 --user"
[[ -n "$KEY" && -n "$PASS" ]] && rsc_die "--key 与 --password 只能二选一"
[[ "$PORT" =~ ^[0-9]+$ ]] && [[ "$PORT" -ge 1 && "$PORT" -le 65535 ]] || rsc_die "无效端口: $PORT"

# 密钥认证时先确认私钥存在
if [[ -n "$KEY" ]]; then
  [[ -f "$RSC_KEYS_DIR/$KEY" ]] || rsc_die "私钥不存在: $RSC_KEYS_DIR/$KEY ，先执行 key-manage.sh generate/import $KEY"
fi

NOW="$(rsc_now)"
ATYPE=""
[[ -n "$KEY" ]] && ATYPE="key"
[[ -n "$PASS" ]] && ATYPE="password"

rsc_ensure_files

# tags 逗号分隔转 JSON 数组
TAGS_JSON="null"
[[ -n "$TAGS" ]] && TAGS_JSON=$(jq -cn --arg t "$TAGS" '$t | split(",") | map(gsub("^\\s+|\\s+$";"")) | map(select(length>0))')

rsc_jq_update '
  (.servers | map(select(.host == $h and .port == ($p|tonumber) and .auth.username == $u))) as $m
  | if ($m | length) > 0 then
      # 更新已有档案：只覆盖调用方提供的字段
      .servers |= map(
        if .host == $h and .port == ($p|tonumber) and .auth.username == $u then
          .category        = (if $c  == "" then .category else $c end)
          | .tags          = (if $tg == null then .tags else ($tg|fromjson) end)
          | .auth.type           = (if $at == "" then .auth.type else $at end)
          | .auth.key_name       = (if $at == "key" then $k else .auth.key_name end)
          | .auth.key_names      = (if $at == "key" then (((.auth.key_names // []) + [$k]) | unique) else (.auth.key_names // []) end)
          | .auth.password       = (if $at == "password" then $pw else .auth.password end)
          | .auth.root_password  = (if $rp == "" then .auth.root_password else $rp end)
          | .auth.become_root    = (if $br == "" then .auth.become_root else ($br == "true") end)
          | .inspection.notes    = (if $nt == "" then .inspection.notes else (.inspection.notes // []) + [{time: $now, text: $nt}] end)
          | .updated_at = $now
        else . end)
    else
      # 新建档案
      .servers += [{
        host: $h,
        port: ($p|tonumber),
        category: (if $c == "" then "未分类" else $c end),
        tags: (if $tg == null then [] else ($tg|fromjson) end),
        auth: {
          type: (if $at == "" then "key" else $at end),
          username: $u,
          key_name: (if $at == "key" then $k else "" end),
          key_names: (if $at == "key" then [$k] else [] end),
          password: (if $at == "password" then $pw else "" end),
          root_password: $rp,
          become_root: ($br == "true")
        },
        watch_services: [],
        inspection: {
          last_check: "", hostname: "", os: "", kernel: "",
          listening_ports: [], services: [], databases: [],
          middleware: [], dev_ports: [], accounts: [],
          notes: (if $nt == "" then [] else [{time: $now, text: $nt}] end)
        },
        created_at: $now,
        updated_at: $now
      }]
    end
' --arg h "$HOST" --arg p "$PORT" --arg u "$USER" \
  --arg c "$CATEGORY" --arg tg "$TAGS_JSON" \
  --arg at "$ATYPE" --arg k "$KEY" --arg pw "$PASS" \
  --arg rp "$ROOT_PASS" --arg br "$BECOME" --arg nt "$NOTE"

rsc_info "档案已保存: $USER@$HOST:$PORT (认证: ${ATYPE:-保持原值})"
rsc_info "查看: server-show.sh $HOST --user $USER ；巡检: server-check.sh $HOST --user $USER"
