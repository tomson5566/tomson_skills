# Server 模式（Web UI）

> ingestr 还有一个 Web UI（`ingestr server`），但它不是主战场——主要是让非工程师能点几下配 ingestion。
> 生产里大多数用 CLI + 调度器（Airflow/Dagster）。

## 1. 启动

```bash
ingestr server --port 8080
# 浏览器开 http://localhost:8080
```

## 2. flag

| Flag | 默认 | 用途 |
|------|------|------|
| `--port` | 8080 | 监听端口 |
| `--creds-file` | `creds.json` | 凭证文件（UI 让你填的连接信息存这里）|
| `--logs-dir` | `logs` | job 日志目录 |
| `--db` | `ingestr.db` | SQLite 状态库（job 历史） |

## 3. creds.json 格式

```json
{
  "sources": {
    "my_pg": {
      "uri": "postgres://u:p@host:5432/db"
    },
    "my_stripe": {
      "uri": "stripe://api_key@api.stripe.com/v1",
      "auth": "bearer"
    }
  },
  "destinations": {
    "my_bq": {
      "uri": "bigquery://project?credentials_path=/path/sa.json"
    }
  }
}
```

**不要提交到 git**——加 `.gitignore`。

## 4. 适用场景

| 用 | 推荐 |
|----|------|
| 数据分析师手动跑 ingestion | ✅ Server UI 友好 |
| 生产 CI/CD | ❌ 用 CLI + Airflow |
| Demo 给非工程师看 | ✅ Server UI 好用 |
| 复杂调度依赖 | ❌ Server 没调度，CLI 接外部调度 |
| 看 job 历史 | ✅ Server 有（SQLite 存）|

## 5. 跟 CLI 的关系

- Server 底层还是调 CLI
- Server 帮你生成命令（不用自己拼 URI）
- Server 把 job 历史存 SQLite

**简单说**：Server 是 ingestr 的"包装壳"，核心功能在 CLI。

## 6. 安全注意

- 默认监听 `0.0.0.0`（**任何人都能访问**）
- 生产环境**必须**加反向代理 + 认证（`--creds-file` 不带认证）
- 不要在公网直接暴露 `--port`

```bash
# 不要这样：
ingestr server --port 8080  # 全网可访问

# 改成：
ingestr server --port 127.0.0.1:8080  # 仅本地
# 然后 nginx/caddy 反代 + basic auth
```

## 7. 不推荐的理由

| 原因 | 解释 |
|------|------|
| 没调度 | 没有"每天 3 点跑"这种 |
| 没依赖 | 没有"orders 跑完跑 summary" |
| 没 lineage | 没有"这表来自 X" |
| 没重试 | job 失败没自动重试 |
| 没监控 | 没有 metrics / alert |
| 没认证 | 公网暴露风险 |

**生产路线**：CLI + Airflow/Dagster + Prometheus + Grafana。

## 8. 跟 Bruin 平台的关系

ingestr 是 Bruin 平台的 ETL 引擎。Server 模式相当于"Bruin 的极简版"。

完整功能（B Bruin Cloud）有：调度、lineage、监控、协作 UI、SSO——比 `ingestr server` 强很多。

ingestr OSS + Bruin Cloud 是"开源引擎 + 商业平台"模式。

## 9. 实战场景

**场景：给数据分析师用**

```bash
# 1. 启动 server
ingestr server --port 8080 --creds-file team_creds.json

# 2. 告诉分析师："开 http://hostname:8080"
# 3. 分析师自己点：选源 → 选目标 → 选表 → 选策略 → 跑
```

**场景：本地开发测试**

```bash
ingestr server --port 8080 --creds-file dev_creds.json
# 本地 Chrome 调 http://localhost:8080
```

**场景：生产**

```bash
# 不要用 server。用 CLI + Airflow。
# Airflow BashOperator 调 ingestr CLI
```

## 10. 替代方案对比

| 方案 | 调度 | UI | 复杂度 | 适合 |
|------|------|-----|--------|------|
| `ingestr server` | ❌ | 简单 | 低 | 内部 demo |
| `ingestr` + cron | ✅ | ❌ | 低 | 单机小项目 |
| `ingestr` + Airflow | ✅ | 强 | 中 | 生产标准 |
| `ingestr` + Dagster | ✅ | 强 | 中 | 资产为中心 |
| `ingestr` + Prefect | ✅ | 强 | 中 | Python 友好 |
| `ingestr` + Bruin Cloud | ✅ | 极强 | 中 | Bruin 生态 |

## 11. 进一步阅读

- 源码：`cmd/server.go` + `internal/server/`
- 官方：`docs/commands/server.md`（看实际版本）
