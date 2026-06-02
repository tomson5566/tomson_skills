# Secret Scan Reference

When the `github-readme-creator` skill runs, it performs a sensitive-information scan on the project directory **before** generating the README. This page documents what to scan, how to scan, and how to report findings.

## Scan Scope

### Directories to EXCLUDE

`.git/`, `node_modules/`, `dist/`, `build/`, `.venv/`, `venv/`, `__pycache__/`, `vendor/`, `vendor/bundle/`, `.tox/`, `.mypy_cache/`, `.pytest_cache/`, `target/`, `.gradle/`, `.idea/`, `.vscode/`, `*.egg-info/`, `.next/`, `.nuxt/`, `coverage/`, `.cache/`, `public/` (static assets), `minimax-output/`, binary/image directories.

Binary files (images, compiled objects, etc.) are skipped by content scanning.

### File types to scan

All text-based files: `*.py`, `*.js`, `*.ts`, `*.jsx`, `*.tsx`, `*.go`, `*.rs`, `*.java`, `*.rb`, `*.php`, `*.c`, `*.cpp`, `*.h`, `*.sh`, `*.bash`, `*.zsh`, `*.yaml`, `*.yml`, `*.json`, `*.toml`, `*.ini`, `*.cfg`, `*.conf`, `*.env*`, `*.properties`, `*.xml`, `*.html`, `*.md`, `*.txt`, `*.sql`, `Dockerfile*`, `Makefile*`, `docker-compose*`, `Jenkinsfile*`, `Vagrantfile`, `.npmrc`, `.pypirc`, `.netrc`, `Gemfile`, `Rakefile`.

## Patterns to Detect

### 🔴 High Severity — Must warn, require confirmation before continue

| Category | Pattern | Example (redacted) |
|---|---|---|
| GitHub PAT (classic) | `ghp_[0-9a-zA-Z]{36}` | `ghp_****************************` |
| GitHub PAT (fine-grained) | `github_pat_[0-9a-zA-Z_]{82}` | `github_pat_**************************************` |
| GitHub OAuth | `gho_[0-9a-zA-Z]{36}` | `gho_****************************` |
| GitHub User-to-Server | `ghu_[0-9a-zA-Z]{36}` | `ghu_****************************` |
| GitHub Server-to-Server | `ghs_[0-9a-zA-Z]{36}` | `ghs_****************************` |
| GitHub Refresh | `ghr_[0-9a-zA-Z]{36}` | `ghr_****************************` |
| AWS Access Key | `AKIA[0-9A-Z]{16}` | `AKIA****************` |
| AWS Secret Key | `(?:AWS_SECRET_ACCESS_KEY|aws_secret)\s*[:=]\s*['"]?[A-Za-z0-9/+=]{40}` | — |
| AWS Session Token | `ASIA[0-9A-Z]{16}` | `ASIA****************` |
| Google API Key | `AIza[0-9A-Za-z_-]{35}` | `AIza***************************` |
| Google OAuth | `[0-9]+-[a-z0-9_]{32}\.apps\.googleusercontent\.com` | — |
| OpenAI / Anthropic Key | `sk-[a-zA-Z0-9]{20,}` | `sk-********************` |
| Slack Token | `xox[baprs]-[0-9a-zA-Z-]{10,}` | `xoxb-******************` |
| Discord Bot Token | `[MN][A-Za-z\d]{23,}\.[\w-]{6}\.[\w-]{27}` | — |
| Telegram Bot Token | `[0-9]{8,10}:[A-Za-z0-9_-]{35}` | — |
| Stripe Key | `[sr]k_live_[0-9a-zA-Z]{24}` | — |
| Private SSH Key | `-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----` | — |
| PGP Private Key Block | `-----BEGIN PGP PRIVATE KEY BLOCK-----` | — |
| JWT / Bearer Token | `(?:eyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}|Bearer\s+[A-Za-z0-9\-._~+/]+=*)` | — |
| Hardcoded Password | `(?:password|passwd|pwd)\s*[:=]\s*['"][^'"]{4,}['"]` | — |
| Database URL with creds | `(?:mysql|postgres|mongodb|redis)://[^\s'"]*:[^\s'"]*@[^\s'"]+` | — |

### 🟡 Medium Severity — Warn, recommend remediation

