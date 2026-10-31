#!/usr/bin/env bash
#===============================================================================
# key-manage.sh — SSH 密钥池管理（多台设备的免密密钥统一托管在 keys/，随目录迁移）
#
# 用法:
#   key-manage.sh list                                   # 密钥池总览（含来源设备/绑定服务器）
#   key-manage.sh generate <name> [--type ed25519|rsa]   # 生成新密钥对
#   key-manage.sh import <name> <私钥文件> [--device D] [--comment T]   # 导入已有私钥
#   key-manage.sh import-all <目录> --device D           # 批量导入某台设备的所有私钥
#   key-manage.sh pub <name>                             # 打印公钥内容
#   key-manage.sh bind <host> [--user U] --key NAME      # 把密钥绑定到服务器（可绑多个）
#   key-manage.sh unbind <host> [--user U] --key NAME    # 解绑
#   key-manage.sh deploy <host> [--user U] [--key NAME]  # 部署单个公钥到服务器并切免密
#   key-manage.sh deploy-all <host> [--user U]           # 部署密钥池全部公钥到服务器
#
# 多设备统一管理模型:
#   - keys/ 是中央密钥池：把每台 agent 主机/笔记本的私钥都导入进来，
#     每个密钥在 keys/index.json 登记来源设备(source_device)、指纹、备注
#   - 每台服务器 auth.key_names 是"可登录密钥列表"（按顺序自动尝试），
#     例如某服务器同时绑了 openclaw 主机和笔记本的密钥，从哪台设备都能连
#   - 整个 skill 目录拷到任意机器 = 密钥池 + 绑定关系完整迁移
#===============================================================================
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/lib-common.sh"

# 从 index.json 取某密钥的登记信息（device|comment）
_key_meta() {
  local name="$1"
  [[ -f "$RSC_KEYS_INDEX" ]] || { printf '|'; return; }
  jq -r --arg n "$name" '.keys[] | select(.name==$n) | "\(.source_device)|\(.comment)"' "$RSC_KEYS_INDEX" 2>/dev/null | head -1
}

