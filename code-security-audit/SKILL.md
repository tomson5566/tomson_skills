---
name: code-security-audit
description: Audit code, configuration, documents, and OpenClaw/Agent Skill packages for security risks. Supports Semgrep, builtin offline rules, SonarQube integration, and dedicated audit_skill checks for Skill structure, dangerous commands, and secret exposure.
---

# code-security-audit：代码安全审计技能

## 定位

本技能用于在 OpenClaw 环境中执行代码/配置/文档的安全审计。当前包含两条能力链：

1. **本地扫描**：`scripts/semgrep_scan.js`
   - 优先使用系统中的 `semgrep` 命令。
   - 如果没有安装 Semgrep，会自动回退到内置轻量规则引擎，保证离线/无外网环境也能用。
2. **SonarQube 对接**：`scripts/analyze.js`、`scripts/quality-gate.js`、`scripts/report.js`
   - 通过 `SONAR_HOST_URL` 和 `SONAR_TOKEN` 查询 SonarQube issues、质量门和分析报告。

> 安全原则：报告默认只输出文件路径、行号、规则和修复建议，不输出命中源码内容，避免二次泄露密钥。

## 快速使用

### 本地安全扫描

```bash
node scripts/semgrep_scan.js --path=/path/to/project --output=security-report.md
```

强制使用内置引擎：

```bash
node scripts/semgrep_scan.js \
  --engine=builtin \
  --path=/path/to/project \
  --severities=BLOCKER,CRITICAL,MAJOR \
  --output=security-report.md
```

常用参数：

- `--engine=auto|semgrep|builtin`：默认 `auto`，有 Semgrep 就用 Semgrep，否则用 builtin。
- `--path`：扫描路径。
- `--config`：Semgrep 配置，默认 `auto`。
- `--severities`：风险等级，支持 `BLOCKER,CRITICAL,MAJOR,MINOR,INFO`。
- `--output`：输出 `.md` 或 `.json` 报告。
- `--exclude`：额外排除目录/路径片段。
- `--max-file-size-kb`：内置引擎单文件扫描大小上限，默认 1024KB。
- `--auto-fix`：仅 Semgrep 引擎下透传 `--autofix`；builtin 不会改文件。

Semgrep 解析顺序：优先使用本技能目录下的 `.venv/bin/semgrep`，其次使用 PATH 中的 `semgrep`；`--engine=auto` 在二者都不可用时回退 builtin。


### Skill 包专项审计

用于检查 OpenClaw/Agent Skill 目录是否存在结构问题、危险命令、硬编码敏感信息，并可委托 `semgrep_scan.js` 做代码安全基线扫描。

```bash
python3 scripts/audit_skill.py /path/to/skill --engine=auto
```

也可以通过 npm script 调用：

```bash
npm run audit-skill -- /path/to/skill --engine=builtin --exclude=node_modules,.venv
```

常用参数：

- `--engine=auto|semgrep|builtin|none`：委托扫描引擎；`none` 表示只做 Skill 专项规则。
- `--severities=BLOCKER,CRITICAL,MAJOR,MINOR,INFO`：保留风险等级。
- `--exclude`：额外排除路径片段，可重复传入或逗号分隔。
- `--strict`：发现 MAJOR 也返回非零退出码，适合更严格 CI。
- `--print-issues`：终端打印问题明细；默认只打印汇总和报告路径。
- `--output=report.md|report.json`：指定报告路径；默认写入 `~/workspaces/ai_agent_self_upgrade/code-security-audit/`。

退出码：

- `0`：未发现 BLOCKER/CRITICAL；如果启用 `--strict`，也未发现 MAJOR。
- `2`：发现阻断级风险，适合 CI/CD 阻断。
- `1`：执行失败，如路径不存在或参数错误。

审计报告不输出命中源码原文，只包含文件、行号、规则、描述和修复建议，避免二次泄露密钥。

### SonarQube 对接

```bash
export SONAR_HOST_URL=http://127.0.0.1:9000
export SONAR_TOKEN=your-token

node scripts/analyze.js --project=my-project --format=markdown
node scripts/quality-gate.js --project=my-project
node scripts/report.js --project=my-project --format=markdown
```

## 内置规则覆盖范围

当 Semgrep 不可用时，builtin 引擎会检查：

- 私钥块：`-----BEGIN PRIVATE KEY-----`
- 疑似硬编码密钥/密码/token
- 弱哈希：MD5/SHA1
- shell 命令执行入口：`exec`、`execSync`、`os.system`、`subprocess.Popen` 等
- 动态代码执行：`eval`、`Function`
- 疑似 SQL 字符串拼接
- 关闭 TLS/证书校验
- 典型 Prompt Injection / RAG 污染标记

限制：builtin 是轻量规则引擎，适合快速基线扫描；深度语义分析、多语言高级规则、真实 autofix 仍应安装 Semgrep 或接入 SonarQube。

## 测试

```bash
npm test
```

当前 smoke test 会验证：

- 核心脚本语法正确。
- 包装入口 `quality-gate.js`、`report.js` 存在。
- 内置引擎能发现私钥、弱哈希和 Prompt Injection 测试样本。
- 发现 BLOCKER/CRITICAL 时返回非零退出码，适合 CI 阻断。

## 退出码

- `0`：未发现 BLOCKER/CRITICAL。
- `2`：发现 BLOCKER 或 CRITICAL，适合 CI/CD 阻断。
- `1`：执行失败，如路径不存在、Semgrep 强制模式失败等。

## 注意事项

- 不要直接删除 OpenClaw 的身份文件，例如 `.openclaw/identity/device.json`。如果扫描报出私钥，应先检查文件权限和用途；本地身份文件通常应保持 `600`，目录保持 `700`。
- `--auto-fix` 可能修改代码，只建议在已提交 Git 或有备份时使用。
- SonarQube 功能依赖可访问的 SonarQube 服务和有效 token。
