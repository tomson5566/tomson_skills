#!/usr/bin/env bash
#===============================================================================
# export-import.sh — skill 迁移工具（换 agent 主机 / 备份 / 分发）
#
# 用法:
#   export-import.sh export [--out FILE] [--with-reports]
#   export-import.sh import <FILE> [--dest DIR]
#
# 说明:
#   - 整个 skill 目录就是可迁移单元：档案(servers.json) + 密钥(keys/) + 脚本
#   - export 默认排除 reports/（体积考虑），--with-reports 可带上历史报告
#   - import 自动修复权限: keys/ 700、私钥 600、scripts/*.sh +x
#   - 导入后即可用原密钥或密码登录所有服务器，无需任何重建
#===============================================================================
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/lib-common.sh"

cmd_export() {
  local out="" with_reports=""
  while [[ $# -gt 0 ]]; do case "$1" in
    --out) out="$2"; shift 2;;
    --with-reports) with_reports="true"; shift 1;;
    *) rsc_die "未知参数: $1";; esac; done

  [[ -z "$out" ]] && out="./server-ops-hub-export-$(date +%Y%m%d-%H%M%S).tar.gz"

  local skill_name
  skill_name=$(basename "$RSC_HOME")

  # MANIFEST（不含私钥内容，仅元数据）
  local manifest
  manifest=$(mktemp)
  {
    echo "export_time: $(rsc_now)"
    echo "export_from: $(hostname 2>/dev/null || echo unknown)"
    echo "skill: $skill_name"
    echo "servers: $(jq '.servers | length' "$RSC_CONFIG" 2>/dev/null || echo 0)"
    echo "servers_sha256: $(sha256sum "$RSC_CONFIG" 2>/dev/null | awk '{print $1}')"
    echo "keys: $(ls "$RSC_KEYS_DIR" 2>/dev/null | grep -v '\.pub$' | grep -v README | tr '\n' ' ')"
    echo "with_reports: ${with_reports:-false}"
  } > "$manifest"

  local -a excludes=(--exclude='.DS_Store' --exclude='*/__pycache__/*')
  [[ "$with_reports" != "true" ]] && excludes+=(--exclude="$skill_name/reports/*")

  # 把 MANIFEST 临时放进 skill 目录一起打包
  cp "$manifest" "$RSC_HOME/MANIFEST.tmp"
  tar czf "$out" -C "$(dirname "$RSC_HOME")" "${excludes[@]}" \
    --transform "s,MANIFEST.tmp,MANIFEST," "$skill_name"
  rm -f "$RSC_HOME/MANIFEST.tmp" "$manifest"

  rsc_info "✅ 已导出: $out （$(du -h "$out" | awk '{print $1}')）"
  rsc_warn "⚠️  该文件包含私钥与明文密码，请加密存储/传输（如 gpg -c），用完即删"
}

cmd_import() {
  local file="${1:-}" dest="." 
  shift || rsc_die "用法: export-import.sh import <FILE> [--dest DIR]"
  while [[ $# -gt 0 ]]; do case "$1" in
    --dest) dest="$2"; shift 2;;
    *) rsc_die "未知参数: $1";; esac; done
  [[ -f "$file" ]] || rsc_die "导入文件不存在: $file"

  tar xzf "$file" -C "$dest"
  # 取压缩包顶层目录名；用 sed 读全量避免 head 提前关闭导致 tar 收 SIGPIPE（pipefail 下会误判失败）
  local dir
  dir=$(tar tzf "$file" 2>/dev/null | sed -n '1p' | cut -d/ -f1)
  local target="$dest/$dir"
  [[ -n "$dir" && -d "$target" ]] || rsc_die "解压异常，未找到目录: $target"

  # 修复权限（tar 不保证 umask 一致）
  chmod 700 "$target/keys" 2>/dev/null || true
  find "$target/keys" -type f ! -name '*.pub' ! -name 'README*' -exec chmod 600 {} \; 2>/dev/null || true
  find "$target/keys" -type f -name '*.pub' -exec chmod 644 {} \; 2>/dev/null || true
  chmod +x "$target/scripts/"*.sh 2>/dev/null || true
  chmod 600 "$target/config/servers.json" 2>/dev/null || true

  rsc_info "✅ 导入完成: $target"
  [[ -f "$target/MANIFEST" ]] && { echo "----- MANIFEST -----"; cat "$target/MANIFEST"; }
  cat <<EOF

后续检查清单:
  1. 确认依赖: command -v ssh jq （密码认证还需 sshpass）
  2. 查看档案: $target/scripts/server-list.sh
  3. 连通性自检: $target/scripts/ssh-run.sh <host> "echo ok"
  4. 缺密钥时: $target/scripts/key-manage.sh import default /path/to/私钥
EOF
}

ACTION="${1:-}"; shift || true
case "$ACTION" in
  export) cmd_export "$@";;
  import) cmd_import "$@";;
  -h|--help|"") sed -n '2,16p' "$0";;
  *) rsc_die "未知子命令: $ACTION";;
esac
