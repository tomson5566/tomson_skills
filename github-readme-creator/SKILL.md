---
name: github-readme-creator
description: Create, improve, or regenerate professional GitHub README.md files for software projects. Use when the user asks to write, update, polish, review, or generate a README for a GitHub repository, local project directory, open-source project, CLI tool, library, framework, service, or documentation package.
---

# GitHub README Creator

Generate practical, project-specific GitHub README.md files. Avoid generic marketing language. Prefer inspecting the repository when a local path or GitHub URL is available.

## Workflow

1. Determine project source:
   - If the user provides a local path, inspect the project files.
   - If the user provides a GitHub URL, fetch or inspect repository metadata when possible.
   - If only a description is provided, ask only for the minimum missing details.

2. Collect or infer:
   - Project name
   - Repository owner/name
   - Project type
   - Primary language/runtime
   - Install method
   - Usage examples
   - Key features
   - License
   - Documentation links
   - Contribution policy

3. Scan for sensitive information before generating README (see `references/secret-scan.md`):
   - Run secret/credential pattern scan over the repository (excluding `.git/`, `node_modules/`, `dist/`, `build/`, `.venv/`, `vendor/` and similar).
   - Detect at minimum: GitHub PAT/fine-grained tokens (`ghp_`, `gho_`, `ghu_`, `ghs_`, `ghr_`, `github_pat_`), generic API keys, AWS keys (`AKIA`, `ASIA`), Google API keys (`AIza`), OpenAI keys (`sk-`), Slack/Discord/Telegram tokens, SSH/PGP private key blocks, `.env`/`.npmrc`/`.pypirc`/`credentials`/`id_rsa` style files, hardcoded passwords/JWTs, and personal info (phone numbers, ID numbers, private emails).
   - Surface findings to the user with file path + line number + redacted snippet. Do not echo the full secret in chat.
   - Recommend remediation before publishing: move to env vars / secret manager, add to `.gitignore`, rotate any leaked credential, and if already committed, rewrite git history with `git filter-repo` / BFG.
   - Verify `.gitignore` covers `.env*`, `*.key`, `*.pem`, `id_rsa*`, `credentials*`, `secrets.*`. Suggest adding missing entries.
   - Require explicit user confirmation to continue when high-severity secrets are found.

4. Generate README sections based on project reality:
   - Title and short description
   - Badges, only if accurate
   - Project overview
   - Features
   - Requirements
   - Installation
   - Usage
   - Configuration, if applicable (use placeholders like `YOUR_API_KEY`, never real values)
   - Project structure, if useful
   - Documentation links
   - Contributing
   - Issue reporting
   - License

5. Verify:
   - No unresolved placeholders
   - Commands match actual package manager
   - Links point to the correct repository
   - License matches the actual LICENSE file when available
   - Project structure matches the real files
   - Markdown syntax is valid
   - No real secrets, tokens, API keys, passwords, or personal info appear in the README itself
   - Example commands use placeholder credentials (`export GITHUB_TOKEN=...`, `YOUR_API_KEY`), not live values

## Repository Inspection Hints

For local projects, inspect common files:

```bash
ls -la
find . -maxdepth 2 -type f | sort
git remote -v
```

Check ecosystem files:

```bash
cat package.json 2>/dev/null
cat pyproject.toml 2>/dev/null
cat setup.py 2>/dev/null
cat go.mod 2>/dev/null
cat Cargo.toml 2>/dev/null
cat pom.xml 2>/dev/null
cat build.gradle 2>/dev/null
cat LICENSE 2>/dev/null
```

## Template Reference

For a reusable README skeleton, read `references/readme-template.md` only when you need a structured starting point. Adapt it to the actual project; do not copy generic wording blindly.

## Output Rules

- Do not leave `[placeholder]` text.
- Do not invent unsupported features.
- Prefer concise, useful README content over inflated wording.
- If writing to a file, preserve important existing custom content unless the user asks for a full rewrite.
- If project details are insufficient, ask only the one or two questions needed to continue.
