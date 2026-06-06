#!/usr/bin/env bash
# Java 依赖审计（Maven/Gradle）
# 用法: dep_audit_java.sh <项目根目录>
set -euo pipefail

PROJECT_DIR="${1:-.}"

echo "=== Java 依赖审计 ==="

if [[ -f "$PROJECT_DIR/pom.xml" ]]; then
  echo "[Maven 项目]"
  if command -v mvn &>/dev/null; then
    echo "--- dependency:tree ---"
    (cd "$PROJECT_DIR" && mvn dependency:tree -DoutputType=text 2>/dev/null) || echo '警告: mvn dependency:tree 执行失败'
    echo "--- OWASP dependency-check ---"
    if (cd "$PROJECT_DIR" && mvn org.owasp:dependency-check-maven:check -DfailBuildOnCVSS=7 -Dformat=JSON 2>/dev/null); then
      echo "OWASP dependency-check 完成"
    else
      echo '提示: 可安装 OWASP dependency-check-maven 插件获取更详细的漏洞报告'
    fi
  else
    echo '{"warning": "未找到 mvn，请安装 Maven"}'
  fi
elif [[ -f "$PROJECT_DIR/build.gradle" ]] || [[ -f "$PROJECT_DIR/build.gradle.kts" ]]; then
  echo "[Gradle 项目]"
  if command -v gradle &>/dev/null || [[ -f "$PROJECT_DIR/gradlew" ]]; then
    GRADLE_CMD="gradle"
    [[ -f "$PROJECT_DIR/gradlew" ]] && GRADLE_CMD="$PROJECT_DIR/gradlew"
    echo "--- dependencies ---"
    (cd "$PROJECT_DIR" && $GRADLE_CMD dependencies 2>/dev/null) || echo '警告: gradle dependencies 执行失败'
  else
    echo '{"warning": "未找到 gradle 或 gradlew"}'
  fi
else
  echo '{"warning": "未找到 pom.xml 或 build.gradle"}'
fi
