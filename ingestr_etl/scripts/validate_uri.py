#!/usr/bin/env python3
"""validate_uri.py - 校验 ingestr URI 格式

不是连接测试（那需要真的去 ping），是语法/结构校验 + scheme 白名单检查。

用法：
    scripts/validate_uri.py "postgres://u:p@h:5432/db?sslmode=disable"
    scripts/validate_uri.py --scheme postgres "postgresql://u:p@h/db"
    echo "postgres://..." | scripts/validate_uri.py -

退出码：
    0 = 通过
    1 = 校验失败
    2 = 用法错误
"""
from __future__ import annotations

import argparse
import re
import sys
from typing import Iterable
from urllib.parse import urlsplit, unquote

# 完整白名单（来自 docs/commands/example-uris.md + 源码 pkg/source/*/register.go 抽样）
SUPPORTED_SCHEMES: set[str] = {
    # 数据库
    "postgres", "postgresql", "mysql", "mssql", "sqlserver",
    "sqlite", "duckdb", "motherduck", "md",
    "snowflake", "bigquery", "redshift", "athena",
    "clickhouse", "databricks", "mongodb",
    "trino", "oracle", "cratedb", "cassandra", "dynamodb",
    "elasticsearch", "influxdb", "hana", "db2",
    "kafka", "couchbase", "spanner", "synapse",
    "fabric", "onelake", "maxcompute", "avatica", "azuresql",
    # 文件型
    "csv", "parquet", "jsonl", "ndjson", "json", "avro", "mmap",
    # 对象存储
    "s3", "gcs", "gs", "abfs", "abfss", "azure", "adls",
    # SaaS（仅 source）
    "stripe", "hubspot", "salesforce", "notion", "slack", "shopify",
    "github", "jira", "linear", "asana", "mixpanel", "mailchimp",
    "klaviyo", "facebook_ads", "google_ads", "tiktok_ads",
    "linkedin_ads", "anthropic", "adjust", "appsflyer", "intercom",
    "zendesk", "docebo", "fireflies", "gorgias", "clickup", "hostaway",
    "personio", "pinterest", "pipedrive", "posthog", "quickbooks",
    "smartsheet", "snapchat_ads", "surveymonkey", "trustpilot", "zoom",
    "chess", "cursor", "dune", "freshdesk", "fundraiseup", "g2",
    "granola", "indeed", "isoc_pulse", "jobtread", "monday",
    "phantombuster", "plusvibeai", "primer", "revenuecat", "sftp",
    "solidgate", "allium", "apple_ads", "applovin", "attio",
    "bruin", "customerio", "frankfurter", "appstore",
    # 自定义 SQL 前缀走源表名而非 URI
}

# 归一化映射（来自 internal/uri/parser.go::NormalizeScheme）
NORMALIZE: dict[str, str] = {
    "postgresql": "postgres",
    "postgresql+psycopg2": "postgres",
    "postgresql+asyncpg": "postgres",
    "pg": "postgres",
    "redshift+psycopg2": "redshift",
    "azure-sql": "azuresql",
    "gs": "gcs",
    "ndjson": "jsonl",
    "md": "motherduck",
}

# 文件型 scheme：跳过 url 解析（来自 internal/uri/parser.go::fileBasedSchemes）
FILE_SCHEMES: set[str] = {
    "jsonl", "ndjson", "json", "csv", "parquet", "avro",
    "sqlite", "duckdb", "motherduck", "md", "mmap",
}

SCHEME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+._-]*$")


def normalize(scheme: str) -> str:
    return NORMALIZE.get(scheme, scheme)


def check(uri: str) -> list[str]:
    """返回错误列表（空列表 = 通过）。"""
    errors: list[str] = []

    if not uri or not uri.strip():
        return ["URI 为空"]

    if "://" not in uri:
        errors.append(f"缺少 '://' 分隔符：{uri!r}")
        return errors

    scheme, rest = uri.split("://", 1)
    scheme_lower = scheme.lower()

    if not SCHEME_RE.match(scheme_lower):
        errors.append(f"scheme 不合法：{scheme!r}")

    canonical = normalize(scheme_lower)
    if canonical not in SUPPORTED_SCHEMES and scheme_lower not in SUPPORTED_SCHEMES:
        errors.append(
            f"不支持的 scheme：{scheme!r}（归一化为 {canonical!r}）。"
            f" 参考 docs/commands/example-uris.md"
        )

    # 文件型：检查路径存在 / 形如 ///path
    if scheme_lower in FILE_SCHEMES:
        if not rest:
            errors.append(f"文件型 scheme {scheme!r} 需要路径")
        # 接受 /abs/path 或 relative/path
        return errors

    # 网络型：用 urlsplit 检查结构
    try:
        parts = urlsplit(uri)
    except Exception as e:  # pragma: no cover
        errors.append(f"urlsplit 失败：{e}")
        return errors

    # host 检查（除 file 之外）
    if not parts.hostname and not parts.path.lstrip("/"):
        errors.append("缺少 host（网络型 URI 应是 scheme://host/...）")

    # port 检查
    if parts.port is not None and not (0 < parts.port < 65536):
        errors.append(f"port 越界：{parts.port}")

    return errors


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="校验 ingestr URI 格式"
    )
    parser.add_argument("uri", help="要校验的 URI（用 - 表示从 stdin 读）")
    parser.add_argument(
        "--scheme",
        action="append",
        help="额外允许的 scheme（自定义）",
    )
    parser.add_argument(
        "--quiet", "-q", action="store_true", help="只打印 URI/错误"
    )
    args = parser.parse_args(argv)

    if args.scheme:
        SUPPORTED_SCHEMES.update(s.lower() for s in args.scheme)

    uris: list[str]
    if args.uri == "-":
        uris = [line.strip() for line in sys.stdin if line.strip()]
    else:
        uris = [args.uri]

    rc = 0
    for uri in uris:
        errs = check(uri)
        if errs:
            rc = 1
            for e in errs:
                print(f"FAIL  {uri}\n      {e}", file=sys.stderr)
        else:
            if not args.quiet:
                scheme = uri.split("://", 1)[0].lower()
                canonical = normalize(scheme)
                marker = f"  (-> {canonical})" if canonical != scheme else ""
                print(f"OK    {uri}{marker}")
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
