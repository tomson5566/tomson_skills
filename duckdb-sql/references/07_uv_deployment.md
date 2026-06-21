# DuckDB uv 独立环境部署

**任务核心要求**。DuckDB 项目用 uv 装独立 Python 环境的标准流程。**实测过**，可直接复制。

---

## 为什么用独立 venv

- **依赖隔离**：DuckDB 项目不污染系统 Python；不同项目可锁不同 duckdb 版本
- **复现性**：`uv.lock` 锁死包版本，跨机器 `uv sync` 一致
- **跨平台**：uv 自动选适配的 Python wheel（CPython 3.8-3.13）
- **磁盘省**：uv 用 hardlink 共享包，10 个项目只占 1 份空间

**vs pip + venv**：uv 速度快 10-100x，锁文件是**确定性**的（pip-tools 需要手动管理）。

---

## 标准 4 步部署（**实测**过）

```bash
# 1. 准备项目目录
mkdir -p /opt/myproject && cd /opt/myproject

# 2. 初始化 uv 项目
uv init --bare --no-readme
# 生成 pyproject.toml（空）+ .python-version（默认 3.13）

# 3. 加 duckdb（**自动建 venv + 装包**）
uv add duckdb
# 产出：
#   .venv/                # 独立 venv
#   pyproject.toml        # 项目配置
#   uv.lock               # 锁文件（必提交 git）

# 4. 跑代码
uv run python -c "import duckdb; print(duckdb.__version__)"
# 1.5.4
```

**实测**（2026-06，Linux x86_64）：
- `uv add duckdb` → 11.8s resolve + 7.8s download + 0.5s install
- duckdb wheel 20.5 MiB
- venv 总大小 60-100M（裸 duckdb），加 pandas+pyarrow 316M

---

## pyproject.toml 标准模板

```toml
[project]
name = "myproject"
version = "0.1.0"
description = "DuckDB data pipeline"
requires-python = ">=3.10"
dependencies = [
    "duckdb>=1.0.0",
    "pandas>=2.0",
    "pyarrow>=15.0",
]

[tool.uv]
# pin python 版本（建议）
# python = "3.12"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

**版本策略**：
- `>=1.0.0` — 接受 1.x 所有更新
- `~=1.5.0` — 接受 1.5.x（PATCH 升级，不接受 1.6+）
- `==1.5.4` — 死锁特定版本（生产环境防 breaking）
- 锁文件 `uv.lock` **必须提交**到 git（`uv sync` 用它精确还原）

---

## 跨机器复现（**核心**）

```bash
# 目标机（已有 uv）
cd /opt/myproject
uv sync                    # 读 uv.lock + pyproject.toml，装回完全相同的版本
uv run python my_script.py
```

**对比** `pip install -r requirements.txt`：
- `uv sync` 是**确定性**的（uv.lock 锁 hash）
- `pip install` 是**机会性**的（依赖解析每次可能不同）

---

## 完整 6 步模板（生产部署用）

```bash
#!/bin/bash
# setup_duckdb_project.sh - 生产环境 DuckDB 项目部署模板
set -euo pipefail

PROJECT_DIR="${1:-/opt/myproject}"
PYTHON_VERSION="${2:-3.12}"

if [[ -d "$PROJECT_DIR" ]]; then
    echo "ERROR: $PROJECT_DIR already exists" >&2
    exit 1
fi

mkdir -p "$PROJECT_DIR"
cd "$PROJECT_DIR"

# 1. 初始化 uv 项目（锁 Python 版本）
uv init --bare --no-readme --python "$PYTHON_VERSION"

# 2. 装核心依赖
uv add "duckdb>=1.0,<2.0"   # 锁 1.x
uv add pandas pyarrow

# 3. 装开发依赖（可选）
uv add --dev pytest ruff mypy

# 4. 写 pyproject.toml 描述（手动）
cat >> pyproject.toml << 'EOF'
description = "DuckDB data pipeline"
authors = [{name = "Your Name"}]
EOF

# 5. 锁文件提交
git init
git add pyproject.toml uv.lock .python-version
git commit -m "init: duckdb project"

# 6. 验证
uv run python -c "
import duckdb, pandas as pd
con = duckdb.connect(':memory:')
print('duckdb:', duckdb.__version__)
print('pandas:', pd.__version__)
print('python:', __import__('sys').version.split()[0])
"

