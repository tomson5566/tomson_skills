# Ingestr 5 大典型 Recipe（来自官方文档）

> **本文件是 v3 新增**。基于官方 `tutorials/` + 多个 source 页面精炼。
> 完整材料：`skills/dot-skill/skills/colleague/ingestr/knowledge/documentation_study/parsed/tutorials_*.md`

每个 recipe 包含：**场景**、**完整命令**、**为什么这样选**、**踩坑提醒**。

---

## Recipe 1: Stripe 增量同步到 BigQuery（merge 策略）

### 场景
订阅服务，把 Stripe `customer` 表增量同步到 BigQuery 用于客户分析。

### 命令
```bash
ingestr ingest \
  --source-uri 'stripe://?api_key=sk_live_xxx' \
  --source-table 'customer' \
  --dest-uri 'bigquery://my-proj?credentials_path=/svc.json&location=EU' \
  --dest-table 'raw.stripe_customers' \
  --incremental-key 'created' \
  --incremental-strategy 'merge' \
  --primary-key 'id'
```

### 为什么
- `merge` 而不是 `append`：不要历史版本，只要最新状态
- `primary-key id`：Stripe 客户唯一标识
- `incremental-key created`：v0 默认全量，**v1 默认 30 天窗口**（注意 `migrations.md`）
- **首次跑必须加 `--full-refresh`**（v1 行为变更）

### 踩坑
- ⚠️ **v1 首次跑**：加 `--full-refresh`，否则目标表不会有全量历史
- BigQuery 需额外 IAM 角色：`roles/bigquery.readSessionUser`
- 要快速 subset：加 `--interval-start 2024-01-01 --interval-end 2024-12-31`
- 要做 SCD2：改 `--incremental-strategy 'scd2'`（v1 新增）

### 变体
```bash
# 拉 subscriptions（带增量策略后缀）
--source-table 'subscriptions:sync:incremental'
--interval-start '2024-01-01'
--interval-end '2024-01-31'

# 拉 events（不走 events-based，始终全量）
--source-table 'event'
```

---

## Recipe 2: Postgres → Postgres 按天窗口同步（delete+insert）

### 场景
数仓内部 ETL，把 OLTP 库 `orders` 表按天同步到 ODS 层。

### 命令
```bash
ingestr ingest \
  --source-uri 'postgresql://user:pass@oltp-host:5432/shop' \
  --source-table 'public.orders' \
  --dest-uri 'postgresql://user:pass@warehouse:5432/ods' \
  --dest-table 'warehouse.orders' \
  --incremental-key 'updated_at' \
  --incremental-strategy 'delete+insert' \
  --interval-start "$(date -d 'yesterday' +%F)" \
  --interval-end "$(date +%F)"
```

### 为什么
- `delete+insert`：目标表干净，相同 `updated_at` 的旧行被替换
- 按天窗口：cron 调度时只重跑昨天的数据，重跑不重
- `interval-start/end`：v1 不会自动算 `max(target.incremental_key)`，**必须显式给**（参见 `internals.md` 的源码注释）

### 踩坑
- ⚠️ `delete+insert` **不保证顺序**、**不按 PK 去重**，会重复
- 想按 PK 去重：换 `merge` + `primary-key`
- 想保留历史：换 `append`
- 如果没有 `updated_at` 列：考虑 `custom_queries`（Recipe 3）

### 调度包装（cron）
```bash
# /etc/cron.d/ingestr-orders
0 2 * * *  user  bash -c 'ingestr ingest ... --interval-start $(date -d yesterday +%F) --interval-end $(date +%F)' >> /var/log/ingestr.log 2>&1
```

---

## Recipe 3: 自定义 SQL 增量（query: 前缀）

### 场景
源表没有干净的 `updated_at`，需要 join 另一张表拿增量键。

### 命令
```bash
ingestr ingest \
  --source-uri 'postgresql://user:pass@host:5432/shop' \
  --source-table "query:select oi.*, o.updated_at
                  from order_items oi
                  join orders o on oi.order_id = o.id
                  where o.updated_at > :interval_start" \
  --dest-uri 'bigquery://my-proj?credentials_path=/svc.json' \
  --dest-table 'raw.order_items_enriched' \
  --incremental-key 'updated_at' \
  --incremental-strategy 'merge' \
  --primary-key 'id'
```

### 为什么
- `query:` 前缀跑任意 SQL（SQLAlchemy 语法）
- `:interval_start` / `:interval_end` 是占位符，v1 自动绑定
- 与增量策略无缝配合

