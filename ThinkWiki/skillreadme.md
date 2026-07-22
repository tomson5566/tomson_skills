# ThinkWiki Skill — 使用与运维手册

> 这份文档是给人看的手册，不会被 Agent Skills 宿主自动加载。
> 宿主入口仍是 [`SKILL.md`](./SKILL.md)，放在 SKILL.md 同目录仅是方便分发时一起打包。

本机实际部署版本：**ThinkWiki 1.7.3**，已与本仓库 `ThinkWiki-1.7.3/` 同源安装到
`/home/tangzhiang/.copaw/workspaces/fqd_pro/skills/ThinkWiki/`。

---

## 1. 这是什么 / 何时用

ThinkWiki 是一个**本地 Markdown 知识库**技能：把零散的文档、网页、笔记、对话沉淀为可查询、可视化的本地 wiki，并提供 inbox / viewer / 知识图谱 / 健康治理等构件。

**适合**：
- 长期积累一个项目 / 主题 / 客户的笔记库
- 抓网页、PDF、DOCX、XLSX、PPTX、纯文本入库
- 基于已有 wiki 回答问题，并支持把"高价值问答"沉淀成 `query / synthesis / decision / concept` 页面
- 在浏览器里看 viewer 与图谱（graph）

**不适合**：
- 一次性 PDF 转 Word 之类的瞬时转化（请用 `pdf`/`docx`/`xlsx`/`pptx` 技能）
- 不需要知识沉淀的闲聊
- 没有写入权限的临时工作目录

---

## 2. 环境要求

| 项 | 本机现状 |
|---|---|
| Python ≥ 3.x（自带 venv） | ✅ Rocky 10.2 自带 python3.13 |
| `.venv` 引导（依赖） | ✅ 由 `bootstrap` 自动创建 |
| Ollama 服务 + 模型 | ✅ 用户态运行，监听 `127.0.0.1:11434` |
| Embedding 模型 `bge-m3:latest` | ✅ 已下载 |
| 磁盘 + 内存 | 本机 15G 内存、215G 剩余磁盘，足够 |

---

## 3. 快速上手（4 步）

> 所有命令在 **ThinkWiki 技能根目录**下执行（下面用 `TW=` 简化）。

```bash
TW=/home/tangzhiang/.copaw/workspaces/fqd_pro/skills/ThinkWiki
cd "$TW"
source ./.env                  # 加载嵌入服务配置；见 §5
```

### 3.1 健康检查
```bash
python3 scripts/thinkwiki doctor --repo-root .
```
预期输出末尾：`All checks passed`。  
`doctor` 不会单独展示 Embedding 状态——只要 `.env` 加载成功且 Ollama 在 `11434` 监听，链路就是通的。

### 3.2 初始化一个 wiki
```bash
python3 scripts/thinkwiki init "$HOME/wikis/my-notes" --name "My Notes"
```
会把 `$HOME/wikis/my-notes/` 初始化为新 wiki 根目录；初次调用嵌入服务做实体去重，需要 Ollama 在跑。

### 3.3 收集 / 导入内容

**网页 → inbox 先收：**
```bash
python3 scripts/thinkwiki clip "$HOME/wikis/my-notes" \
  --url https://example.com/article \
  --title "示例文章"
```

**本地文件 → inbox：**
```bash
# MD/PDF/DOCX/XLSX/XLS/PPTX/纯文本都吃
python3 scripts/thinkwiki ingest "$HOME/wikis/my-notes" --file /path/to/file.pdf
```

**浏览 inbox 后批量入 wiki：**
```bash
python3 scripts/thinkwiki inbox view "$HOME/wikis/my-notes"
python3 scripts/thinkwiki inbox approve "$HOME/wikis/my-notes" --ids 1,3,7
python3 scripts/thinkwiki batch-ingest "$HOME/wikis/my-notes"
```

### 3.4 提问与产出

```bash
# 问答
python3 scripts/thinkwiki ask "$HOME/wikis/my-notes" "项目 A 的里程碑是什么？"

# 把问答结果沉淀成一篇页
python3 scripts/thinkwiki crystallize "$HOME/wikis/my-notes" \
  --kind synthesis --title "A 项目里程碑梳理"

# 浏览器视图：serve + 在浏览器打开 http://127.0.0.1:28765/
python3 scripts/thinkwiki serve "$HOME/wikis/my-notes" --open

# 生成知识图谱
python3 scripts/thinkwiki graph "$HOME/wikis/my-notes"
```