cmd_list() {
  rsc_ensure_files
  shopt -s nullglob
  local keys=()
  local f
  for f in "$RSC_KEYS_DIR"/*; do
    [[ "$f" == *.pub || "$f" == *README* || "$f" == *.json ]] && continue
    keys+=("$f")
  done
  if [[ ${#keys[@]} -eq 0 ]]; then
    rsc_warn "密钥池为空。生成: key-manage.sh generate default；导入单机: key-manage.sh import <name> <私钥>；批量导入某设备: key-manage.sh import-all ~/.ssh --device 笔记本"
    return 0
  fi
  printf '\033[1m%-24s %-10s %-16s %-30s %s\033[0m\n' "NAME" "TYPE" "SOURCE_DEVICE" "FINGERPRINT" "绑定的服务器"
  for f in "${keys[@]}"; do
    local name type info dev bound
    name=$(basename "$f")
    if command -v ssh-keygen >/dev/null 2>&1; then
      info=$(ssh-keygen -lf "$f" 2>/dev/null) || info="(无法读取指纹)"
      type=$(awk '{print $4}' <<<"$info")
      info=$(awk '{print $2}' <<<"$info")
    else
      type="?"; info="$(rsc_key_fingerprint "$f")"
    fi
    dev=$(_key_meta "$name"); dev="${dev%%|*}"
    # 绑定了该密钥的服务器
    bound=$(jq -r --arg k "$name" '
      .servers[] | select(
        ((.auth.key_names // []) + [(.auth.key_name // "")]) | index($k) != null
      ) | .host + "/" + .auth.username' "$RSC_CONFIG" | paste -sd, -)
    printf '%-24s %-10s %-16s %-30s %s\n' "$name" "$type" "${dev:--}" "$info" "${bound:--}"
  done
  echo
  rsc_info "密钥目录: $RSC_KEYS_DIR （权限 700，私钥 600；登记信息: keys/index.json）"
}

cmd_generate() {
  local name="${1:-}" type="${3:-ed25519}"
  [[ -n "$name" ]] || rsc_die "用法: key-manage.sh generate <name> [--type ed25519|rsa]"
  [[ "$name" =~ ^[a-zA-Z0-9_-]+$ ]] || rsc_die "密钥名只允许字母数字_-: $name"
  command -v ssh-keygen >/dev/null 2>&1 || rsc_die "缺少 ssh-keygen。安装 openssh-client/openssh-clients"
  local f="$RSC_KEYS_DIR/$name"
  [[ -f "$f" ]] && rsc_die "密钥已存在: $f（如需重建请先删除旧密钥及 keys/index.json 中的登记）"
  mkdir -p "$RSC_KEYS_DIR"; chmod 700 "$RSC_KEYS_DIR"
  local dev
  dev=$(hostname 2>/dev/null || echo "unknown")
  if [[ "$type" == "rsa" ]]; then
    ssh-keygen -t rsa -b 4096 -f "$f" -N "" -C "server-ops-hub/$name@$dev-$(date +%Y%m%d)"
  else
    ssh-keygen -t ed25519 -f "$f" -N "" -C "server-ops-hub/$name@$dev-$(date +%Y%m%d)"
  fi
  chmod 600 "$f"; chmod 644 "$f.pub"
  rsc_key_register "$name" "$dev" "generated"
  rsc_info "密钥对已生成: $f / $f.pub"
  rsc_info "下一步: key-manage.sh deploy <host> --key $name 把公钥部署到服务器"
}

# 导入单个私钥的内部实现（供 import / import-all 复用）
_import_one() {
  local name="$1" src="$2" dev="$3" comment="$4"
  [[ "$name" =~ ^[a-zA-Z0-9_-]+$ ]] || { rsc_err "密钥名只允许字母数字_-: $name"; return 1; }
  [[ -f "$src" ]] || { rsc_err "源私钥文件不存在: $src"; return 1; }
  grep -q "PRIVATE KEY" "$src" || { rsc_err "不是有效私钥（缺少 PRIVATE KEY 头）: $src"; return 1; }
  local f="$RSC_KEYS_DIR/$name"
  [[ -f "$f" ]] && { rsc_err "密钥已存在，跳过: $name"; return 1; }
  mkdir -p "$RSC_KEYS_DIR"; chmod 700 "$RSC_KEYS_DIR"
  cp "$src" "$f"; chmod 600 "$f"
  if [[ -f "$src.pub" ]]; then
    cp "$src.pub" "$f.pub"; chmod 644 "$f.pub"
  elif command -v ssh-keygen >/dev/null 2>&1; then
    ssh-keygen -y -f "$f" > "$f.pub" 2>/dev/null && chmod 644 "$f.pub" \
      || { rm -f "$f"; rsc_err "无法从私钥导出公钥，文件可能损坏: $src"; return 1; }
  else
    rsc_warn "无 ssh-keygen，未生成 $f.pub；deploy 时需要公钥，请补上"
  fi
  rsc_key_register "$name" "$dev" "$comment"
  rsc_info "私钥已导入: $name (来源设备: ${dev:-未标注})"
}

cmd_import() {
  local name="${1:-}" src="${2:-}" dev="" comment="imported"
  shift 2 || true
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --device) dev="$2"; shift 2;;
      --comment) comment="$2"; shift 2;;
      *) rsc_die "未知参数: $1";;
    esac
  done
  [[ -n "$name" && -n "$src" ]] || rsc_die "用法: key-manage.sh import <name> <私钥文件> [--device D] [--comment T]"
  _import_one "$name" "$src" "$dev" "$comment"
}

cmd_import_all() {
  local dir="${1:-}" device=""
  shift || true
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --device) device="$2"; shift 2;;
      *) rsc_die "未知参数: $1";;
    esac
  done
  [[ -n "$dir" && -d "$dir" ]] || rsc_die "用法: key-manage.sh import-all <目录> --device <设备名>（如 import-all ~/.ssh --device openclaw主机）"
  [[ -n "$device" ]] || rsc_die "必须用 --device 标注来源设备，否则多设备密钥无法区分"
  local ok=0 skip=0 f base name
  shopt -s nullglob
  for f in "$dir"/*; do
    base=$(basename "$f")
    # 跳过公钥、known_hosts、配置等非私钥文件
    case "$base" in
      *.pub|known_hosts*|config|authorized_keys|*.md|*.json|.*) continue;;
    esac
    grep -q "PRIVATE KEY" "$f" 2>/dev/null || continue
    name="${device}_${base}"
    if _import_one "$name" "$f" "$device" "import-all from $dir"; then
      ok=$((ok+1))
    else
      skip=$((skip+1))
    fi
  done
  rsc_info "批量导入完成: 成功 $ok 个，跳过/失败 $skip 个。命名规则: ${device}_<原文件名>"
  rsc_info "接下来可对各服务器执行: key-manage.sh bind <host> --key <name> 或 deploy-all <host>"
}

cmd_pub() {
  local name="${1:-}"
  [[ -n "$name" ]] || rsc_die "用法: key-manage.sh pub <name>"
  local f="$RSC_KEYS_DIR/$name"
  if [[ -f "$f.pub" ]]; then
    cat "$f.pub"
  elif [[ -f "$f" ]] && command -v ssh-keygen >/dev/null 2>&1; then
    ssh-keygen -y -f "$f"
  else
    rsc_die "找不到公钥: $f.pub"
  fi
}

# 绑定/解绑共用解析
_parse_host_user_key() {
  HOST_ARG="${1:-}"; shift || true
  USER_ARG="" KEY_ARG=""
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --user|--username) USER_ARG="$2"; shift 2;;
      --key) KEY_ARG="$2"; shift 2;;
      *) rsc_die "未知参数: $1";;
    esac
  done
  [[ -n "$HOST_ARG" && -n "$KEY_ARG" ]] || rsc_die "需要 <host> 和 --key <name>"
}

cmd_bind() {
  _parse_host_user_key "$@"
  [[ -f "$RSC_KEYS_DIR/$KEY_ARG" ]] || rsc_die "密钥池中不存在私钥: $KEY_ARG，先 generate/import/import-all"
  local srv luser
  srv=$(rsc_server_json "$HOST_ARG" "$USER_ARG" "")
  luser=$(jq -r '.auth.username' <<<"$srv")
  rsc_jq_update '
    .servers |= map(
      if .host == $h and .auth.username == $u then
        .auth.key_names = (((.auth.key_names // []) + [$k]) | unique)
        | .auth.key_name = ((.auth.key_name // "") | if . == "" then $k else . end)
        | .updated_at = $now
      else . end)
  ' --arg h "$HOST_ARG" --arg u "$luser" --arg k "$KEY_ARG"
  rsc_info "已绑定: $KEY_ARG -> $luser@$HOST_ARG（连接时按 key_names 顺序自动尝试）"
  if [[ "$(jq -r '.auth.type' <<<"$srv")" != "key" ]]; then
    rsc_warn "该档案当前是密码认证。确认公钥已部署到服务器后，用 key-manage.sh deploy $HOST_ARG --key $KEY_ARG 一键切换"
  fi
}

cmd_unbind() {
  _parse_host_user_key "$@"
  local srv luser
  srv=$(rsc_server_json "$HOST_ARG" "$USER_ARG" "")
  luser=$(jq -r '.auth.username' <<<"$srv")
  rsc_jq_update '
    .servers |= map(
      if .host == $h and .auth.username == $u then
        .auth.key_names = (((.auth.key_names // []) - [$k]))
        | .updated_at = $now
      else . end)
  ' --arg h "$HOST_ARG" --arg u "$luser" --arg k "$KEY_ARG"
  rsc_info "已解绑: $KEY_ARG -/-> $luser@$HOST_ARG（仅改档案，不动远端 authorized_keys）"
}

cmd_deploy() {
  local host="${1:-}" user="" keyname=""
  shift || true
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --user|--username) user="$2"; shift 2;;
      --key) keyname="$2"; shift 2;;
      *) rsc_die "未知参数: $1";;
    esac
  done
  [[ -n "$host" ]] || rsc_die "用法: key-manage.sh deploy <host> [--user U] [--key NAME]"

  local srv
  srv=$(rsc_server_json "$host" "$user" "")
  if [[ -z "$keyname" ]]; then
    keyname=$(jq -r '.auth.key_name // ""' <<<"$srv")
    [[ -n "$keyname" ]] || keyname=$(jq -r '(.auth.key_names // [])[0] // ""' <<<"$srv")
    [[ -n "$keyname" ]] || keyname="default"
  fi

  local pub
  pub=$(cmd_pub "$keyname") || rsc_die "密钥 $keyname 不存在，先 generate/import"

  local luser
  luser=$(jq -r '.auth.username' <<<"$srv")
  rsc_info "正在用现有认证方式登录 $luser@$host 部署公钥 ($keyname) ..."

  # 用当前档案认证方式把公钥追加到远端 authorized_keys（幂等）
  local remote_cmd
  remote_cmd="mkdir -p ~/.ssh && chmod 700 ~/.ssh && touch ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys && grep -qF '$pub' ~/.ssh/authorized_keys 2>/dev/null || echo '$pub' >> ~/.ssh/authorized_keys; echo DEPLOY_OK"
  local out
  out=$(rsc_ssh_run "$srv" "$remote_cmd") || rsc_die "部署失败：无法用现有认证登录 $host，请检查档案中的密码/密钥"
  grep -q "DEPLOY_OK" <<<"$out" || rsc_die "部署结果异常: $out"

  # 切换档案为 key 认证，并把该密钥纳入绑定列表
  rsc_jq_update '
    .servers |= map(
      if .host == $h and .auth.username == $u then
        .auth.type = "key" | .auth.key_name = $k
        | .auth.key_names = (((.auth.key_names // []) + [$k]) | unique)
        | .updated_at = $now
      else . end)
  ' --arg h "$host" --arg u "$luser" --arg k "$keyname"

  # 验证免密连通性
  local srv_new
  srv_new=$(rsc_server_json "$host" "$luser" "")
  if rsc_ssh_run "$srv_new" "echo KEY_AUTH_OK" 2>/dev/null | grep -q KEY_AUTH_OK; then
    rsc_info "✅ 免密登录验证通过: $luser@$host (key=$keyname)"
  else
    rsc_warn "公钥已写入且档案已切换为 key 认证，但免密验证失败。可能远端 sshd 禁用了密钥认证，请人工检查 /etc/ssh/sshd_config (PubkeyAuthentication)"
  fi
}

cmd_deploy_all() {
  local host="${1:-}" user=""
  shift || true
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --user|--username) user="$2"; shift 2;;
      *) rsc_die "未知参数: $1";;
    esac
  done
  [[ -n "$host" ]] || rsc_die "用法: key-manage.sh deploy-all <host> [--user U]"

  # 收集密钥池全部公钥
  shopt -s nullglob
  local pubs=() names=() f
  for f in "$RSC_KEYS_DIR"/*.pub; do
    pubs+=("$(cat "$f")")
    names+=("$(basename "$f" .pub)")
  done
  [[ ${#pubs[@]} -gt 0 ]] || rsc_die "密钥池为空（无 .pub 文件），先 generate/import"

  local srv luser
  srv=$(rsc_server_json "$host" "$user" "")
  luser=$(jq -r '.auth.username' <<<"$srv")
  rsc_info "将把密钥池 ${#pubs[@]} 个公钥部署到 $luser@$host: ${names[*]}"

  # 一次性远程执行：逐个幂等追加
  local remote_cmd="mkdir -p ~/.ssh && chmod 700 ~/.ssh && touch ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys"
  local p
  for p in "${pubs[@]}"; do
    remote_cmd="$remote_cmd && (grep -qF '$p' ~/.ssh/authorized_keys 2>/dev/null || echo '$p' >> ~/.ssh/authorized_keys)"
  done
  remote_cmd="$remote_cmd; echo DEPLOY_ALL_OK"
  local out
  out=$(rsc_ssh_run "$srv" "$remote_cmd") || rsc_die "部署失败：无法用现有认证登录 $host，请检查档案中的密码/密钥"
  grep -q "DEPLOY_ALL_OK" <<<"$out" || rsc_die "部署结果异常: $out"

  # 档案切换为 key 认证，绑定全部密钥
  local names_json
  names_json=$(printf '%s\n' "${names[@]}" | jq -R . | jq -sc .)
  rsc_jq_update '
    .servers |= map(
      if .host == $h and .auth.username == $u then
        .auth.type = "key"
        | .auth.key_names = (((.auth.key_names // []) + ($ks | fromjson)) | unique)
        | .auth.key_name = (((.auth.key_names // []) + ($ks | fromjson)) | unique | .[0])
        | .updated_at = $now
      else . end)
  ' --arg h "$host" --arg u "$luser" --arg ks "$names_json"

  local srv_new
  srv_new=$(rsc_server_json "$host" "$luser" "")
  if rsc_ssh_run "$srv_new" "echo KEY_AUTH_OK" 2>/dev/null | grep -q KEY_AUTH_OK; then
    rsc_info "✅ 免密登录验证通过: $luser@$host（${#names[@]} 个密钥均可用于连接，按绑定顺序自动尝试）"
  else
    rsc_warn "公钥已写入且档案已更新，但免密验证失败，请人工检查远端 sshd 配置"
  fi
}

ACTION="${1:-}"; shift || true
case "$ACTION" in
  list) cmd_list "$@";;
  generate) cmd_generate "$@";;
  import) cmd_import "$@";;
  import-all) cmd_import_all "$@";;
  pub) cmd_pub "$@";;
  bind) cmd_bind "$@";;
  unbind) cmd_unbind "$@";;
  deploy) cmd_deploy "$@";;
  deploy-all) cmd_deploy_all "$@";;
  -h|--help|"") sed -n '2,21p' "$0";;
  *) rsc_die "未知子命令: $ACTION（用 --help 查看用法）";;
esac