### 踩坑
- ⚠️ **标记为 experimental**（DANGER 警示框）
- 增量键必须在 SELECT 结果里
- 增量键必须是 datetime/timestamp
- SQL 里的过滤要自己写（占位符不自动加 WHERE）
- **不限于 Postgres**：所有 SQL 源都支持（MySQL / Snowflake / BigQuery / ...）

### 变体：按日期范围
```bash
--source-table "query:select * from events
                where created_at >= :interval_start
                and created_at < :interval_end"
```

---

## Recipe 4: S3 文件一次性落 DuckDB（探索场景）

### 场景
拿到一个 S3 bucket 的 Parquet 文件，想快速用 SQL 探索结构。

### 命令
```bash
ingestr ingest \
  --source-uri 's3://?access_key_id=AKIA...&secret_access_key=...&region=us-east-1' \
  --source-table 'my-bucket/data/**/*.parquet' \
  --dest-uri 'duckdb:///local.duckdb' \
  --dest-table 'raw.data'
```

### 验证
```bash
duckdb local.duckdb "select * from raw.data limit 10"
# 或
duckdb -ui local.duckdb
```

### 为什么
- DuckDB 零配置、列式、本地文件 → 探索最快
- S3 支持 glob / 压缩 / 类型 hint / 编码 hint
- 无增量 = 全量覆盖（适合一次性）

### 踩坑
- 第一次跑要等（glob 列出 + 下载 + 转 Arrow + 落 DuckDB）
- 大桶（百万级对象）：用 `file_discovery=athena_inventory` 加速
- 文件类型不对：用 `#format` hint（`#csv` / `#jsonl` / `#parquet` / `#csv_headless`）
- 编码乱码：用 `#encoding=windows-1252` hint
- 压缩文件：`.gz` 自动检测

### 变体：JSONL 增量（按文件修改时间）
```bash
--source-table 'my-bucket/logs/**/*.jsonl' \
--incremental-key '_ingestr_source_file_modified_at' \
--incremental-strategy 'append' \
--interval-start '2026-01-01T00:00:00Z'
```

### 变体：S3 兼容（MinIO / R2 / Spaces）
```bash
--source-uri 's3://?endpoint_url=http://localhost:9000&access_key_id=...&secret_access_key=...'
```

---

## Recipe 5: 列脱敏（合规场景）

### 场景
把 PII 数据搬到沙箱库用于分析，需要脱敏 email / phone / ssn / salary。

### 命令
```bash
ingestr ingest \
  --source-uri 'postgresql://user:pass@host:5432/customers' \
  --source-table 'customer_data' \
  --dest-uri 'duckdb:///masked_customers.db' \
  --dest-table 'masked_customers' \
  --mask 'email:hash' \
  --mask 'phone:partial:3' \
  --mask 'ssn:redact' \
  --mask 'salary:round:5000'
```

### 4 种 mask 算法
| 算法 | 行为 | 例 |
|---|---|---|
| `hash` | 一致性哈希（同一原文 → 同一 hash） | `john@example.com` → `a1b2c3d4...` |
| `partial:N` | 只保留前 N + 后 N 字符 | `555-123-4567` (N=3) → `555-***-4567` |
| `redact` | 完全屏蔽 | `123-45-6789` → `***` |
| `round:N` | 四舍五入到 N | `125000` (N=5000) → `125000`（已对齐） |
| `nullify` | 设为 NULL | `john@example.com` → `NULL` |

### 踩坑
- ⚠️ `--mask` 在源端应用（不是目的地端）
- 多次 `--mask` 累加（同一列多次 = 多次脱敏，但通常只 1 次）
- `hash` 算法对相同原文产生相同结果 → **可分析但不可逆**
- 配合 `--primary-key` 用 `merge` 策略：脱敏后 upsert 不会冲突
- 不脱敏想看 raw：去掉 `--mask` flag

### 变体：仅裁剪列 + 重命名
```bash
--columns 'id::user_id,email,phone,created_at:timestamp'
# 格式：name:type:source 或 name::source（重命名）或 name:type（重写类型）
```

---

## Recipe 6: SQL Server 2012 → MySQL 8 单表全量迁移（实战案例）

> 🛠️ **来源**: 2026-06-08 真实任务，从 MSSQL 133.14 的 `HR.HR_Archive` (789 行, 14 列) 迁移到 MySQL 188 的 `hr.hr_archive`。**包含 2 个官方文档没写的坑**。

### 场景
- 源：**SQL Server 2012 RTM**（仅支持 TLS 1.0，TLS 1.2 握手会失败）
- 目标：**MySQL 8.4**，启用了 `lower_case_table_names=1`（Linux 默认行为，强制表名小写）
- 表：14 列混合类型（`int` / `varchar` / `datetime` / `nvarchar`），主键 `ArchiveId`
- 规模：小（789 行）— 用默认 `replace` 策略全量重建最简单