---

## 4. 嵌入模型策略（中英混合为主，英文可临时切）

ThinkWiki 默认接 **本地 Ollama 上的 `bge-m3`**（1024 维，覆盖中英混合语义）。  
纯英文临时切到 **`nomic-embed-text` 的步骤**：

```bash
# 1) 拉模型（一次性，约 274 MB）
ollama pull nomic-embed-text

# 2) 改 .env 第三行
# THINKWIKI_EMBED_MODEL=nomic-embed-text

# 3) 重载环境变量后跑 ThinkWiki 即可生效，无需重启 Ollama
```

反之亦然。两份模型共存，`~/.local/share/ollama/models/blobs/` 里各自按 sha256 缓存。

---

## 5. 本机 `.env` 内容

`/home/tangzhiang/.copaw/workspaces/fqd_pro/skills/ThinkWiki/.env`：

```env
# Embedding（本地 Ollama）
THINKWIKI_EMBED_API_KEY=ollama                # 占位；Ollama 本机不鉴权，非空即启用
THINKWIKI_EMBED_BASE_URL=http://127.0.0.1:11434/v1/embeddings
THINKWIKI_EMBED_MODEL=bge-m3
```

> **为什么 API key 是 "ollama"？** ThinkWiki 的 `ai_config.py` 要求 `THINKWIKI_EMBED_API_KEY` 非空；
> Ollama 本机不校验 key，任意非空字符串都可。这是为了让"通过环境变量开关功能"的语义保持一致。
>
> **LLM（`crystallize` / `digest` 等内容生成）**：本机暂未配置；功能会按 SKILL.md 描述优雅降级。
> 需要时按以下任一来源补齐 `.env`：
>
> ```env
> THINKWIKI_LLM_API_KEY=...
> THINKWIKI_LLM_BASE_URL=https://api.openai.com/v1/chat/completions
> THINKWIKI_LLM_MODEL=gpt-4o-mini
> ```

---

## 6. Ollama 服务与开机自启

Ollama 现在是**用户态**跑的（`~/.local/bin/ollama`，`PID` 跟随登录会话）。  
固化到 systemd 的脚本在：

```
/home/tangzhiang/.copaw/workspaces/fqd_pro/scripts/install_ollama_systemd.sh
```

启用方法（**需要 sudo**）：

```bash
bash /home/tangzhiang/.copaw/workspaces/fqd_pro/scripts/install_ollama_systemd.sh
```

脚本会：

1. 停掉当前用户态 `ollama serve`
2. 把 `~/.local/lib/ollama/bin/ollama` 拷到 `/usr/local/bin/`
3. 写 `/etc/systemd/system/ollama.service`：
   - `User=tang_zhiang`（**不新建系统用户**，复用现有家目录，模型路径不挪动）
   - `Environment="OLLAMA_HOST=127.0.0.1:11434"`（**只听本机回环**，不开外网）
   - `Environment="OLLAMA_MODELS=/home/tang_zhiang/.local/share/ollama/models"`
4. `systemctl enable --now ollama`
5. 自查：`/api/version`、`ollama list`

服务检查 / 启停 / 日志：

```bash
systemctl status ollama
systemctl restart ollama
journalctl -u ollama -f
```

模型目录（按 sha256 缓存）：

```
~/.local/share/ollama/models/
├── blobs/        # 实际权重；bge-m3 当前占 1.1 GB
└── manifests/    # 模型清单
```

卸载某个模型：

```bash
ollama rm bge-m3
```

---

## 7. 常见坑（FAQ）

| 症状 | 原因 / 修法 |
|---|---|
| `Embedding is not configured. Set THINKWIKI_EMBED_API_KEY...` | `.env` 没 source。前面补一句 `. ./.env` |
| `Embedding auth failed (HTTP 401/403): check THINKWIKI_EMBED_API_KEY` | Ollama 上游 401。检查 `127.0.0.1:11434` 是否真在：`ss -tln \| grep 11434` |
| `ConnectError [Errno 111] Connection refused` / `urllib... timed out` | Ollama 没在跑。`pgrep ollama`；没就 `ollama serve &` 或 `systemctl start ollama` |
| `doctor` 只看到 `Core runtime: ready` 没列 Embedding | 是设计如此。Embedding 状态以实际 `embed_texts()` 调用为准（见下一条） |
| 想确认嵌入链路 | `cd $TW && . ./.env && PYTHONPATH=./scripts ./.venv/bin/python3 -c "from embed_client import embed_texts; print(len(embed_texts(['hi','bge-m3 test'])))"`，期望返回 `2` |
| 端口 28765 占用 | `thinkwiki serve` 的本地端口。换机器或停占用进程 |
| 模型下不动 | 出口防火墙在挡 `registry.ollama.ai`。走 `http_proxy=http://192.168.3.23:7890 https_proxy=...` |

