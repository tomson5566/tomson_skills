---
name: code-security-audit
description: Audit code, configuration, documents, and OpenClaw/Agent Skill packages for security risks. Supports Semgrep, builtin offline rules, dependency audit helpers, false-positive filtering, SonarQube integration, and dedicated audit_skill checks for Skill structure, dangerous commands, and secret exposure.
---

# code-security-audit：代码安全审计技能

## 定位

本技能用于在 OpenClaw / Agent 环境中执行代码、配置、文档与 Skill 包安全审计。升级后包含四条能力链：

1. **本地扫描**：`scripts/semgrep_scan.js`
   - 优先使用本技能私有 `.venv/bin/semgrep`。
   - 其次使用 PATH 中的 `semgrep`。
   - 如果没有 Semgrep，自动回退到 builtin 离线规则。
2. **依赖审计辅助**：`scripts/dep_audit.sh`、`scripts/dep_audit_java.sh`
   - 支持 Python / Node.js / Go / Java 项目的依赖工具扫描。
3. **误报过滤**：`scripts/review_filter.py`
   - 借鉴 PR Security Review 的 hard exclusion 思路，对 DoS、rate-limit、resource leak、open redirect、memory-safety 等低信噪比类别做可配置过滤。
4. **Skill 专项审计 + SonarQube 对接**
   - `scripts/audit_skill.py`：检查 Skill 结构、危险命令、敏感信息、重型运行时目录，并可委托本地扫描。
   - `scripts/analyze.js`、`scripts/quality-gate.js`、`scripts/report.js`：查询 SonarQube issues、质量门和报告。

> 安全原则：报告默认只输出文件路径、行号、规则和修复建议，不输出命中源码内容，避免二次泄露密钥。

## 审计模式建议

- **Quick / 轻度**：快速发现阻断级风险，适合提交前本地自检。
- **Standard / 中度**：默认推荐，覆盖 secrets、注入、认证、配置、AI Prompt Injection、供应链基线。
- **Deep / 深度**：结合 `references/vulnerability_rules.md`、依赖审计脚本、Semgrep/SonarQube 和人工数据流追踪执行。

核心审计哲学：**不可信 Source → 传播链路 Propagation → 危险 Sink**。确认漏洞前必须验证可达性、过滤/授权是否可绕过、前置条件和影响范围。

## 快速使用

### 本地安全扫描

```bash
node scripts/semgrep_scan.js --path=/path/to/project --output=security-report.md
```

强制使用 builtin 离线引擎：

```bash
node scripts/semgrep_scan.js \
  --engine=builtin \
  --path=/path/to/project \
  --mode=standard \
  --severities=BLOCKER,CRITICAL,MAJOR \
  --output=security-report.md
```

常用参数：

- `--engine=auto|semgrep|builtin`：默认 `auto`，有 Semgrep 就用 Semgrep，否则用 builtin。
- `--path`：扫描路径。
- `--mode=quick|standard|deep`：审计深度提示；当前主要写入报告元信息，供流程和后续工具识别。
- `--config`：Semgrep 配置，默认 `auto`。
- `--severities`：风险等级，支持 `BLOCKER,CRITICAL,MAJOR,MINOR,INFO`。
- `--fail-on=BLOCKER|CRITICAL|MAJOR|MINOR|INFO`：达到该等级及以上时返回退出码 `2`，默认 `CRITICAL`。
- `--output`：输出 `.md` 或 `.json` 报告。
- `--exclude`：额外排除目录/路径片段。
- `--max-file-size-kb`：内置引擎单文件扫描大小上限，默认 1024KB。
- `--auto-fix`：仅 Semgrep 引擎下透传 `--autofix`；builtin 不会改文件。

### 误报过滤

对 JSON 报告做 deterministic hard-exclusion 过滤：

```bash
python3 scripts/review_filter.py security-report.json \
  --output security-report.filtered.json
```

可配置类别：

```bash
python3 scripts/review_filter.py security-report.json \
  --exclude-classes=dos,rate-limit,resource-leak,open-redirect,memory-safety \
  --keep-classes=open-redirect \
  --output security-report.filtered.json
```

说明：过滤只基于规则 ID / 描述 / 修复建议等元数据，不读取或输出源码片段。

