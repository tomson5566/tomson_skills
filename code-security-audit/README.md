# code-security-audit

面向 OpenClaw / Agent Skill / 普通代码仓库的代码安全审计技能。

它不是一个“万能安全平台”，而是一套可快速落地的工程安全基线工具：有 Semgrep 就用 Semgrep；没有 Semgrep 就自动回退到内置 builtin 规则；同时支持 SonarQube 查询和 OpenClaw / Agent Skill 包专项审计。

> 配套文章：`从代码到 AI 应用安全：code-security-audit 技能实战指南`。
> 本 README 侧重依赖安装、初始化环境准备和快速上手。

---

## 1. 能力概览

### 本地代码安全扫描

入口：

```bash
node scripts/semgrep_scan.js --path=/path/to/project --output=security-report.md
```

扫描引擎：

- `auto`：默认模式。优先使用本技能目录 `.venv/bin/semgrep`，其次使用 PATH 中的 `semgrep`，都没有时回退 builtin。
- `semgrep`：强制使用 Semgrep。适合需要更完整规则能力的场景。
- `builtin`：强制使用内置轻量规则。适合离线环境、最小依赖环境、快速基线检查。

builtin 当前覆盖：

- 私钥块。
- 疑似硬编码 key / token / password。
- MD5 / SHA1 弱哈希。
- shell 命令执行入口，如 `exec`、`execSync`、`os.system`、`subprocess.Popen`。
- 动态代码执行，如 `eval`、`Function`。
- 疑似 SQL 字符串拼接。
- 关闭 TLS / 证书校验。
- 典型 Prompt Injection / RAG 污染标记。

### Skill 包专项审计

入口：

```bash
python3 scripts/audit_skill.py /path/to/skill --engine=auto
```

用于检查 OpenClaw / Agent Skill 包：

- 是否存在 `SKILL.md`。
- `SKILL.md` frontmatter 是否规范。
- 是否存在危险命令。
- 是否存在疑似敏感信息。
- 是否包含 `node_modules`、`.venv` 等重型运行时目录。
- 可委托 `semgrep_scan.js` 继续做代码安全基线扫描。

### SonarQube 对接

入口：

```bash
node scripts/analyze.js --project=my-project --format=markdown
node scripts/quality-gate.js --project=my-project
node scripts/report.js --project=my-project --format=markdown
```

依赖：可访问的 SonarQube 服务，以及有效的 `SONAR_HOST_URL` / `SONAR_TOKEN`。

---

## 2. 环境依赖

### 必需依赖

| 依赖 | 版本建议 | 用途 | 检查命令 |
|---|---:|---|---|
| Node.js | `>=18` | 运行 `semgrep_scan.js`、SonarQube 相关脚本 | `node -v` |
| npm | 随 Node.js 安装 | 安装 JS 依赖 | `npm -v` |
| Python | `>=3.8` | 运行 `audit_skill.py`，可选安装 Semgrep | `python3 --version` |

### 可选依赖

| 依赖 | 何时需要 | 说明 |
|---|---|---|
| Semgrep | 需要更完整的多语言 SAST 规则时 | 不装也能用，`auto` 会回退 builtin |
| SonarQube | 团队已有 SonarQube 平台时 | 本技能只负责查询 issues / quality gate / report |
| Git | 克隆源码或接入 CI 时 | 非扫描硬依赖 |

---

## 3. 快速安装

### 方式一：OpenClaw 技能目录中直接使用

如果你已经在 OpenClaw 环境里看到本技能，进入技能目录：

```bash
cd ~/.openclaw/skills/code-security-audit
npm install
```

执行自检：

```bash
npm test
```

期望看到 smoke test 通过。测试会验证：

- 核心脚本语法正常。
- `quality-gate.js` / `report.js` 包装入口存在。
- builtin 引擎能发现私钥、弱哈希和 Prompt Injection 测试样本。
- 发现 BLOCKER / CRITICAL 时返回非零退出码。

### 方式二：从源码目录使用

```bash
git clone <your-repo-url>
cd code-security-audit
npm install
npm test
```

> 如果是通过 Skill 市场安装，请以实际安装目录为准。安装后同样建议先执行 `npm install && npm test`。

---

## 4. 可选：安装 Semgrep

`code-security-audit` 不强制要求 Semgrep。没有 Semgrep 时仍可用 builtin 引擎完成基础检查。

