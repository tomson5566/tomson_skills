#!/usr/bin/env bash
#===============================================================================
# lib-common.sh — server-ops-hub 公共函数库
# 被 scripts/*.sh source，不要直接执行
#
# 可迁移性设计：
#   所有路径都相对本文件自身位置解析（RSC_HOME = skill 根目录），
#   整个 skill 目录拷到任意机器即可用，无需改任何配置。
#   也可用环境变量 RSC_HOME / RSC_CONFIG 覆盖（测试或多档案场景）。
#===============================================================================

# ---- 路径解析（相对自身，禁止硬编码绝对路径）----
RSC_HOME="${RSC_HOME:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
RSC_CONFIG="${RSC_CONFIG:-$RSC_HOME/config/servers.json}"
RSC_KEYS_DIR="${RSC_KEYS_DIR:-$RSC_HOME/keys}"
RSC_KEYS_INDEX="${RSC_KEYS_INDEX:-$RSC_KEYS_DIR/index.json}"
RSC_REPORTS_DIR="${RSC_REPORTS_DIR:-$RSC_HOME/reports}"
RSC_SSH_TIMEOUT="${RSC_SSH_TIMEOUT:-10}"

# ---- 输出 ----
rsc_info() { printf '\033[32m[INFO]\033[0m %s\n' "$*" >&2; }
rsc_warn() { printf '\033[33m[WARN]\033[0m %s\n' "$*" >&2; }
rsc_err()  { printf '\033[31m[ERROR]\033[0m %s\n' "$*" >&2; }
rsc_die()  { rsc_err "$*"; exit 1; }

rsc_now() { date '+%Y-%m-%dT%H:%M:%S%z'; }

# ---- 巡检报告留存策略 ----
# 读取报告保留天数：环境变量 RSC_REPORT_KEEP_DAYS > servers.json settings.report_keep_days > 默认 30
rsc_report_keep_days() {
  if [[ -n "${RSC_REPORT_KEEP_DAYS:-}" ]]; then
    echo "$RSC_REPORT_KEEP_DAYS"; return
  fi
  if command -v jq >/dev/null 2>&1 && [[ -f "$RSC_CONFIG" ]]; then
    local d
    d=$(jq -r '.settings.report_keep_days // empty' "$RSC_CONFIG" 2>/dev/null)
    [[ -n "$d" ]] && { echo "$d"; return; }
  fi
  echo 30
}

