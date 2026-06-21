# ingestr 排错指南

> 按"症状 → 原因 → 解决"组织。所有错误都来自源码 `*_test.go` 和 `*ValidationError` 的实际语义。

## 连接类

### `unsupported source scheme: xxx`

- **原因**：URI scheme 拼错 / 不支持
- **解决**：
  - 检查 scheme 拼写（小写、不要有空格）
  - 看 `docs/commands/example-uris.md` 确认支持哪些
  - 文件型：必须是 `///path`（三斜杠）

### `failed to connect to source: ...`

- **原因**：URI 里 host/port/user/pass/db 错，或者网络不通
- **解决**：
  - 用 `psql` / `mongosh` / `mysql` 等原生 client 先连一遍
  - 检查防火墙 / 安全组
  - 检查 SSL 设置（PG 加 `?sslmode=disable`）
  - 检查 `+` 复合 scheme（如 `postgresql+psycopg2` 自动转 `postgres`）

### `failed to ping postgres` / `connection refused`

- **原因**：服务没起、端口错、DNS 错
- **解决**：先 `telnet host port` 验证连通性

## Schema 类

### `merge strategy requires at least one primary_key`

- **原因**：merge 必须有 PK
- **解决**：加 `--primary-key <col>`（可多值）
- **旁路**：如果源表有自然 PK（如 PG 的 `PRIMARY KEY` 约束），部分 source 会自动填，但显式指定更安全

### `column "xxx" does not exist`

- **原因**：源表不存在、或者用了错的 schema 名
- **解决**：
  - PG：`--source-table "schema_name.table_name"`
  - 检查拼写
  - 用 `query:SELECT ...` 走自定义 SQL 绕开

### schema evolution 报错

- **症状**：`--schema-contract freeze` 模式下抛错
- **原因**：源 schema 跟目标不匹配
- **解决**：
  - 改 `--schema-contract evolve`（默认，放行）
  - 或改 `discard_row` / `discard_value`
  - 或用 `--full-refresh` 全量重置

### MongoDB 等无 schema 源报错

- **症状**：`schema inference failed`
- **解决**：
  - 手动指定列：`--columns "id:bigint,name:text,created_at:timestamp"`
  - 加 `--no-inference` 强制用 `--columns` 不用推断

## 权限类

### BigQuery `permission denied` / `403`

- **检查项**：
  - `credentials_path` 指向的 SA JSON 是否有效
  - SA 是否有 BigQuery Data Editor / Job User 角色
  - 项目 ID 是否对
- **调试**：`gcloud auth activate-service-account --key-file=...` 然后 `bq ls`

### Snowflake `Insufficient privileges`

- **检查项**：
  - `role=` 参数填的角色是否有 USAGE on warehouse / database / schema
  - 是否有 INSERT 权限
  - 凭证里的 user/pass 是否对

### Postgres `permission denied for table`

- **检查项**：
  - 用户对源表有 SELECT
  - 用户对目标 schema 有 CREATE / INSERT

## 性能类

### 跑得太慢

- **检查项**：
  - 调 `--extract-parallelism 8` 或更高
  - 调 `--page-size 10000`
  - 大表用 `truncate+insert` 或 `merge` 代替 `replace`
  - 检查源端是否需要索引（如 `WHERE updated_at > ...`）
  - 避免网络跨 region

### 内存爆

- **原因**：源端一次性返回太多行，没分批
- **解决**：
  - 调小 `--page-size`
  - 用 `--interval-start` / `--interval-end` 分片
  - 用 `--sql-limit` 限制（debug 时）

## 增量类

### `UNIQUE constraint failed: ...` 或目标表行数爆炸

- **症状**：append / merge 跑完报 `UNIQUE constraint failed`，或者目标表出现大量重复行
- **原因**：ingestr **不**自动从 dest 算 `max(incremental_key)`。你不传 `--interval-start/end` 时，源会全表扫描 + 全量写
- **解决**：
  - **必须**显式传 `--interval-start` 和 `--interval-end`（窗口格式 `YYYY-MM-DD HH:MM:SS` 或 ISO8601）
  - 想"全量"就跑 `interval-start="1970-01-01"` + `interval-end="2099-01-01"`
  - 看 `references/strategy_guide.md` 的"增量区间控制"章节

### 增量没生效（每次都全量）

- **症状**：用 append/merge 跑多次，目标表行数爆炸
- **检查项**：
  - 是不是忘了 `--incremental-key`（**label 必填**）
  - 是不是忘了 `--interval-start/end`（**窗口必填**，见上一条）
  - `incremental-key` 列在源表是否有索引
  - 源表该列是不是 NULL（NULL 不会被识别为增量）

### merge 把不该改的行改了

- **风险**：merge 命中 PK 就 UPDATE；没配 interval 时等于"全表 merge"
- **缓解**：
  - 显式配 `--interval-start/end` 限制更新时间窗口
  - 用 `delete+insert` 替代（按增量键删+插）

### delete+insert 把数据删没了

- **症状**：源表删了一行，目标表对应行也消失
- **原因**：这是 delete+insert 的设计行为 — 它会删目标表里 `incremental-key` 命中的行
- **缓解**：
  - 改用 `append`（保留历史）
  - 或改用 `merge`（按 PK 保留）

## URI 类

### Windows 路径报错