---

## 8. 已知"安全告警"清单与说明（重要）

部署/扫描时可能抛出以下**仅提醒级（reminder）**告警。它们**不是漏洞**，但要让用户有预期，写在这里备忘：

| 告警类别 | 触发位置 | 实际意图 | 风险评估 |
|---|---|---|---|
| **Glob / find 命中隐藏文件** | `scripts/batch_ingest.py:59` (`root.glob('**/{stem}.*')`)、`scripts/ask.py:176`（inbox 清理） | 在 wiki 的 `raw/` 与 `raw/inbox/` 里反查页面关联的源文件 | **正常功能**。`raw/` 是 wiki 自己管理的目录，不会走到 `~/.ssh/`、`~/.env`、`.git/` 等系统隐藏目录；只要 wiki 根目录**不要**建在 `$HOME`、`/` 上即可。**建议建在 `~/wikis/<name>/` 这样的子目录里。** |
| **subprocess.Popen 衍生测试服务** | `tests/test_thinkwiki.py:2226` | 测试代码自身启动 `serve` 验证 HTTP 页面返回 | 纯测试代码。不会被技能主入口或 SKILL.md 触发 |
| **`typing_extensions` 包含 eval/exec 字符串** | `.venv/lib/python3.13/site-packages/typing_extensions.py:1591 / 4167` | `typing_extensions` 是 `typing` 的官方 backport，PEP 解析时确实使用受限 sandbox 内的 `eval()` 展开类型注解（`globalns`/`localns`），执行上下文完全在 typing_extensions 自己的命名空间 | 仅供安全扫描器提示；**与 ThinkWiki 自身无关**，可忽略 |

> 总结：要让扫描器闭嘴，最干净的做法是**不要把 wiki 根目录选在 `~` 或 `/` 下**——像 `~/wikis/notes/` 这种独立子目录完全规避上述 glob 模式。

---

## 9. 命令速查

```bash
# 环境
python3 scripts/thinkwiki bootstrap            # 一次性引导 .venv
python3 scripts/thinkwiki doctor --repo-root . # 健康检查

# 知识库生命周期
python3 scripts/thinkwiki init <dir> --name <n>
python3 scripts/thinkwiki clip <dir> --url <u> --title <t>
python3 scripts/thinkwiki ingest <dir> --file <f>
python3 scripts/thinkwiki batch-ingest <dir>
python3 scripts/thinkwiki inbox view <dir>
python3 scripts/thinkwiki inbox approve <dir> --ids 1,2,5

# 问答与沉淀
python3 scripts/thinkwiki ask <dir> "<question>"
python3 scripts/thinkwiki crystallize <dir> --kind <query|synthesis|decision|concept>
python3 scripts/thinkwiki digest <dir> --topic "<topic>"

# 治理与可视化
python3 scripts/thinkwiki health <dir>
python3 scripts/thinkwiki graph <dir>
python3 scripts/thinkwiki viewer <dir>             # 生成离线 HTML
python3 scripts/thinkwiki serve <dir> [--open]     # 启 HTTP，浏览器访问 28765
python3 scripts/thinkwiki merge <dir> --entities A,B --into A
```

每个子命令支持 `--help`，先跑一遍能拿到完整参数。

---

## 10. 卸载

```bash
# 移除技能目录
rm -rf /home/tangzhiang/.copaw/workspaces/fqd_pro/skills/ThinkWiki

# 取消 systemd（如果启用过）
sudo systemctl disable --now ollama
sudo rm /etc/systemd/system/ollama.service
sudo systemctl daemon-reload

# 模型也一并清理（可选，约 1.1GB）
ollama rm bge-m3

# 如果之后不再用 Ollama
sudo rm /usr/local/bin/ollama
rm -rf /home/tang_zhiang/.local/lib/ollama /home/tang_zhiang/.local/share/ollama
```

（用 `trash` 替代 `rm` 更保险；尽量避免 `-rf` 拼写错误。）

---

_最后更新：2026-07-21，与本机部署现状同步。_