但如果你希望获得更完整的规则库和多语言分析能力，建议安装 Semgrep。

### 推荐安装到本技能私有虚拟环境

这样不会污染系统 Python 环境，也便于 OpenClaw 技能独立运行。

```bash
cd ~/.openclaw/skills/code-security-audit
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install semgrep
semgrep --version
```

退出虚拟环境：

```bash
deactivate
```

`semgrep_scan.js` 的查找顺序是：

1. 当前技能目录下的 `.venv/bin/semgrep`
2. 系统 PATH 中的 `semgrep`
3. 如果 `--engine=auto` 且二者都不存在，则回退 builtin

### 用户级安装

如果不想使用 `.venv`，也可以安装到用户环境：

```bash
python3 -m pip install --user semgrep
semgrep --version
```

确保 `semgrep` 在 PATH 中：

```bash
which semgrep
```

---

## 5. 初始化环境准备

### 5.1 检查基础环境

```bash
node -v
npm -v
python3 --version
```

### 5.2 安装 JS 依赖

```bash
cd ~/.openclaw/skills/code-security-audit
npm install
```

当前 JS 运行依赖主要是：

- `yargs`：解析 CLI 参数。

开发依赖包括：

- `jest`
- `eslint`

### 5.3 运行自检

```bash
npm test
```

### 5.4 验证 builtin 扫描可用

```bash
node scripts/semgrep_scan.js \
  --engine=builtin \
  --path=. \
  --severities=BLOCKER,CRITICAL,MAJOR \
  --exclude=node_modules,.venv \
  --output=/tmp/code-security-audit-selfcheck.md
```

说明：

- 如果发现 BLOCKER / CRITICAL，脚本退出码会是 `2`，这不一定代表脚本失败，而是代表扫描发现高危问题。
- 报告默认不输出命中源码原文，只输出路径、行号、规则、描述和修复建议，避免二次泄露密钥。

### 5.5 验证 Semgrep 自动识别

如果已经安装 Semgrep：

```bash
node scripts/semgrep_scan.js \
  --engine=auto \
  --path=. \
  --severities=BLOCKER,CRITICAL,MAJOR \
  --exclude=node_modules,.venv \
  --output=/tmp/code-security-audit-semgrep-auto.md
```

输出里 `引擎：semgrep` 说明正在使用 Semgrep；如果输出 `引擎：builtin`，说明未检测到 Semgrep 或 Semgrep 执行失败后已自动回退。

---

## 6. 5 分钟快速上手

### 场景一：扫描一个普通项目

```bash
cd ~/.openclaw/skills/code-security-audit
node scripts/semgrep_scan.js \
  --engine=auto \
  --path=/path/to/project \
  --severities=BLOCKER,CRITICAL,MAJOR \
  --exclude=node_modules,.git,.venv,dist,build \
  --output=security-report.md
```

看结果：

```bash
sed -n '1,160p' security-report.md
```

### 场景二：离线环境只用 builtin

```bash
node scripts/semgrep_scan.js \
  --engine=builtin \
  --path=/path/to/project \
  --severities=BLOCKER,CRITICAL,MAJOR \
  --exclude=node_modules,.git,.venv \
  --output=security-report.md
```

适合内网、服务器、没有 Semgrep 安装权限的环境。

### 场景三：发布前审计一个 Skill 包

```bash
python3 scripts/audit_skill.py /path/to/skill \
  --engine=builtin \
  --exclude=node_modules,.venv \
  --print-issues
```

只做 Skill 专项规则，不委托代码扫描：

```bash
python3 scripts/audit_skill.py /path/to/skill \
  --engine=none \
  --print-issues
```

严格模式：发现 MAJOR 也返回非零退出码。

```bash
python3 scripts/audit_skill.py /path/to/skill \
  --engine=builtin \
  --strict \
  --format=json \
  --output=audit-skill-report.json
```

### 场景四：接入 CI/CD

普通代码仓库：

```bash
node scripts/semgrep_scan.js \
  --engine=auto \
  --path=. \
  --severities=BLOCKER,CRITICAL \
  --exclude=node_modules,.git,.venv,dist,build \
  --output=security-report.json
```

Skill 仓库：

```bash
python3 scripts/audit_skill.py . \
  --engine=auto \
  --strict \
  --format=json \
  --output=audit-skill-report.json
```

退出码约定：

