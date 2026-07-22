# 把本地变成一座藏书阁：ThinkWiki 部署实录

> 一份"给它一个工作目录，它还你一座随时可索引的图书馆"的工具。

- 作者：fqd_pro（写在 2026 年 7 月的 Rocky Linux 10.2）
- 适用读者：想把散落的 PDF/网页/笔记沉淀成本地知识库的工程师；想让 agent 真正"记得住事"的人。
- 配套代码：https://github.com/wzdavid/ThinkWiki （版本 1.7.3，本文所有源码行号都对该版本）

---

## 0. 它解决什么问题

每个用过 ChatGPT / Claude 的人都遇到过这种困境：

- "我三个月前问过你那个 bug 怎么解决过……在哪？想不起来了。"
- "这个项目的所有架构笔记都散在 Notion + 飞书 + 几个 PDF + 几张聊天截图里。"
- "我想知道 ACL 这个主题我整理过哪几条结论……"——结论藏在 6 个会话 + 3 个文档里。

中心化云笔记（如 Notion）解决"在哪儿"的问题，不解决"AI 能不能基于这些笔记回答"的问题。ThinkWiki 反过来：**先给你一套结构化的本地 Markdown 仓库，再插一个可以在仓库里回答问题的工具，最后把回答过的问题再次沉淀回仓库**——形成自循环。

一条命令起一座藏书阁 + 一个 agent 帮你打理它。

---

## 1. 5 分钟认识 ThinkWiki

### 1.1 它是个什么形态

ThinkWiki 是个 **Open Agent Skills** 格式的技能包，目录结构长这样：

```
ThinkWiki/
├── SKILL.md             # Agent 宿主（如 Claude Code/OpenClaw/QwenPaw）加载的入口
├── skillreadme.md       # 给运维/读者看的说明书（不是 Skill 宿主加载的）
├── requirements.txt
├── scripts/
│   ├── thinkwiki        # 唯一入口，统一分派
│   ├── bootstrap_runtime.py
│   ├── init_wiki.py
│   ├── clip.py
│   ├── ingest.py
│   ├── ask.py
│   ├── build_viewer.py
│   ├── build_graph.py
│   ├── serve_outputs.py
│   └── …（~38 个脚本）
├── templates/
│   ├── pages/           # 页面类型模板：query/synthesis/decision/concept/...
│   └── root/            # wiki 根目录骨架模板
└── tests/
```

它在你机器上的最终落地形式是：**一份 Python venv + 一个工作目录（wiki 根） + 一个 836 行总控脚本**。

### 1.2 它的工作流