### 命令
```bash
ingestr ingest \
  --source-uri 'mssql://sa:rootkit_99852@192.168.133.14:1433/HR?encrypt=true&trustservercertificate=true&tlsmin=1.0' \
  --dest-uri 'mysql://tmsj:Tmsj%408888@192.168.0.188:3308/hr' \
  --source-table HR_Archive \
  --dest-table HR_Archive \
  --schema-naming direct \
  --progress log \
  --yes
```

### 为什么
- `replace` 策略：默认全量重建，789 行小表不需要增量
- `--progress log`：避免 interactive 进度条卡住 CI / agent
- `--yes`：跳过交互确认（脚本必备）
- 不加 `--incremental-key`：小表全量更直接
- 不加 `--primary-key`：replace 策略下不需要（仅 merge 需要）

### 踩坑（3 个真实坑，2 个不显然）

#### ⚠️ 坑 1：MSSQL 2012 RTM + ingestr 的 TLS 1.0 不兼容
**症状**: `Error: failed to connect to source: failed to ping SQL Server: TLS Handshake failed: tls: server selected unsupported protocol version 301`

**根因**:
- SQL Server 2012 RTM 仅支持 TLS 1.0（要到 SP4 才支持 TLS 1.2）
- Go runtime（ingestr 用的）默认最低 TLS 1.2 → 握手失败
- `mssql-legacy` skill 那个 `OPENSSL_CONF` 隔离方案**只对 sqlcmd / ODBC 有效**，ingestr 走 Go mssql driver（`denisenkom/go-mssqldb`）**不读 OpenSSL 配置**

**解法**: URI 加 `?tlsmin=1.0`（go-mssqldb DSN 参数）
```text
完整参数串：?encrypt=true&trustservercertificate=true&tlsmin=1.0
  ├─ encrypt=true                    强制 TLS 加密（SQL Server 默认会要求）
  ├─ trustservercertificate=true     信任自签证书（SQL Server 2012 默认自签）
  └─ tlsmin=1.0                      允许 TLS 1.0（绕过 Go 默认 TLS 1.2 限制）
```

**未来 MSSQL 2012 RTM 任务必加这三个参数**（升级到 SP4 后可去掉 `tlsmin=1.0`）。

#### ⚠️ 坑 2：`snake_case` 列名转换在 MSSQL 端踩到列名引用错
**症状**: `Error: ingestion failed: failed to write data: failed to query: mssql: 列名 'warning_level' 无效。`

**根因**:
- ingestr 默认 `--schema-naming snake_case`，destination 表不存在时强制 snake_case
- 源 MSSQL 列名是驼峰（`WarningLevel`），ingestr 在某个 metadata 查询里把它转成 `warning_level` 后引用 → MSSQL 找不到这列
- 影响范围：所有 MSSQL 源 + 默认 snake_case 的组合

**解法**: 加 `--schema-naming direct` 保持源列名原样
```bash
--schema-naming direct
```

**副作用**: 目标 MySQL `lower_case_table_names=1` 时，驼峰列名最终存为小写**不带下划线**（`WarningLevel` → `warninglevel`），牺牲了可读性换"能跑通"。

**业务上需要 snake_case 列名怎么办**：
- 方案 A：目标 MySQL 改 `lower_case_table_names=0`（需删库重建，**破坏性**）
- 方案 B：post-ETL 跑 `ALTER TABLE ... RENAME COLUMN` 把 `warninglevel` 改回 `warning_level`
- 方案 C：容忍小写无下划线（如果只是内部 ETL，可接受）

#### 坑 3：密码含 `@` 必须 percent-encode
**症状**: 拼 URI 时如果直接写 `mysql://tmsj:Tmsj@8888@host`，shell 和 URI 解析器都会把 `@8888` 当作主机段

**解法**: `@` → `%40`，其他特殊字符同理
```text
原始密码:   Tmsj@8888
URI 编码:   Tmsj%408888
完整 URI:   mysql://tmsj:Tmsj%408888@192.168.0.188:3308/hr
```

**速查表**:
| 字符 | percent-encode |
|---|---|
| `@` | `%40` |
| `:` | `%3A` |
| `/` | `%2F` |
| `?` | `%3F` |
| `#` | `%23` |
| `%` | `%25` |