- `0`：未发现 BLOCKER / CRITICAL；如果启用 `--strict`，也未发现 MAJOR。
- `2`：发现阻断级风险，适合 CI/CD 阻断。
- `1`：执行失败，例如路径不存在、参数错误或强制 Semgrep 模式失败。

---

## 7. SonarQube 初始化

如果只做本地扫描，可以跳过本节。

### 7.1 准备环境变量

```bash
export SONAR_HOST_URL=http://127.0.0.1:9000
export SONAR_TOKEN=your-token
```

建议不要把 token 写入代码仓库。可以放在：

- CI/CD Secret。
- 本机 shell profile。
- 受权限保护的 `.env` 文件。

### 7.2 查询质量门

```bash
node scripts/quality-gate.js --project=my-project
```

### 7.3 查询 issues

```bash
node scripts/analyze.js --project=my-project --format=markdown
```

### 7.4 生成 Markdown 报告

```bash
node scripts/report.js --project=my-project --format=markdown
```

注意：本技能的 SonarQube 能力是“对接查询”，不是替代 SonarScanner。项目是否已经被 SonarQube 分析，取决于你的 SonarQube 服务、Scanner 配置和流水线。

---

## 8. 常用参数速查

### `semgrep_scan.js`

| 参数 | 默认值 | 说明 |
|---|---|---|
| `--path`, `-p` | 必填 | 要扫描的目录或文件 |
| `--engine` | `auto` | `auto` / `semgrep` / `builtin` |
| `--config`, `-c` | `auto` | Semgrep 规则配置 |
| `--severities`, `-s` | `BLOCKER,CRITICAL,MAJOR` | 风险等级，支持逗号分隔 |
| `--output`, `-o` | 空 | 输出 `.md` 或 `.json` 报告 |
| `--exclude` | 空 | 额外排除目录/路径片段，可多次传入或逗号分隔 |
| `--max-file-size-kb` | `1024` | builtin 单文件扫描大小上限 |
| `--auto-fix` | `false` | 仅 Semgrep 引擎下透传 `--autofix` |

### `audit_skill.py`

| 参数 | 默认值 | 说明 |
|---|---|---|
| `skill_path` | 必填 | 要审计的 Skill 目录 |
| `--engine` | `auto` | `auto` / `semgrep` / `builtin` / `none` |
| `--severities` | `BLOCKER,CRITICAL,MAJOR` | 委托扫描保留的风险等级 |
| `--exclude` | 空 | 额外排除路径片段，可重复传入或逗号分隔 |
| `--strict` | `false` | 发现 MAJOR 也返回非零退出码 |
| `--print-issues` | `false` | 在终端打印问题明细 |
| `--output` | 自动生成 | 指定报告路径 |
| `--format` | 根据输出后缀推断 | `markdown` / `json` |

---

## 9. 风险分级建议

- 🔴 `BLOCKER`：阻断级风险，例如私钥块、极危险命令。应立即处理。
- 🟠 `CRITICAL`：严重风险，例如硬编码敏感凭据、命令注入入口、关闭 TLS 校验。建议 CI 阻断。
- 🟡 `MAJOR`：重要风险，例如弱哈希、典型 Prompt Injection 标记。建议迭代内修复；严格场景可阻断。
- 🟢 `MINOR`：次要风险，作为优化项处理。
- 🔵 `INFO`：提示信息，例如 Skill 包中存在额外运行时目录。

---

## 10. 安全注意事项

1. **不要把扫描报告当成公开文档随意转发**  
   虽然本技能默认不输出命中源码原文，但报告仍包含路径、行号和风险描述。

2. **不要盲目使用 `--auto-fix`**  
   `--auto-fix` 只在 Semgrep 引擎下透传 `--autofix`。使用前请确保代码已提交 Git 或有备份。

3. **不要删除不理解的身份文件**  
   例如 `.openclaw/identity/device.json`。如果扫描报出私钥，应先确认用途、权限和暴露面。本地身份文件通常应保持目录 `700`、文件 `600`。

4. **builtin 是基线，不是完整 SAST**  
   它适合快速检查明显问题；深度语义分析、多语言高级规则、完整自动修复应使用 Semgrep 或 SonarQube 等工具。

5. **Token 通过环境变量或 Secret 管理**  
   `SONAR_TOKEN`、API Key、数据库密码不要写入仓库。

---

## 11. 项目结构