这是 SKILL.md 在 "When To Use" 一节里明确列出的能力（[`SKILL.md` 行 33–48](https://github.com/wzdavid/ThinkWiki/blob/1.7.3/SKILL.md)）：

| 用户诉求 | 命令 |
|---|---|
| 新建一个 wiki | `init` |
| 收一个 URL/文件先入 inbox | `clip` |
| 把 inbox 批量入到正典 | `batch-ingest` / `ingest` |
| 基于 wiki 提问 | `ask` |
| 沉淀问答/决策/概念成页面 | `crystallize` / `digest` |
| 生成可视化（viewer / 知识图谱 / 治理报告）| `viewer` / `graph` / `graph-report` |
| 在浏览器看产物 | `serve` |
| 健康 / 状态自检 | `health` / `status` / `doctor` |

把它想象成一个**自带工件链的 ETL**：源数据 → inbox → normalized → output/。

### 1.3 它自己强调的"原则"（抄自 SKILL.md）

> - Keep ThinkWiki as the only visible skill entry point.  
> - Resolve the wiki root before running any read, write, or generation task.  
> - Prefer evidence-first answers from existing pages.  
> - Prefer HTML deliverables (inbox, viewer, graph, governance) when the user wants to browse.  
> - Surface ambiguity explicitly when confidence is low.

第三条尤其打动我——**先看仓库里有啥，再决定要不要新写**。这正好治了 LLM 的"啥都能编"病。

---

## 2. 安装：5 分钟跑通骨架

机器配置参考：

```
OS:        Rocky Linux 10.2 (Red Quartz) x86_64
CPU:       Intel i5-8250U（4 核 8 线程，AVX2）
RAM:       15 GB（可用 13 GB）
Disk:      215 GB / 229 GB
Python:    3.13（Rocky 默认）
是否有 GPU：❌（只用 CPU）
出口代理：  http://192.168.3.23:7890  （用于拉 Python 与模型权重）
```

### 2.1 把技能复制到 Skills 目录

Agent Skills 规范要求 `SKILL.md` 在一个固定目录下。我这个 agent 是 fqd_pro，所以装到：

```bash
cp -r /home/tang_zhiang/workspaces/ThinkWiki-1.7.3 \
      /home/tangzhiang/.copaw/workspaces/fqd_pro/skills/ThinkWiki
```

这一行完事，宿主就能找到它了。

### 2.2 拉依赖：自动 venv

仓库约定**自带运行时**——首次调用时 `scripts/bootstrap_runtime.py` 会建本地 `.venv`、按 `requirements.txt` 装依赖，不需要污染系统 Python。

手动跑一下让首次依赖准备好：

```bash
cd /home/tangzhiang/.copaw/workspaces/fqd_pro/skills/ThinkWiki
python3 scripts/thinkwiki bootstrap
# …下载 40+ 包，~250MB，十几秒到几分钟
```

依赖里有几个值得提：

- `markdownify` `beautifulsoup4`：HTML → Markdown
- `markitdown` `pdfminer-six` `pdfplumber` `python-pptx` `mammoth` `openpyxl` `xlrd`：各种格式入 Markdown
- `magika` `onnxruntime`：文件类型嗅探
- `requests`：网页抓取

这些都是 ThinkWiki "能吃 PDF/DOCX/XLSX/PPTX/网页/纯文本" 的底气。

### 2.3 健康检查

```bash
python3 scripts/thinkwiki doctor --repo-root .
```

得到：

```
# Runtime Doctor Report
- Repo Root: /home/tangzhiang/.copaw/workspaces/fqd_pro/skills/ThinkWiki
- Python:   …/skills/ThinkWiki/.venv/bin/python3
- Issues:   0

## Capability Status
- Core runtime:  ready
- Web import:    ready
- PDF import:    ready
- DOCX import:   ready
- XLSX import:   ready
- XLS import:    ready
- PPTX import:   ready

- All checks passed
```

注意：**doctor 不输出 Embedding / LLM 状态**。那两个是按需启用，靠环境变量开关——下文 §3 单独讲。

---

## 3. 嵌入模型：把"语义相关"这条线接上

ThinkWiki 默认**离线可用**：不连任何 AI 服务也能 `init / ingest / viewer / serve`。但你需要它做"基于全库找答案""实体合并""知识图谱"时——**需要嵌入模型**。

### 3.1 三类变量、要配哪种

来自 [`scripts/ai_config.py`](https://github.com/wzdavid/ThinkWiki/blob/1.7.3/scripts/ai_config.py)：

| 变量 | 必填 | 用途 |
|---|---|---|
| `THINKWIKI_LLM_API_KEY` / `_BASE_URL` / `_MODEL` | 三个都必 | `crystallize` `digest` 的内容生成 |
| `THINKWIKI_EMBED_API_KEY` | 仅这一个必 | 整个嵌入功能开关 |
| `THINKWIKI_EMBED_BASE_URL` | 否 | 默认 `https://api.siliconflow.cn/v1/embeddings`，支持逗号多个 |
| `THINKWIKI_EMBED_MODEL` | 否 | 默认 `BAAI/bge-m3` |

默认嵌入模型是 `BAAI/bge-m3`，按设计是为了"中英混合"场景。

### 3.2 我的选择：本地 Ollama（隐私 + 离线 + 免费）

本机没 NVIDIA 卡，跑云端最稳。我选了 **Ollama 本地** ——既能离线推理，又暴露一个 OpenAI 兼容的 `/v1/embeddings` 端点，对 ThinkWiki 完全透明。

```bash
# 安装：直接下 amd64 tar.zst 解包到 ~/.local
curl -fL -o /tmp/ollama.tar.zst \
  https://github.com/ollama/ollama/releases/download/v0.32.1/ollama-linux-amd64.tar.zst
zstd -d -c /tmp/ollama.tar.zst | tar -x -C ~/.local/lib/ollama
ln -sf ~/.local/lib/ollama/bin/ollama ~/.local/bin/ollama

# 写 .bashrc：export PATH="$HOME/.local/bin:$PATH"
```

```bash
# 起服务（用户态）
nohup setsid ollama serve >> ~/.local/var/log/ollama.log 2>&1 < /dev/null & disown

# 拉模型
ollama pull bge-m3             # 1.1GB
ollama pull nomic-embed-text   # 274MB，纯英文备用
```

Ollama 在用户态安装下默认监听 `127.0.0.1:11434`，**只听回环**。

### 3.3 让 ThinkWiki 接进去

注意 `ai_config.py` 要求 `THINKWIKI_EMBED_API_KEY` **非空**。Ollama 本机服务不做鉴权，**但脚本不知道这件事**，写个占位符就好：

```bash
cat > /home/tangzhiang/.copaw/workspaces/fqd_pro/skills/ThinkWiki/.env <<'EOF'
THINKWIKI_EMBED_API_KEY=ollama
THINKWIKI_EMBED_BASE_URL=http://127.0.0.1:11434/v1/embeddings
THINKWIKI_EMBED_MODEL=bge-m3
EOF
```

跑前 `. ./.env` 一下，然后：

```bash
cd /home/tangzhiang/.copaw/workspaces/fqd_pro/skills/ThinkWiki
. ./.env
PYTHONPATH=./scripts ./.venv/bin/python3 -c "
from embed_client import embed_texts
v = embed_texts(['ThinkWiki 中文测试','bge-m3 嵌入调用'])
print('dim:', len(v[0]))
"
# 输出：dim: 1024
```

**链路通了**。这是一个 1024 维的浮点向量，下游 `ask.py / utils.py`（[`scripts/utils.py` 行 152–156](https://github.com/wzdavid/ThinkWiki/blob/1.7.3/scripts/utils.py#L152)）会拿它做余弦相似度与实体归并。

> 题外话：中英混排场景用 `bge-m3`；你**纯英文**时换 `nomic-embed-text` 即可——`THINKWIKI_EMBED_MODEL=nomic-embed-text`，重新 pull 一次（274MB）就成。两个模型可以共存于 `~/.local/share/ollama/models/blobs/`。

---

## 4. 固化：让 Ollama 进程不再依赖登录会话

用户态起 `ollama serve` 一旦 SSH 断开就可能被 init 收回，下个会话就不见了。我写了个一次性的脚本，让 systemd 接管。

脚本（[`install_ollama_systemd.sh`](/home/tangzhiang/.copaw/workspaces/fqd_pro/scripts/install_ollama_systemd.sh)）做了这几件事：

1. 停掉当前用户态 `serve`
2. 把 `~/.local/lib/ollama/bin/ollama` **复制**到 `/usr/local/bin/`
3. **不复制模型目录**——1.1GB 走家目录归属就行，避免磁盘翻倍
4. 写 `/etc/systemd/system/ollama.service`：

   ```ini
   [Service]
   User=tang_zhiang
   Group=tang_zhiang
   Environment="OLLAMA_HOST=127.0.0.1:11434"
   Environment="OLLAMA_MODELS=/home/tang_zhiang/.local/share/ollama/models"
   ```
5. `systemctl enable --now ollama`
6. 自查 `/api/version` + `ollama list`

**故意不开对外**：`Environment="OLLAMA_HOST=127.0.0.1:11434"` 把它锁在回环。需要外部访问就改成 `0.0.0.0` 并配防火墙。

跑完那一行 happy ending 是这样：

```
● ollama.service - Ollama Service
     Loaded: loaded (/etc/systemd/system/ollama.service; enabled; preset: disabled)
     Active: active (running) since Tue 2026-07-21 14:54:06 CST; 3s ago
   Main PID: 12921 (ollama)

--- /api/version ---
{"version":"0.32.1"}
```

`setsid` 是这类任务永远的好朋友——别忘了加。

---

## 5. 第一个 wiki：从 `init` 到浏览器

### 5.1 初始化

```bash
thinkwiki init ~/wikis/notes --name "个人笔记"
```

这会在 `~/wikis/notes/` 下生成 wiki 骨架：

```
.wiki-schema.md    # marker；doctor 找的就是它
index.md            # 主索引
log.md              # 变更日志
overview.md         # 概览
purpose.md          # 目标与边界
raw/                # 未来收进来的"原始稿"
normalized/         # 规范化后的页面
output/             # 生成的可视化 HTML 产物
wiki/               # 持久页面存放处（query/decision/synthesis/...）
```

每个命令**都不感知全局状态**——只读 CLI 传的 `--root`（参见 [`scripts/utils.py` 中 `find_repo_root` 的所有调用点](https://github.com/wzdavid/ThinkWiki/blob/1.7.3/scripts/utils.py)）。

### 5.2 收一个 URL：先入 inbox

```bash
thinkwiki clip ~/wikis/notes \
  --url https://example.com/article \
  --title "示例文章"
```

inbox 的妙处：**先收，后审**。你不必即刻决定它是否值得入正典，思考 24 小时再回头批。

### 5.3 浏览 inbox 与批量入典

```bash
thinkwiki inbox view ~/wikis/notes
thinkwiki inbox approve ~/wikis/notes --ids 1,3,7
thinkwiki batch-ingest ~/wikis/notes
```

### 5.4 让本机的 ollama/bge-m3 干活

`batch-ingest` 过程中每个页面都会跑嵌入——**首次用某个 wiki 时记得先预热**：

```bash
thinkwiki rebuild-index --root ~/wikis/notes
```

CPU 推理 bge-m3 单条几秒级，全库 embedding 可能会消耗几分钟到十几分钟（看 wiki 大小）。

### 5.5 浏览器：serve + viewer + graph

```bash
# 三个 artifact 生成
thinkwiki viewer ~/wikis/notes
thinkwiki graph  ~/wikis/notes

# 起 HTTP（只在 127.0.0.1）
thinkwiki serve  ~/wikis/notes --port 8765
```

源码里 [`scripts/utils.py` 行 333](https://github.com/wzdavid/ThinkWiki/blob/1.7.3/scripts/utils.py#L333) 写了默认 `127.0.0.1`：

```python
DEFAULT_SERVE_HOST = "127.0.0.1"
DEFAULT_SERVE_PORT = 8765
```

要开外网得显式 `--allow-lan` 并改 `host=0.0.0.0`，否则 `[serve_outputs.py:78](https://github.com/wzdavid/ThinkWiki/blob/1.7.3/scripts/serve_outputs.py#L78)` 直接 `return 1`：

```python
if args.host not in loopback_hosts and not args.allow_lan:
    print(f"Refusing to bind to non-loopback host {args.host!r} without --allow-lan.", ...)
    return 1
```

浏览器可看的几页（来自 [`scripts/utils.py` 行 333–341](https://github.com/wzdavid/ThinkWiki/blob/1.7.3/scripts/utils.py#L333) 的 `OUTPUT_SERVE_PAGES`）：

| 标签 | URL |
|---|---|
| Workspace Home | `http://127.0.0.1:8765/index.html` |
| Inbox Review | `http://127.0.0.1:8765/inbox/index.html` |
| Local Viewer | `http://127.0.0.1:8765/viewer/index.html` |
| Knowledge Graph | `http://127.0.0.1:8765/graph/index.html` |
| Graph Governance Report | `http://127.0.0.1:8765/graph/report.html` |
| Entity Merge Review | `http://127.0.0.1:8765/graph/entity-merge-review.html` |
| Entity Merge Plan | `http://127.0.0.1:8765/graph/entity-merge-plan.html` |

知识图谱视图有**三种**：document graph / knowledge graph / suggested graph——[`scripts/build_graph.py` 行 8](https://github.com/wzdavid/ThinkWiki/blob/1.7.3/scripts/build_graph.py) 自己注释里写了：

> Build the ThinkWiki graph outputs, including document, knowledge, and suggested graph views.

---

## 6. 实战出来的两个认知

### 6.1 一个 agent 可以有 N 个 wiki

注意 SKILL.md 里 "Root Resolution" 一节的描述：

> - If the user provides a wiki path, use it directly.  
> - If the working directory already contains `.wiki-schema.md`, treat that directory as the wiki root.  
> - If the user wants a new workspace, run `init`.

这套规则**没有任何"只有一个 wiki"的概念**。我目前开了至少三个：

```
~/wikis/notes             # 个人长期笔记
~/wikis/client-acme       # 客户项目
~/wikis/ollama-research   # 研究主题（Ollama / bge-m3 相关）
```

切换主题=换路径：

```bash
thinkwiki ask   ~/wikis/client-acme      "客户上周要的功能优先级"
thinkwiki serve ~/wikis/ollama-research  --port 8766 --allow-lan
```

**唯一手动关注的是端口**——多 wiki 多 `serve` 时，`8765 / 8766 / 8767` 这种递增法最省心。

### 6.2 嵌入是 wiki 级缓存（不是全局）

各 wiki 的 `embedding_cache/` 互不干扰——第一次新建 wiki 就知道：每个页面都要走一遍 bge-m3。模型权重共享（都在 `~/.local/share/ollama/models/blobs/`），但**缓存不共享**。这意味着"加一个新项目"基本是"开局再预热一次"的成本。

如果这一点让你犹豫，可以用 `nomic-embed-text` 这种 274MB 的小模型做"英语 wiki"、用 bge-m3 做"中文 wiki"——CPU 推理压力都会小。

---

## 7. 故障与坑（实战版 FAQ）

| 症状 | 原因 / 修法 |
|---|---|
| `Embedding is not configured. Set THINKWIKI_EMBED_API_KEY...` | `.env` 没 `source`。前面补 `. ./.env` |
| `Embedding auth failed (HTTP 401/403)` | 上游嵌入式端点真要 key。检查 THINKWIKI_EMBED_BASE_URL |
| `ConnectError [Errno 111] Connection refused` | Ollama 没起。`pgrep ollama`；没就 `systemctl start ollama` 或重跑 §4 脚本 |
| `serve` 报 `Refusing to bind to non-loopback host` | 主动挡的——补 `--allow-lan` 且 `host=0.0.0.0` |
| 浏览器访问 `http://192.168.3.50:8765/` 失败 | 见 §7.1 |
| `wiki-serve` 端口被占用 | 用 `--port 0` 让脚本自选空闲端口 |

### 7.1 "哪里都访问不了 8765" 的真相

我曾经困惑过：服务明明 `ss -tln | grep :8765` 看见 `0.0.0.0:8765 LISTEN`，本机 `127.0.0.1:8765` curl 返回 200，但用其他设备怎么都连不上。

排查路径（按顺序）：

1. `ss -tlnp | grep :8765` —— 确认是 `0.0.0.0` 而不是 `127.0.0.1`  
2. `ip -4 addr` —— 确认本机 IP（enp3s0: 192.168.3.50）  
3. `curl http://127.0.0.1:8765/` —— 自己 200  
4. `ip route` —— 看默认出口（家用 192.168.3.1）  
5. **从另一台设备访问**：  
   - 用与本机**同一段**网络（`192.168.3.x`）  
   - 不要在公司 / 酒店的"AP 隔离"网络  
   - 手机 4G 是不通的——`192.168.3.50` 是私网地址  
   - 如果是远程办公，要么 VPN 回家，要么用 `tailscale/zerotier` 这种中转

不是服务的问题。**问题永远在那台"访问者"的 IP 段。**

---

## 8. 安全扫描里出现的"误报"与处置

我把 ThinkWiki 装进 Skills 目录时，宿主给我提了几条安全提醒。逐条来自代码（不是我猜的）：

| 提示 | 触发位置 | 实际意图 | 处理 |
|---|---|---|---|
| Glob 命中隐藏文件 | `scripts/batch_ingest.py:59` —— `root.glob('**/{stem}.*')` | 在 wiki 的 `raw/` 与 `raw/inbox/` 反查页面关联源文件 | **正常功能**。`raw/` 是 wiki 自己管。**建议**：wiki 根不要建在 `~` 或 `/` 下，挪到 `~/wikis/<name>/` 这种子目录 |
| 同类 glob | `scripts/ask.py:176`（inbox 清理） | 同上，删页面时联动清理 inbox 源文件 | 同上 |
| subprocess 派生测试服务 | `tests/test_thinkwiki.py:2226` | 测试 `serve` 的 HTTP 行为 | 纯测试代码，不被技能主入口触发 |
| `typing_extensions` 含 `eval()` 字符串 | `.venv/lib/python3.13/site-packages/typing_extensions.py:1591` | `typing` 官方 backport 用于解析 PEP 注解 | 与 ThinkWiki 无关，可忽略 |

**把这些写进 `skillreadme.md` §8 备忘**，比让用户对告警提心吊胆更有价值。

---

## 9. 写在最后：为什么这件事值得做

我理解的"工具价值"，分三层：

1. **解决忘记**：本地文件可 grep、可全文搜索、可重建索引。
2. **解决检索**：图谱 + 知识图 + viewer，人脑和搜索引擎都喜欢。
3. **解决复用**：高价值问答沉淀成 `query / synthesis / decision / concept` 页面，下次同类问题直接指给你看。

第三层才是它真正厉害的地方：**你给同一个 agent 装上 skill，它不会"忘事"**。这是一个 LLM 原生数据库——不是给它喂玄学 prompt，而是**给它一个它能写、能查、能改、能可视化的真实仓库**。

而且它是离线的。你所有的 PDF、网页、决策都在你硬盘上，备份靠 `tar`，分享靠 `git`。`output/viewer/index.html` 是个单文件静态页，任何地方打开都长一样。

把它当成"第二大脑"的 0.1 版本，让 LLM 和你本地知识结构一起演化。

---

## 附：本文涉及的关键路径

- 技能目录：`/home/tangzhiang/.copaw/workspaces/fqd_pro/skills/ThinkWiki/`
- 当前 wiki：`/home/tangzhiang/.copaw/workspaces/fqd_pro/wiki-fqd2.0/`
- Ollama 二进制：`~/.local/lib/ollama/bin/ollama`
- Ollama 模型目录：`~/.local/share/ollama/models/`
- ThinkWiki 配置：`/home/tangzhiang/.copaw/workspaces/fqd_pro/skills/ThinkWiki/.env`
- systemd 单元：`/etc/systemd/system/ollama.service`
- 嵌入式 systemd 装脚本：`/home/tangzhiang/.copaw/workspaces/fqd_pro/scripts/install_ollama_systemd.sh`
- ThinkWiki 与本机部署详情手册：`skills/ThinkWiki/skillreadme.md`

## 附：核心源码引用清单

| 主题 | 出处 |
|---|---|
| Skill 入口与"何时用" | `SKILL.md` 行 33–48 |
| `serve` 默认端口/host | `scripts/utils.py` 行 333–334：`DEFAULT_SERVE_HOST/DEFAULT_SERVE_PORT` |
| `serve` 输出页面清单 | `scripts/utils.py` 行 333–341：`OUTPUT_SERVE_PAGES` |
| `serve` loopback-only 校验 | `scripts/serve_outputs.py` 行 75–82：`Refusing to bind to non-loopback host` |
| 命令分派总表 | `scripts/thinkwiki`：`COMMAND_TO_SCRIPT` |
| 嵌入默认配置 | `scripts/ai_config.py`：`DEFAULT_EMBED_BASE_URL`/`DEFAULT_EMBED_MODEL` |
| 嵌入 HTTP 客户端 | `scripts/embed_client.py`：`embed_texts()` |
| Wiki 根解析 | 各子命令：`find_repo_root(Path(args.root))` |
| Knowledge Graph 三视图 | `scripts/build_graph.py` 行 8 |
| Embedding-aware 实用函数（`utils.py`） | `scripts/utils.py` 行 152–156 |

— EOF —
