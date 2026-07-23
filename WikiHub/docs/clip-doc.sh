#!/bin/bash
# WikiHub · 收 .doc / .pptx / .pdf / 任意文件到指定 wiki 的 SOP
# 用法:
#   ./clip-doc.sh <wiki-name> <source-file> [--title "..."]
# 例:
#   ./clip-doc.sh compliance-meeting /path/to/某文件.doc --title "某标题"

set -euo pipefail

WIKI="$1"
SRC="$2"
TITLE=""
shift 2

while [[ $# -gt 0 ]]; do
  case "$1" in
    --title) TITLE="$2"; shift 2;;
    *) echo "unknown arg: $1" >&2; exit 1;;
  esac
done

WIKIHUB=/home/tangzhiang/.copaw/workspaces/DevOpsMain_writer/skills/WikiHub/scripts/wikihub
SOFFICE=/opt/libreoffice26.2/program/soffice

if [[ -z "$SRC" ]]; then
  echo "usage: $0 <wiki-name> <source-file> [--title '...']" >&2
  exit 1
fi

EXT_LOWER="$(echo "${SRC##*.}" | tr '[:upper:]' '[:lower:]')"

# .doc 是老 Word 格式，markitdown 不直接支持
# 走 LibreOffice 转 .docx → 再让 wikihub clip
if [[ "$EXT_LOWER" == "doc" ]]; then
  TMPDIR=$(mktemp -d)
  echo "[clip-doc] .doc detected -> convert to .docx via LibreOffice..."
  $SOFFICE --headless --convert-to docx --outdir "$TMPDIR" "$SRC" >/dev/null 2>&1
  CONVERTED="$TMPDIR/$(basename "${SRC%.*}").docx"
  if [[ ! -f "$CONVERTED" ]]; then
    echo "[clip-doc] ERROR: LibreOffice conversion failed" >&2
    rm -rf "$TMPDIR"
    exit 2
  fi
  SRC="$CONVERTED"
  echo "[clip-doc] converted -> $SRC"
fi

EXTRA=()
if [[ -n "$TITLE" ]]; then
  EXTRA+=(--title "$TITLE")
fi

python3 "$WIKIHUB" clip "$WIKI" --source "$SRC" "${EXTRA[@]}"

if [[ -n "${CONVERTED:-}" ]]; then
  rm -rf "$(dirname "$CONVERTED")"
fi