# 清理 reports/ 下超过保留期的 .log 报告；$1=天数（可选，默认走策略）$2=dry-run（传 "dry" 只列不删）
rsc_report_cleanup() {
  local days="${1:-$(rsc_report_keep_days)}" dry="${2:-}"
  [[ -d "$RSC_REPORTS_DIR" ]] || return 0
  [[ "$days" =~ ^[0-9]+$ ]] || { rsc_warn "保留天数无效: $days，跳过清理"; return 0; }
  local -a old=()
  while IFS= read -r f; do old+=("$f"); done < <(find "$RSC_REPORTS_DIR" -maxdepth 1 -type f -name '*.log' -mtime +"$days" 2>/dev/null)
  if [[ ${#old[@]} -eq 0 ]]; then
    rsc_info "报告清理：无超过 ${days} 天的巡检报告"
    return 0
  fi
  if [[ "$dry" == "dry" ]]; then
    rsc_warn "以下 ${#old[@]} 份报告超过 ${days} 天保留期（dry-run，未删除）："
    printf '  %s\n' "${old[@]}"
    return 0
  fi
  rm -f "${old[@]}"
  rsc_info "报告清理：已删除 ${#old[@]} 份超过 ${days} 天的巡检报告（保留期: servers.json settings.report_keep_days 或环境变量 RSC_REPORT_KEEP_DAYS 可调）"
}

# ---- 密钥登记（keys/index.json，统一管理多台设备的密钥）----
# 取密钥指纹：优先 ssh-keygen，缺失时退化为文件 sha256 摘要
rsc_key_fingerprint() {
  local f="$1"
  if command -v ssh-keygen >/dev/null 2>&1; then
    ssh-keygen -lf "$f" 2>/dev/null | awk '{print $2}'
  else
    sha256sum "$f" 2>/dev/null | awk '{print "file-sha256:" substr($1,1,16)}'
  fi
}

# 登记/更新密钥元数据。用法: rsc_key_register <name> [source_device] [comment]
rsc_key_register() {
  local name="$1" dev="${2:-}" comment="${3:-}"
  rsc_ensure_files
  local f="$RSC_KEYS_DIR/$name"
  [[ -f "$f" ]] || return 0
  [[ -f "$RSC_KEYS_INDEX" ]] || printf '{"schema_version":1,"keys":[]}\n' > "$RSC_KEYS_INDEX"
  local fp type
  fp=$(rsc_key_fingerprint "$f")
  if command -v ssh-keygen >/dev/null 2>&1; then
    type=$(ssh-keygen -lf "$f" 2>/dev/null | awk '{print $4}')
  fi
  local tmp
  tmp=$(mktemp "${RSC_KEYS_INDEX}.XXXXXX")
  if jq --arg n "$name" --arg t "${type:-?}" --arg fp "$fp" --arg d "$dev" --arg c "$comment" --arg now "$(rsc_now)" '
      .keys |= (map(select(.name != $n))
        + [{name:$n, type:$t, fingerprint:$fp, source_device:$d, comment:$c, created_at:$now}])
    ' "$RSC_KEYS_INDEX" > "$tmp"; then
    mv "$tmp" "$RSC_KEYS_INDEX"
  else
    rm -f "$tmp"
    rsc_warn "密钥登记失败（index.json 写入错误），不影响密钥使用"
  fi
}

# 某台服务器的候选密钥列表（key_names[] + 旧字段 key_name，去重，保持顺序）
rsc_server_key_candidates() {
  local srv="$1"
  jq -r '(((.auth.key_names // []) + [(.auth.key_name // "")]) | map(select(length>0)) | unique)[]' <<<"$srv"
}

# ---- 依赖检查 ----
rsc_require_jq() {
  command -v jq >/dev/null 2>&1 || rsc_die "缺少 jq。安装: apt install -y jq 或 yum install -y jq 或 apk add jq"
}
rsc_require_ssh() {
  command -v ssh >/dev/null 2>&1 || rsc_die "缺少 ssh 客户端。安装: apt install -y openssh-client 或 yum install -y openssh-clients"
}

# ---- 初始化数据文件（首次使用/迁移后自愈）----
rsc_ensure_files() {
  rsc_require_jq
  [[ -d "$RSC_KEYS_DIR" ]] || { mkdir -p "$RSC_KEYS_DIR"; chmod 700 "$RSC_KEYS_DIR"; }
  [[ -d "$RSC_REPORTS_DIR" ]] || mkdir -p "$RSC_REPORTS_DIR"
  if [[ ! -f "$RSC_CONFIG" ]]; then
    printf '{"schema_version":2,"description":"server-ops-hub 服务器资产档案库","updated_at":"%s","settings":{"report_keep_days":30},"servers":[]}\n' "$(rsc_now)" > "$RSC_CONFIG"
    rsc_warn "未找到档案库，已初始化空档案: $RSC_CONFIG"
  fi
  chmod 600 "$RSC_CONFIG" 2>/dev/null || true
}

# ---- 服务器查找 ----
# 用法: rsc_server_json <host> [user] [port]
# 命中唯一一条 → 输出该服务器 JSON；多条 → 报错并列出候选；零条 → 报错
rsc_server_json() {
  local host="$1" user="${2:-}" port="${3:-}"
  rsc_ensure_files
  local filter='.servers | map(select(.host == $h))'
  [[ -n "$user" ]] && filter="$filter | map(select(.auth.username == \$u))"
  [[ -n "$port" ]] && filter="$filter | map(select(.port == (\$p | tonumber)))"
  local result count
  result=$(jq --arg h "$host" --arg u "$user" --arg p "$port" "$filter" "$RSC_CONFIG") \
    || rsc_die "读取档案库失败: $RSC_CONFIG"
  count=$(jq 'length' <<<"$result")
  if [[ "$count" == "0" ]]; then
    rsc_die "档案库中不存在服务器 $host${user:+ (user=$user)}${port:+ (port=$port)}，先用 server-add.sh 登记"
  fi
  if [[ "$count" -gt 1 ]]; then
    rsc_err "主机 $host 存在多条档案，请用 --user 区分:"
    jq -r '.[] | "  - " + .host + ":" + (.port|tostring) + "  user=" + .auth.username + "  category=" + .category' <<<"$result" >&2
    exit 1
  fi
  jq '.[0]' <<<"$result"
}

# ---- 组装并执行 ssh ----
# 用法: rsc_ssh_run <server_json> <remote_command_string>
# 自动按档案选择认证方式:
#   key      -> 按候选列表（auth.key_names + auth.key_name）依次用 keys/<name> 尝试，
#               适配"多台设备各自持有不同密钥"的统一管理场景
#   password -> sshpass
rsc_ssh_run() {
  local srv="$1" cmd="$2"
  rsc_require_ssh
  local host port user atype pass
  host=$(jq -r '.host' <<<"$srv")
  port=$(jq -r '.port' <<<"$srv")
  user=$(jq -r '.auth.username' <<<"$srv")
  atype=$(jq -r '.auth.type' <<<"$srv")
  pass=$(jq -r '.auth.password // ""' <<<"$srv")

  local -a opts=(
    -o ConnectTimeout="$RSC_SSH_TIMEOUT"
    -o StrictHostKeyChecking=no
    -o UserKnownHostsFile=/dev/null
    -o LogLevel=ERROR
    -p "$port"
  )
  case "$atype" in
    key)
      local -a candidates=()
      local k
      while IFS= read -r k; do candidates+=("$k"); done < <(rsc_server_key_candidates "$srv")
      [[ ${#candidates[@]} -gt 0 ]] || rsc_die "$host 为密钥认证但未绑定任何密钥（auth.key_names 为空）。用 key-manage.sh bind/deploy 绑定"
      local -a tried=() missing=()
      for k in "${candidates[@]}"; do
        local keyfile="$RSC_KEYS_DIR/$k"
        if [[ ! -f "$keyfile" ]]; then
          missing+=("$k")
          continue
        fi
        chmod 600 "$keyfile" 2>/dev/null || true
        if ssh "${opts[@]}" -i "$keyfile" -o IdentitiesOnly=yes -o BatchMode=yes -o NumberOfPasswordPrompts=0 "$user@$host" "$cmd"; then
          return 0
        fi
        tried+=("$k")
      done
      rsc_err "所有候选密钥均无法登录 $user@$host（已试: ${tried[*]:-无}${missing:+；密钥文件缺失: ${missing[*]}}）"
      rsc_err "排查: key-manage.sh list 看密钥池；key-manage.sh deploy $host --key <name> 重新部署；或改用密码认证"
      return 1
      ;;
    password)
      [[ -n "$pass" ]] || rsc_die "$host 配置为密码认证但 password 为空，用 server-add.sh --password 更新"
      command -v sshpass >/dev/null 2>&1 || rsc_die "密码认证需要 sshpass。安装: apt install -y sshpass 或 yum install -y sshpass"
      sshpass -p "$pass" ssh "${opts[@]}" "$user@$host" "$cmd"
      ;;
    *) rsc_die "未知认证类型: $atype (只支持 key/password)" ;;
  esac
}

# ---- 以 root 身份执行远程脚本（su - root）----
# 用法: rsc_ssh_run_script <server_json> <local_script_file> [as_root: auto|yes|no]
#   auto = 按档案 auth.become_root 决定
rsc_ssh_run_script() {
  local srv="$1" script_file="$2" as_root="${3:-auto}"
  local rp become host
  rp=$(jq -r '.auth.root_password // ""' <<<"$srv")
  become=$(jq -r '.auth.become_root // false' <<<"$srv")
  host=$(jq -r '.host' <<<"$srv")
  [[ "$as_root" == "auto" ]] && as_root="$become"

  # 远程落盘路径加随机后缀，避免冲突
  local rpath="/tmp/.rsc-check-$$-$(date +%s).sh"
  local b64
  b64=$(base64 < "$script_file" | tr -d '\n')

  if [[ "$as_root" == "true" && -n "$rp" ]]; then
    # 单引号转义密码后拼进 su 管道（与原 skill 验证过的机制一致）
    local sq_rp
    sq_rp=$(printf '%s' "$rp" | sed "s/'/'\\\\''/g")
    rsc_ssh_run "$srv" "echo '$b64' | base64 -d > $rpath && echo '$sq_rp' | su - root -c 'bash $rpath; rc=\$?; rm -f $rpath; exit \$rc'"
  else
    rsc_ssh_run "$srv" "echo '$b64' | base64 -d > $rpath && bash $rpath; rc=\$?; rm -f $rpath; exit \$rc"
  fi
}

# ---- 写库（统一出口，自动刷新 updated_at）----
# 用法: rsc_jq_update <jq_program> [jq 参数...]
#   jq_program 操作在整个档案 JSON 上
rsc_jq_update() {
  local prog="$1"; shift
  rsc_ensure_files
  local tmp
  tmp=$(mktemp "${RSC_CONFIG}.XXXXXX")
  if jq --arg now "$(rsc_now)" "$@" \
      ".updated_at = \$now | $prog" "$RSC_CONFIG" > "$tmp"; then
    chmod 600 "$tmp" 2>/dev/null || true
    mv "$tmp" "$RSC_CONFIG"
  else
    rm -f "$tmp"
    rsc_die "更新档案库失败（jq 错误），档案未改动"
  fi
}