### Skill 包专项审计

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
- `--filter`：当输出为 JSON 时，调用 `review_filter.py` 生成 `.filtered.json`。
- `--filter-classes` / `--filter-keep-classes`：传递给 `review_filter.py` 的类别控制参数。
- `--print-issues`：终端打印问题明细；默认只打印汇总和报告路径。
- `--output=report.md|report.json`：指定报告路径；默认写入 `~/workspaces/ai_agent_self_upgrade/code-security-audit/`。

### 依赖审计辅助

```bash
scripts/dep_audit.sh /path/to/project auto
scripts/dep_audit_java.sh /path/to/project
```

这些脚本优先调用生态原生工具，例如 `npm audit`、`pip-audit`、`govulncheck`、Maven/Gradle OWASP Dependency Check（取决于本机安装情况）；工具不存在时会跳过而不是破坏环境。

### SonarQube 对接

```bash
export SONAR_HOST_URL=http://127.0.0.1:9000
export SONAR_TOKEN=your-token

node scripts/analyze.js --project=my-project --format=markdown
node scripts/quality-gate.js --project=my-project
node scripts/report.js --project=my-project --format=markdown
```

## 内置规则覆盖范围

builtin 引擎适合离线快速基线扫描，当前覆盖：

- 私钥块：`-----BEGIN PRIVATE KEY-----`
- 疑似硬编码密钥 / 密码 / token / JWT secret / Session secret
- 弱哈希：MD5 / SHA1
- shell 命令执行入口：`exec`、`execSync`、`os.system`、`subprocess.Popen` 等
- 动态代码执行：`eval`、`Function`
- 疑似 SQL 字符串拼接
- NoSQL 操作符注入：Mongo 查询直接接收 `req.body/query/params`、`$where`
- 原型污染：不安全 merge / `Object.assign` 处理用户输入
- 路径遍历：文件 API 接收用户可控路径
- XXE：XML 解析入口提示
- JWT `alg=none` / none algorithms
- CORS wildcard、DEBUG/dev 模式、关闭 TLS/证书校验
- 容器 privileged / root 运行基线
- 典型 Prompt Injection / RAG 污染标记
- 供应链基线：Node 项目缺少 lockfile、Python requirements 未固定版本

限制：builtin 是轻量正则规则引擎，不替代 Semgrep、SonarQube、SCA 工具和人工数据流审计。深度语义分析、多语言高级规则、真实 autofix 仍应安装 Semgrep 或接入 SonarQube。

## 参考资料

本技能内置了从参考包归纳融合的审计知识：

- `references/vulnerability_rules.md`：Python / Node.js / Go / Java 漏洞规则、业务逻辑检查、攻击链模式、数据流追踪指南。
- `references/report_template.md`：完整审计报告模板。
- `references/examples/`：Juice Shop 审计示例与对比。

深度审计时优先读取这些参考文件，再结合项目实际攻击面动态拆分审计方向。

## 测试

```bash
npm test
.venv/bin/python -m py_compile scripts/audit_skill.py scripts/review_filter.py
```

当前 smoke test 会验证：

- 核心脚本语法正确。
- 包装入口 `quality-gate.js`、`report.js` 存在。
- builtin 引擎能发现私钥、弱哈希和 Prompt Injection 测试样本。
- 发现 BLOCKER/CRITICAL 时返回非零退出码，适合 CI 阻断。

## 退出码

- `0`：未发现达到 `--fail-on` 阈值的问题。
- `2`：发现达到 `--fail-on` 阈值的问题，适合 CI/CD 阻断。
- `1`：执行失败，如路径不存在、Semgrep 强制模式失败等。

## 注意事项

- 运行本技能的 Python 工具时优先使用本目录 `.venv`：例如 `.venv/bin/python scripts/review_filter.py ...`。
- 不要直接删除 OpenClaw 的身份文件，例如 `.openclaw/identity/device.json`。如果扫描报出私钥，应先检查文件权限和用途；本地身份文件通常应保持 `600`，目录保持 `700`。
- `--auto-fix` 可能修改代码，只建议在已提交 Git 或有备份时使用。
- SonarQube 功能依赖可访问的 SonarQube 服务和有效 token。