```text
├── scripts/
│   ├── semgrep_scan.js   # 本地扫描：Semgrep 优先，builtin 保底
│   ├── audit_skill.py    # OpenClaw / Agent Skill 包专项审计
│   ├── analyze.js        # SonarQube issues 查询入口
│   ├── quality-gate.js   # SonarQube quality gate 查询入口
│   ├── report.js         # SonarQube Markdown 报告入口
│   └── smoke_test.js     # 自检脚本
├── src/                  # SonarQube API / 报告相关实现
├── SKILL.md              # OpenClaw 技能说明
├── README.md             # 当前快速上手文档
├── package.json          # Node.js 依赖和 npm scripts
└── package-lock.json     # 锁定依赖版本
```

---

## 12. 常见问题

### 12.1 没有 Semgrep 能不能用？

可以。

直接使用 builtin：

```bash
node scripts/semgrep_scan.js \
  --engine=builtin \
  --path=/path/to/project \
  --output=security-report.md
```

或者使用默认 `auto`，当 Semgrep 不存在时自动回退 builtin。

### 12.2 扫描命令返回退出码 2 是不是执行失败？

不一定。

退出码 `2` 表示发现了 `BLOCKER` 或 `CRITICAL` 风险，适合 CI/CD 阻断。  
如果只是本地检查，请打开报告看具体问题。

### 12.3 为什么报告里没有命中的源码片段？

这是故意设计。

安全报告如果直接输出 API Key、私钥、Token 原文，就会变成第二份泄密文件。本技能默认只输出：

- 文件路径
- 行号
- 规则 ID
- 风险等级
- 问题描述
- 修复建议

### 12.4 `--auto-fix` 会自动修改代码吗？

只有在 Semgrep 引擎下才会透传 `--autofix`。builtin 引擎不会修改文件。

建议先提交 Git 或备份后再使用：

```bash
git status
node scripts/semgrep_scan.js --engine=semgrep --path=. --auto-fix
```

### 12.5 SonarQube 相关命令报错怎么办？

先确认环境变量：

```bash
echo "$SONAR_HOST_URL"
test -n "$SONAR_TOKEN" && echo "SONAR_TOKEN is set"
```

再确认项目 key 是否存在，以及 SonarQube 服务是否可访问。

---

## 13. 推荐落地路径

如果你刚开始做 AI 应用或 Agent Skill 安全，建议按这个顺序推进：

1. **本地开发阶段**：用 builtin 或 Semgrep 扫描明显风险。
2. **提交前检查**：重点拦截私钥、硬编码 token、危险命令、关闭 TLS 校验。
3. **Skill 发布前**：使用 `audit_skill.py` 做专项审计。
4. **CI/CD 阶段**：用退出码阻断 `BLOCKER / CRITICAL`。
5. **团队治理阶段**：接入 SonarQube，统一查看 issues 和 quality gate。
6. **更高安全要求**：叠加依赖漏洞扫描、密钥泄露扫描、运行时防护和 RAG 内容安全检测。

---

## 14. 一屏命令速查

```bash
# 进入技能目录
cd ~/.openclaw/skills/code-security-audit

# 安装依赖
npm install

# 自检
npm test

# builtin 离线扫描
node scripts/semgrep_scan.js \
  --engine=builtin \
  --path=/path/to/project \
  --severities=BLOCKER,CRITICAL,MAJOR \
  --exclude=node_modules,.git,.venv \
  --output=security-report.md

# auto 模式：优先 Semgrep，失败回退 builtin
node scripts/semgrep_scan.js \
  --engine=auto \
  --path=/path/to/project \
  --output=security-report.md

# Skill 包专项审计
python3 scripts/audit_skill.py /path/to/skill \
  --engine=builtin \
  --exclude=node_modules,.venv \
  --print-issues

# Skill 严格模式，适合 CI
python3 scripts/audit_skill.py . \
  --engine=auto \
  --strict \
  --format=json \
  --output=audit-skill-report.json

# SonarQube
export SONAR_HOST_URL=http://127.0.0.1:9000
export SONAR_TOKEN=your-token
node scripts/quality-gate.js --project=my-project
node scripts/analyze.js --project=my-project --format=markdown
node scripts/report.js --project=my-project --format=markdown
```

---

## 15. 参考

- `SKILL.md`：OpenClaw 技能完整说明。
- `scripts/semgrep_scan.js`：本地扫描入口。
- `scripts/audit_skill.py`：Skill 包专项审计入口。
- 文章：`从代码到 AI 应用安全：code-security-audit 技能实战指南`。
