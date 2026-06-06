# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] - 2026-06-06

### Added
- **新协议层参考融合**：从 `claude-code-security-review` 项目借鉴 hard-exclusion 误报过滤理念，实现 `scripts/review_filter.py`（也可独立于审计流程使用）。
- **内置规则大幅扩展**：新增 JWT `alg=none` / hardcoded JWT secret、NoSQL 操作符注入、原型污染、路径遍历、XXE 解析入口、CORS wildcard、DEBUG/dev 模式、容器 privileged/root、Python 依赖未锁版本、Node 缺失 lockfile 等规则。
- **供应链基线检查**：自动识别项目语言栈；Node 项目缺失 lockfile 报 MAJOR；Python `requirements.txt` 未锁版本报 MINOR；无法识别语言栈报 INFO。
- **--mode / --fail-on 选项**：`semgrep_scan.js` 新增 `--mode=quick|standard|deep`（审计深度提示）和 `--fail-on`（可配置退出码触发阈值）。
- **审计参考文档融合**：从 `code-security-audit-skill` 原包合并 `references/vulnerability_rules.md`（五语言漏洞规则 + 业务逻辑 + 攻击链模式）、`references/report_template.md`、`references/examples/`（Juice Shop 审计示例 + 对比）。
- **依赖审计脚本**：`scripts/dep_audit.sh` 和 `scripts/dep_audit_java.sh`（依赖生态原生工具，自动跳过不可用工具）。
- **audit_skill --filter 参数**：当输出为 JSON 时自动调用 `review_filter.py` 生成 `.filtered.json`。
- **npm script：filter** 和 **npm script：dep-audit**。

### Changed
- `semgrep_scan.js` 退出码逻辑从"硬编码 BLOCKER/CRITICAL 阈值"改为 `--fail-on` 可配置。
- `semgrep_scan.js` 报告输出格式统一为 `{tool, engine, mode, scannedPath, generatedAt, total, severities, findings}`。
- `audit_skill.py` 委托扫描解析兼容新 JSON 格式（issues / findings）。
- `package.json` 更新描述、脚本和技能元信息。
- `SKILL.md` 全面重写，合并参考包的审计流程描述，新增误报过滤、审计模式建议、参考资料章节。
- `README.md` 同步更新（用户自行查看差异）。

### Security
- 所有 Python 脚本运行前使用 `.venv` 环境，确保隔离的 Python 依赖。
- 报告默认不输出命中源码原文，只包含文件路径、行号、规则和修复建议。

[1.1.0]: https://github.com/FelipeOFF/sonarqube-analyzer/compare/v1.0.0...v1.1.0