- **原因**：文件型 URI 走 `url.Parse` 会把 `C:\` 误识别为 URL
- **解决**：用正斜杠 `C:/path/to/file.csv` 或相对路径 `./file.csv`

### URI 含特殊字符

- **密码含 `@` / `:` / `?`**：URL encode
  - `@` → `%40`
  - `:` → `%3A`
  - `?` → `%3F`

```bash
--source-uri "postgres://user:p%40ss%3Aword@host/db"
```

## 安装类

### `ingestr: command not found`

- **解决**：
  - pip：`pip install ingestr`
  - 二进制：参考 `scripts/ingestr.sh` 自动找/装
  - brew：`brew install ingestr`

### 第一次跑下载 ADBC 驱动慢

- **原因**：`pkg/source/adbc` 用 `dbc` 客户端下载驱动
- **解决**：耐心等一次，后续会缓存

## 调试技巧

### 1. 用 `--debug` 看到所有 SQL

```bash
ingestr ingest --debug --source-uri ... --dest-uri ... --yes 2>&1 | head -200
```

### 2. 用 `--sql-limit 100` 试跑

```bash
ingestr ingest --sql-limit 100 ... --yes
```

先验证连通性、schema、类型映射，再去掉 limit 跑全量。

### 3. 用 `--progress log` 在 CI 里跑

```bash
ingestr ingest --progress log ... --yes
```

避免 interactive 进度条卡 CI。

### 4. 用 `--keep-staging` 保留 staging 表

```bash
ingestr ingest --keep-staging --incremental-strategy merge ... --yes
```

跑完去目标库看 staging 表内容，验证转换逻辑。

### 5. 看 `PrintFailedQuery` 输出

main.go 里如果 ingest 失败，会自动打印最近执行的 SQL。这是定位源/目标 SQL 错误的金矿。

## 何时**不要**用 ingestr

| 场景 | 替代方案 |
|------|---------|
| 需要调度、依赖、retry | Airflow / Dagster / Prefect 包 ingestr |
| 需要 SQL 转换、建模 | dbt（ingestr 喂数据，dbt 建模） |
| 需要 lineage / catalog | Bruin 平台 / DataHub / OpenLineage |
| 需要 GUI 让非工程师配 | Airbyte / Fivetran |
| 实时流（毫秒级） | Kafka / Materialize / Flink（ingestr 是批/微批） |
| 反向 ETL 到 SaaS | Hightouch / Census（ingestr 部分 SaaS 仅做 source 不做 dest） |

## datasource CLI 排错

> `scripts/datasource.py`（`~/.local/bin/datasource` wrapper）的专属坑。底层走本机 MySQL `datahub.db_source`。

### `datasource add` 跑完"成功"但 `datasource list` 看不到新行

- **症状**：`datasource add ...` 命令 exit 0、无 Python traceback，但 `datasource list` 行数没变；`SELECT ... FROM db_source` 也没新行
- **原因**：复合命令在 wrapper 外 `set -a; . ~/workspaces/sqlremote/.env; set +a` → 然后 `datasource add ...` 时，**子 shell 的 stdout buffer 没 flush**就被 `exec` 吃掉了；加 `cd /tmp` + 末尾 `echo "EXIT=$?"` 强制 flush 就正常输出 `✅ 已添加：xxx (id=N)`
- **排查**（不要瞎重试）：直接查 MySQL 兜底 —— `mysql -uroot datahub -e "SELECT id, source_code FROM db_source WHERE source_code='XXX';"`
- **解决**：
  - 跑 add 时**单独一句**、尾部加 `echo "EXIT=$?"`，强制 buffer flush
  - 落库验证**永远查 MySQL**，不只看 CLI 输出
- **教训**：工具 stdout 不等于数据落库；遵守 R14 原则 —— **用户观察 / 直接 SQL 兜底 > CLI 自报"成功"**

### shell 里 `---` 会被外层命令误解析

- **症状**：`mysql -uroot datahub -e "..."; echo "---"; datasource list` 报 `mysql: [ERROR] unknown option '---'.`
- **原因**：**整个复合命令是 `;` 串接，所有 argv 都进 mysql 的解析**，`---` 被当成表名/参数
- **解决**：用 `echo` 代替 `---` 做分隔，或者**分多个 execute_shell_command call 跑**
- **教训**（教训 #R20）：调试时输出分隔符**不要用 `---`**，用 `echo` 或 `printf '==\n'`；多个独立命令走**独立 shell call**而非 `;` 串

### `datasource add` 密码从 .env 传参模板

```bash
set -a; . ~/workspaces/sqlremote/.env; set +a
cd /tmp   # 切目录
datasource add \
  --code MYSQL_22_YIQI \
  --name "一期数据库" \
  --type mysql \
  --host 192.168.0.22 --port 3306 \
  --database yiqi --username "$yiqiuser" --password "$yikey" \
  --environment prod --status active
echo "EXIT=$?"
mysql -uroot datahub -e "SELECT id, source_code, host, port FROM db_source WHERE source_code='MYSQL_22_YIQI';"
```

- **约定**：密码不直接出现在命令行（不进 shell history）→ 写进 `~/workspaces/sqlremote/.env` (chmod 600)，用 `${ENV_VAR}` 引用
- **现有 .env 变量命名**：`<缩写>user` / `<缩写>key`（小写、无下划线），如 `msuser`/`mskey`、`yiqiuser`/`yikey`

## 报告 bug

去 https://github.com/bruin-data/ingestr/issues，附：
- ingestr 版本（`ingestr --version`）
- 完整命令（去掉敏感信息）
- 完整错误输出（加 `--debug`）
- 源/目标类型
