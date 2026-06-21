# ingestr URI 格式速查

> 完整支持列表见 `docs/commands/example-uris.md` 和官方文档。
> 通用语法：`<scheme>://<user>:<pass>@<host>:<port>/<database>?<query_params>`

## 数据库

| 用途 | Scheme | URI 示例 |
|------|--------|---------|
| Postgres 源/目标 | `postgres` (也接受 `postgresql`, `postgresql+psycopg2`, `pg`) | `postgres://user:pass@host:5432/db?sslmode=disable` |
| MySQL | `mysql` (也接受 `mysql+pymysql`, `mariadb`) | `mysql://user:pass@host:3306/db` |
| SQL Server | `mssql` (也接受 `sqlserver`, `mssql+pyodbc`) | `mssql://user:pass@host:1433/db` |
| SQLite | `sqlite` (文件型) | `sqlite:///path/to/db.db` |
| DuckDB | `duckdb` (文件型) | `duckdb:///path/to/db.db` |
| MotherDuck | `motherduck` / `md` | `motherduck://db?motherduck_token=xxx` |
| Snowflake | `snowflake` | `snowflake://user:pass@account/db/schema?warehouse=WH&role=ROL` |
| BigQuery | `bigquery` | `bigquery://project/dataset?credentials_path=/path/sa.json` |
| Redshift | `redshift` | `redshift://user:pass@host:5439/db` |
| Athena | `athena` | `athena://?access_key=...&secret_key=...&region=us-east-1&s3_staging_dir=s3://...&database=default` |
| ClickHouse | `clickhouse` | `clickhouse://user:pass@host:8123/db` |
| Databricks | `databricks` | `databricks://token@host:443/sql/1.0/warehouses/xxx` |
| MongoDB | `mongodb` | `mongodb://user:pass@host:27017/db` (也接受 `mongodb+srv://`) |
| Trino | `trino` | `trino://user@host:8080/catalog/schema` |
| Oracle | `oracle` | `oracle://user:pass@host:1521/service` |
| CrateDB | `cratedb` | `cratedb://user:pass@host:4200/db` |
| Cassandra | `cassandra` | `cassandra://user:pass@host:9042/keyspace` |
| DynamoDB | `dynamodb` | `dynamodb://?region=us-east-1&aws_access_key_id=...&aws_secret_access_key=...` |
| Elasticsearch | `elasticsearch` | `elasticsearch://user:pass@host:9200` |
| InfluxDB | `influxdb` | `influxdb://user:pass@host:8086/db` |
| SAP Hana | `hana` | `hana://user:pass@host:39017/db` |
| IBM Db2 | `db2` | `db2://user:pass@host:50000/db` |
| Kafka | `kafka` | `kafka://host:9092/topic` |
| Couchbase | `couchbase` | `couchbase://user:pass@host:11210/bucket` |
| GCP Spanner | `spanner` | `spanner://project/instance/db` |

## SaaS 平台（仅 source）

Stripe、HubSpot、Salesforce、Notion、Slack、Shopify、GitHub、Jira、Linear、Asana、Mixpanel、Mailchimp、Klaviyo、Reddit Ads、Facebook Ads、Google Ads、TikTok Ads、LinkedIn Ads、Anthropic、Adjust、AppsFlyer、Intercom、Zendesk、Docebo、Fireflies、Gorgias、ClickUp、Hostaway、Personio、Pinterest、Pipedrive、PostHog、QuickBooks、Smartsheet、Snapchat Ads、SurveyMonkey、Trustpilot、Zoom、Airwallex、Allium、Anthropic、Apple Ads、AppLovin、Asana、Attio、Bruin、Chess.com、Cursor、Customer.io、Dune、Frankfurter、Freshdesk、FundraiseUp、G2、Granola、Indeed、ISOC Pulse、JobTread、Monday、PhantomBuster、Plus Vibe AI、Primer、RevenueCat、SFTP、Solidgate、Stripe、Substack、TimeTaco、Whatagraph、Wise 等。

## 文件型

| Scheme | URI | 用途 |
|--------|-----|------|
| `csv` | `csv:///path/to/file.csv` | 本地 CSV |
| `parquet` | `parquet:///path/to/file.parquet` | 本地 Parquet |
| `jsonl` / `ndjson` | `jsonl:///path/to/file.jsonl` | 本地 JSON Lines |
| `json` | `json:///path/to/file.json` | 本地 JSON |
| `avro` | `avro:///path/to/file.avro` | 本地 Avro |
| `mmap` | `mmap:///path/to/memmap` | mmap 数据 |

## 对象存储

| 用途 | URI |
|------|-----|
| S3 | `s3://bucket/path?region=us-east-1&access_key=...&secret_key=...` |
| GCS | `gcs://bucket/path?credentials_path=/path/sa.json` |
| Azure Data Lake | `abfs://container/path?account_name=...&account_key=...` |
| ADLS Gen2 | `abfss://container/path?account_name=...&account_key=...` |

## URI 归一化（不用记，工具自动处理）

`internal/uri/parser.go::NormalizeScheme`：

- `postgresql` / `postgresql+psycopg2` / `postgresql+asyncpg` / `pg` → `postgres`
- `redshift+psycopg2` → `redshift`
- `azure-sql` → `azuresql`

## 自定义 SQL（query: 前缀）

```bash
--source-table "query:SELECT id, name, created_at FROM users WHERE active = true"
```

`pkg/source.IsCustomQuery` 识别 `query:` 前缀，走自定义查询路径。

## CDC 模式

Postgres CDC 走 logical replication，ingestr 自动派生 dest-aware slot 后缀（`isCDCSource`）。Resume LSN 自动从目标表状态推断。

## 常用 query 参数

| 参数 | 适用 | 用途 |
|------|------|------|
| `sslmode=disable` | postgres | 关 SSL |
| `credentials_path=...` | bigquery/gcs | GCP service account JSON 路径 |
| `region=...` | s3/athena/dynamodb | AWS 区域 |
| `access_key` / `secret_key` | s3/athena | AWS 凭证（生产建议用 IAM role） |
| `warehouse=` | snowflake | 仓库名 |
| `role=` | snowflake | 角色名 |
| `s3_staging_dir=` | athena | Athena 查询结果落盘 S3 |