| Category | Pattern | Notes |
|---|---|---|
| Generic API key variable | `(?:API_KEY|APIKEY|SECRET|TOKEN|PRIVATE_KEY)\s*[:=]\s*['"][A-Za-z0-9_\-]{16,}['"]` | May be placeholder; verify context |
| `.env` file with values | `\.env(?:\.\w+)?` containing `KEY=VALUE` pairs where VALUE is non-empty and not placeholder | Check if `.env.example` exists alongside |
| `.npmrc` with auth | `_auth=\s*[A-Za-z0-9+/=]{20,}` or `//registry\.npmjs\.org/:_authToken=` | — |
| `.pypirc` with password | `password\s*[:=]\s*\S+` | — |
| `.netrc` with password | `password\s+\S+` | — |
| Personal email (non-noreply) | `[a-zA-Z0-9._%+-]+@(?!gmail\.com|outlook\.com|yahoo\.com|hotmail\.com|noreply\.github\.com|users\.noreply\.github\.com)[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}` | May be corporate/personal email |
| Phone number (CN) | `1[3-9]\d{9}` (in non-test context) | — |
| ID number (CN) | `[1-9]\d{5}(?:19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])\d{3}[\dXx]` | — |
| Internal IP / hostname | `(?:192\.168\.|10\.\d+\.\d+\.|172\.(?:1[6-9]|2\d|3[01])\.)\d+` in config/deploy files | May expose internal topology |

### 🔵 Low Severity — Suggest `.gitignore` additions

| Category | What to check |
|---|---|
| Missing `.gitignore` | Project has no `.gitignore` at all |
| `.env` not in `.gitignore` | `.env` files exist but are not ignored |
| `*.key`, `*.pem` not ignored | Key/cert files not ignored |
| `id_rsa*`, `*.ppk` not ignored | SSH key files not ignored |
| `credentials*`, `secrets.*` not ignored | Credential files not ignored |
| `node_modules/`, `.venv/` not ignored | Dependency dirs not ignored |

## Scan Implementation

Use `grep -rn` or `ripgrep (rg)` for pattern matching. Example:

```bash
# Scan for GitHub tokens
rg -n 'ghp_[0-9a-zA-Z]{36}|github_pat_[0-9a-zA-Z_]{82}|gho_[0-9a-zA-Z]{36}|ghu_[0-9a-zA-Z]{36}|ghs_[0-9a-zA-Z]{36}|ghr_[0-9a-zA-Z]{36}' --glob '!.git' --glob '!node_modules' --glob '!dist' --glob '!build' --glob '!.venv' --glob '!vendor' .

# Scan for AWS keys
rg -n 'AKIA[0-9A-Z]{16}|ASIA[0-9A-Z]{16}' --glob '!.git' .

# Scan for private keys
rg -n '-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----' --glob '!.git' .

# Scan for hardcoded passwords
rg -in '(?:password|passwd|pwd)\s*[:=]\s*['\''"][^'\''"]{4,}['\''"]' --glob '!.git' --glob '!node_modules' --type-add 'config:*.env*' --type config --type py --type js --type ts .

# Check .gitignore coverage
cat .gitignore 2>/dev/null | grep -E '\.env|\.key|\.pem|id_rsa|credentials|secrets' || echo "MISSING .gitignore entries"
```

## Reporting Format

When findings exist, present results like:

```
⚠️ 敏感信息扫描结果 / Secret Scan Results

🔴 高危 (High) — 发现 N 处
  • path/to/file:42 — GitHub PAT (ghp_...) [redacted: ghp_****...****]
  • path/to/.env:5 — Hardcoded database URL with credentials

🟡 中危 (Medium) — 发现 N 处
  • path/to/config.py:10 — API_KEY variable with non-placeholder value
  • .env exists but no .env.example counterpart

🔵 低危 (Low) — 发现 N 处
  • .gitignore 缺少 .env*, *.key, *.pem, id_rsa* 条目

📋 修复建议 / Remediation:
  1. 将敏感值移至环境变量或密钥管理器（如 GitHub Secrets、Vault）
  2. 将 .env、*.key 等加入 .gitignore
  3. 如已提交，使用 git filter-repo 或 BFG 清除历史记录
  4. 轮换已泄露的密钥（GitHub PAT 可在 Settings → Developer settings → Personal access tokens 撤销）

❓ 是否继续生成 README？（高危发现需明确确认）
```

## README Output Guard

After generating the README, perform a final check:

- The README itself must NOT contain any real secrets, tokens, API keys, or passwords.
- Configuration examples must use placeholders: `YOUR_API_KEY`, `your-github-token`, `REPLACE_WITH_SECRET`, etc.
- Environment variable examples: `export GITHUB_TOKEN=your_token_here` (not a real token).
- If a real value somehow ends up in the README, strip it and replace with a placeholder immediately.