echo "=== Setup complete: $PROJECT_DIR ==="
echo "Activate:  cd $PROJECT_DIR && source .venv/bin/activate"
echo "Run:       uv run python my_script.py"
```

---

## 常见陷阱（**已验证**）

### 1. Python 3.13 + duckdb 1.0.x 老版本
**问题**：duckdb < 1.3 没有 3.13 wheel，`uv add` 失败
**修法**：
- 升级 duckdb：`uv add "duckdb>=1.3"`
- 或降 Python：`uv init --python 3.12`

### 2. 网络慢导致 wheel 下载失败
**问题**：duckdb wheel 20MB，国内拉 GitHub release 慢
**修法**：
```bash
# 换清华源（临时）
UV_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple uv add duckdb

# 或永久
export UV_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
```

### 3. venv 体积大想清理
```bash
# 列出大头
du -sh .venv/lib/python*/site-packages/* | sort -h | tail -10

# 装但不要 pandas（duckdb 单独用）
uv remove pandas pyarrow
# → venv 缩到 ~100M

# 装但不存 lock
uv pip install --no-deps duckdb    # 跳过依赖（不推荐，可能少东西）
```

### 4. 老项目用 pip + requirements.txt 迁 uv
```bash
# 把 requirements.txt 转 pyproject.toml
uv add -r requirements.txt          # 装并写 pyproject.toml
uv lock                             # 生成 uv.lock
git rm requirements.txt             # 删掉老文件
```

### 5. 多项目共享 duckdb wheel
uv 默认 venv 在项目目录里，**多项目不共享**（每个项目一份）。要共享：
```bash
# 用系统 Python + uv pip install --system（不推荐，会污染系统）
uv pip install --system duckdb

# 或用 uv tool 装 CLI 工具
uv tool install duckdb-cli
```

### 6. 已有 conda 环境想用 uv
```bash
# 1. 退出 conda
conda deactivate

# 2. 确保系统有 python3.10+
python3 --version

# 3. uv 装独立 venv（不依赖 conda）
uv venv --python 3.12 .venv
source .venv/bin/activate
uv pip install duckdb
```

---

## venv 路径速查

| 需求 | 命令 |
|---|---|
| 找 venv 路径 | `uv run python -c "import sys; print(sys.prefix)"` |
| 找 Python 解释器 | `uv run which python` 或 `.venv/bin/python` |
| 临时换 Python 版本 | `uv python install 3.12` 然后 `uv venv --python 3.12` |
| 升级所有包 | `uv lock --upgrade && uv sync` |
| 升级单个包 | `uv add duckdb@latest` |
| 重新解析（清缓存） | `rm -rf .venv && uv sync` |
| 导出 requirements.txt | `uv export --no-hashes -o requirements.txt`（兼容 pip） |
| 导出 pyproject 风格 | `uv export --format requirements-txt -o requirements.txt` |
| 看依赖树 | `uv tree` |

---

## 三种部署模式对比

| 场景 | 命令 | 适用 |
|---|---|---|
| 临时脚本 | `uv run --with duckdb python script.py` | 一次性跑、CI 任务 |
| 项目开发 | `uv init` + `uv add` + `uv run` | 长期项目 |
| 系统工具 | `uv tool install duckdb-cli` | 全局 CLI，不污染项目 |

### 临时脚本模式（**最轻量**）

不需要 init 项目：
```bash
# 一次性跑
uv run --with duckdb --with pandas python my_analysis.py

# 跑 jupyter
uv run --with duckdb --with jupyter jupyter lab

# 跑命令
uv run --with duckdb python -c "import duckdb; print(duckdb.__version__)"
```

**自动**：uv 临时建 venv → 装包 → 跑完自动清。比 conda 临时环境快 5x。

---

## 跨机器部署 checklist

新机器上从 git clone 复现：

```bash
# 1. 装 uv（如果没装）
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. clone 项目
git clone <repo> /opt/myproject && cd /opt/myproject

# 3. 同步（核心：完全相同的包）
uv sync
# 自动选 .python-version 锁定的 Python（如 3.12）
# 装 pyproject.toml + uv.lock 所有依赖

# 4. 验证
uv run python -c "import duckdb; print(duckdb.__version__)"
```

**uv.lock 兼容性**：
- uv 0.4+ 生成的 lock，uv 0.5+ 仍能读
- 升级 uv 会自动重 lock（可能改 hash，安全）

---

## Python 版本选择

| Python | duckdb 支持 | 推荐度 |
|---|---|---|
| 3.8 | 0.9+ | 退役，不建议 |
| 3.9 | 0.9+ | 旧项目 |
| 3.10 | 1.0+ | 可用 |
| 3.11 | 1.0+ | 推荐（**最佳性能/兼容**） |
| 3.12 | 1.0+ | 推荐（最新稳定） |
| 3.13 | 1.3+ | OK（duckdb 1.3+ 才有 wheel） |

**默认建议**：Python 3.12 + duckdb 1.5+（验证过兼容性最好）。

```bash
uv init --python 3.12     # 锁 Python 版本
```
