# ingestr 完整 flag 参考（v1.0.21）

> 来自 `ingestr ingest --help` 实际输出 + 源码 `cmd/ingest.go`。
> 每个 flag 都有 `INGESTR_<NAME>` 和短名 `<NAME>` 两种环境变量别名。

## 必填

| Flag | 用途 |
|------|------|
| `--source-uri` | 源 URI（含凭证） |
| `--dest-uri` | 目标 URI |

## 核心

| Flag | 默认 | 用途 |
|------|------|------|
| `--source-table` | (空) | 源表名（schema.table 或 `query:SQL`） |
| `--dest-table` | 同 source-table | 目标表名 |
| `--incremental-strategy` | `replace` | 策略：`replace`/`truncate+insert`/`append`/`delete+insert`/`merge`/`scd2`/`none` |
| `--yes` / `-y` | false | 跳过确认提示直接跑 |

## 增量配置

| Flag | 用途 |
|------|------|
| `--incremental-key` | 增量键列名（如 `updated_at`） |
| `--interval-start` | 区间起点（ISO 8601） |
| `--interval-end` | 区间终点（ISO 8601） |
| `--primary-key` | 主键（可多次指定：`--primary-key id --primary-key tenant_id`） |
| `--full-refresh` | 忽略状态，全量重来（默认 false） |
| `--cdc-resume-lsn` | CDC 模式 resume LSN（一般自动推断） |

## Schema 与命名

| Flag | 默认 | 用途 |
|------|------|------|
| `--schema-contract` | `evolve` | `evolve` / `freeze` / `discard_row` / `discard_value` |
| `--schema-naming` | `auto` | `direct` / `snake_case` / `auto` |
| `--columns` | (空) | schema-less 源的手动列定义：`id:bigint,name:text,created_at:timestamp` |
| `--no-inference` | false | 跳过 schema 推断（用 --columns 当 schema） |

## 性能与行为

| Flag | 默认 | 用途 |
|------|------|------|
| `--extract-parallelism` | 4 | 源端并行度 |
| `--page-size` | 取决于 source | 分页大小 |
| `--loader-file-size` | 取决于 dest | 加载文件分片大小 |
| `--loader-file-format` | 取决于 dest | 加载文件格式（parquet/csv） |
| `--progress` | `interactive` | `interactive` / `log` |
| `--sql-limit` | 0（无限） | 限制 SQL 拉取行数（debug 用） |
| `--sql-exclude-columns` | (空) | SQL 拉取时排除列（可多次指定） |
| `--debug` | false | 打 debug 日志 |

## 目标表结构

| Flag | 用途 |
|------|------|
| `--partition-by` | 目标表分区列（BigQuery） |
| `--cluster-by` | 目标表聚簇列（可多次指定，BigQuery） |
| `--staging-bucket` | 临时文件落盘 bucket（部分 dest 用） |
| `--staging-dataset` | 临时表落盘 dataset |
| `--keep-staging` | 跑完不删 staging 表（debug 用） |

## 数据处理

| Flag | 用途 |
|------|------|
| `--mask` | 列脱敏，格式 `<column>:<algorithm>[:<param>]`，可多次指定 |
| `--query-annotations` | JSON 注解，附到目标 SQL（cost attribution） |

## 其他

| Flag | 用途 |
|------|------|
| `--pipelines-dir` | pipeline 文件目录（多 pipeline 模式） |
| `--creds-file` | 凭证文件（server 用） |
| `--version` / `-v` | 打印版本 |

## 环境变量

所有 flag 都有环境变量别名（`cli.EnvVars`）。优先级：CLI flag > 环境变量 > 默认值。

```bash
export INGESTR_SOURCE_URI="postgres://..."
export INGESTR_DEST_URI="bigquery://..."
export INGESTR_INCREMENTAL_STRATEGY="merge"
export INGESTR_INCREMENTAL_KEY="updated_at"
export INGESTR_PRIMARY_KEY="id"  # 单值；多值用空格或重复
ingestr ingest
```

## `--mask` 算法

格式：`--mask <column>:<algorithm>[:<param>]`

| Algorithm | Param | 效果 |
|-----------|-------|------|
| `hash` | - | SHA256 哈希 |
| `partial` | 末位保留 N 位 | `123456789` → `123456789` 末 4 位 + `*****` |
| `round` | 圆整基数 | `12345` → `12000`（百位圆整） |
| `nullify` | - | 全部置 NULL |
| `redact` | - | 替换为 `***REDACTED***` |

```bash
--mask "email:hash"
--mask "ssn:partial:4"
--mask "salary:round:1000"
--mask "phone:redact"
```

## 调试输出格式

时间戳前缀：
- info：`[15:04:05]`
- debug：`[15:04:05.000]`

阶段标签：
- `[STRATEGY]`, `[MERGE]`, `[STAGING]`, `[SCHEMA]`, `[CDC]` 等

## 退出码

- 0：成功
- 1：失败（错误信息打到 stderr，红字）

## Server 子命令额外 flag

| Flag | 默认 | 用途 |
|------|------|------|
| `--port` | 8080 | 监听端口 |
| `--creds-file` | `creds.json` | 凭证文件 |
| `--logs-dir` | `logs` | job 日志目录 |
| `--db` | `ingestr.db` | SQLite 状态库 |