### 验证命令
```bash
# 源端行数（MSSQL）
MSSQL_SERVER=192.168.133.14 MSSQL_USER=sa MSSQL_PASSWORD=rootkit_99852 \
  mssql -d HR -C -Q "SELECT COUNT(*) AS src_count, COUNT(DISTINCT ArchiveId) AS src_distinct_pk FROM HR_Archive;"

# 目标行数（MySQL，注意小写表名）
mysql -h192.168.0.188 -P3308 -utmsj -p'Tmsj@8888' hr \
  -e "SELECT COUNT(*) AS dst_count, COUNT(DISTINCT ArchiveId) AS dst_distinct_pk FROM hr_archive;"

# 双向对比：src_count == dst_count, src_distinct_pk == dst_distinct_pk 即可
```

### 性能基线（参考）
- 789 行 + 14 列：4.9s 完成
- 吞吐：~162 rows/s
- 内存峰值：~114 MB

### 变体：先试跑（带 limit）
```bash
ingestr ingest ... --sql-limit 100 --debug --progress log --yes
# 看 staging 表是否建对、列名是否正确，再去掉 --sql-limit 跑全量
```

### 变体：迁移到 schema 名不同的目标
```bash
# 目标用 archive 库（与源库 HR 不同名）
ingestr ingest \
  --source-uri 'mssql://...' \
  --source-table HR.HR_Archive \
  --dest-uri 'mysql://tmsj:Tmsj%408888@192.168.0.188:3308/archive' \
  --dest-table HR_Archive \
  ...
```

---

## 通用 recipe 模板

### 模板 A：HTTP / API 源 → 数仓
```bash
ingestr ingest \
  --source-uri '<scheme>://?<creds>' \
  --source-table '<table>' \
  --dest-uri '<warehouse>://?<creds>' \
  --dest-table '<schema>.<table>' \
  --incremental-key '<timestamp_col>' \
  --incremental-strategy '<replace|append|merge|delete+insert>' \
  --primary-key '<pk>'   # 仅 merge
```

### 模板 B：文件 → 本地探索
```bash
ingestr ingest \
  --source-uri '<storage>://?<creds>' \
  --source-table '<bucket>/<glob>.<format>' \
  --dest-uri 'duckdb:///local.duckdb' \
  --dest-table 'raw.<table>'
```

### 模板 C：DB → DB 全量复制
```bash
ingestr ingest \
  --source-uri 'postgresql://...' \
  --source-table '<schema>.<table>' \
  --dest-uri 'postgresql://...' \
  --dest-table '<schema>.<table>'
# 默认 replace 策略，全量
```

### 模板 D：DB → DB 增量
```bash
ingestr ingest \
  --source-uri 'postgresql://...' \
  --source-table '<schema>.<table>' \
  --dest-uri 'bigquery://...' \
  --dest-table '<schema>.<table>' \
  --incremental-key 'updated_at' \
  --incremental-strategy 'delete+insert' \
  --interval-start '2024-01-01' \
  --interval-end '2024-01-31'
```

---

## Recipe 选择决策树

```
场景？
├── 一次性探索 → Recipe 4 (S3/DuckDB)
├── 增量同步
│   ├── 有自然 PK + 保留最新 → Recipe 1 (merge)
│   ├── 无 PK + 干净目标 + 回填 → Recipe 2 (delete+insert)
│   ├── join 出增量键 → Recipe 3 (custom query)
│   └── 历史版本需求 → 改 append
├── 合规/沙箱 → Recipe 5 (mask)
└── 跨 DB 类型单表全量（小表）
    ├── SQL Server 2012 → MySQL → Recipe 6 (含 TLS 1.0 兼容)
    └── 其他跨 DB 类型 → 模板 C（见下）
```

## 调试 recipe

每个 recipe 第一次跑前：
1. **dry run**：加 `--full-refresh` + 小 `--interval-start/end` 子集
2. **看 schema**：先用 `duckdb` 探索目标表结构
3. **看 row count**：源端 `select count(*)` 与目标端对比
4. **看历史**：用 `ingestr server` 跑 + 看 Run History + View Logs

### SQL Server 2012 特有检查点（Recipe 6 配套）
- [ ] URI 是否带 `encrypt=true&trustservercertificate=true&tlsmin=1.0`
- [ ] 列名是否踩 snake_case 转换 → 加 `--schema-naming direct`
- [ ] 密码是否 percent-encode（`@` → `%40`）
- [ ] 目标 MySQL 是否启用了 `lower_case_table_names=1`（决定表名/列名是否会被强制小写）
- [ ] 源/目标库都需存在（ingestr 不会自动 `CREATE DATABASE`）

## 相关 references
- `internals.md` — 7 策略的源码实现
- `strategy_guide.md` — 4 策略选型决策树
- `uri_catalog.md` — 70 源 URI 模板
- `migrations.md` — v1 默认行为变更
- `best_practices.md` — 通用 best practice（错误重试、幂等性）
