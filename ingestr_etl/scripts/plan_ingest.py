#!/usr/bin/env python3
"""plan_ingest.py - 从结构化输入生成 ingestr 命令

不是 LLM，是个 deterministic 的"模板引擎"——给清楚的信息就能拼出可执行命令。

支持两种输入：

  1) 命令行参数（最常见）：
     scripts/plan_ingest.py \
         --source-uri "postgres://..." \
         --source-table "public.users" \
         --dest-uri "bigquery://..." \
         --dest-table "raw.users" \
         --strategy append \
         --incremental-key updated_at

  2) JSON（编程用）：
     echo '{"source_uri": "...", "source_table": "...", "dest_uri": "...", ...}' | \\
         scripts/plan_ingest.py --from-json -

策略选择：
  - 显式 --strategy 优先
  - 没给策略：默认 replace
  - 给了 --incremental-key 但没给策略：自动选 append（最安全的"我只是增量同步"语义）

输出：
  - 默认：打印可粘贴到 shell 的命令
  - --exec：直接调 ingestr 执行（需要 binaries 已安装）
  - --dry：打印而不执行
"""
from __future__ import annotations

import argparse
import json
import shlex
import sys
from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class Plan:
    source_uri: str
    dest_uri: str
    source_table: str = ""
    dest_table: str = ""
    strategy: str = ""  # 空 = 让 plan 决定
    incremental_key: str = ""
    primary_key: list[str] = field(default_factory=list)
    interval_start: str = ""
    interval_end: str = ""
    partition_by: str = ""
    cluster_by: list[str] = field(default_factory=list)
    schema_contract: str = ""
    schema_naming: str = ""
    full_refresh: bool = False
    extract_parallelism: int = 0
    page_size: int = 0
    yes: bool = True
    debug: bool = False
    progress: str = ""
    mask: list[str] = field(default_factory=list)
    columns: str = ""

    def needs_primary_key(self) -> bool:
        return self.strategy in ("merge", "scd2")

    def auto_pick_strategy(self) -> str:
        if self.strategy:
            return self.strategy
        if self.incremental_key:
            return "append"
        return "replace"

    def validate(self) -> list[str]:
        errs: list[str] = []
        if not self.source_uri:
            errs.append("--source-uri 必填")
        if not self.dest_uri:
            errs.append("--dest-uri 必填")
        if not self.source_table:
            errs.append("--source-table 必填（没有显式指定时可用 'query:SELECT ...'）")
        strategy = self.auto_pick_strategy()
        if strategy not in {"replace", "truncate+insert", "append", "delete+insert", "merge", "scd2", "none"}:
            errs.append(f"未知 strategy：{strategy}")
        if self.needs_primary_key() and not self.primary_key:
            errs.append(f"strategy={strategy} 需要 --primary-key")
        return errs

    def to_command(self) -> list[str]:
        strategy = self.auto_pick_strategy()
        cmd = ["ingestr", "ingest"]
        cmd += ["--source-uri", self.source_uri]
        cmd += ["--dest-uri", self.dest_uri]
        if self.source_table:
            cmd += ["--source-table", self.source_table]
        if self.dest_table:
            cmd += ["--dest-table", self.dest_table]
        if strategy and strategy != "replace":
            cmd += ["--incremental-strategy", strategy]
        if self.incremental_key:
            cmd += ["--incremental-key", self.incremental_key]
        for pk in self.primary_key:
            cmd += ["--primary-key", pk]
        if self.interval_start:
            cmd += ["--interval-start", self.interval_start]
        if self.interval_end:
            cmd += ["--interval-end", self.interval_end]
        if self.partition_by:
            cmd += ["--partition-by", self.partition_by]
        for c in self.cluster_by:
            cmd += ["--cluster-by", c]
        if self.schema_contract:
            cmd += ["--schema-contract", self.schema_contract]
        if self.schema_naming:
            cmd += ["--schema-naming", self.schema_naming]
        if self.full_refresh:
            cmd += ["--full-refresh"]
        if self.extract_parallelism:
            cmd += ["--extract-parallelism", str(self.extract_parallelism)]
        if self.page_size:
            cmd += ["--page-size", str(self.page_size)]
        if self.progress:
            cmd += ["--progress", self.progress]
        if self.debug:
            cmd += ["--debug"]
        if self.columns:
            cmd += ["--columns", self.columns]
        for m in self.mask:
            cmd += ["--mask", m]
        if self.yes:
            cmd += ["--yes"]
        return cmd

    def to_shell(self) -> str:
        return " ".join(shlex.quote(p) for p in self.to_command())


def from_json(d: dict[str, Any]) -> Plan:
    # 接受 camelCase 也接受 snake_case
    def g(*keys: str, default: Any = None) -> Any:
        for k in keys:
            if k in d:
                return d[k]
        return default

    def gstr(*keys: str) -> str:
        for k in keys:
            if k in d and d[k] is not None:
                return d[k]
        return ""

    def glist(*keys: str) -> list:
        for k in keys:
            if k in d and d[k] is not None:
                v = d[k]
                if isinstance(v, list):
                    return list(v)
                if isinstance(v, str):
                    return [v]
                return list(v)
        return []

    def gbool(*keys: str, default: bool = False) -> bool:
        for k in keys:
            if k in d and d[k] is not None:
                return bool(d[k])
        return default

    def gint(*keys: str, default: int = 0) -> int:
        for k in keys:
            if k in d and d[k] is not None:
                try:
                    return int(d[k])
                except (TypeError, ValueError):
                    return default
        return default

    return Plan(
        source_uri=gstr("source_uri", "sourceUri"),
        dest_uri=gstr("dest_uri", "destUri"),
        source_table=gstr("source_table", "sourceTable"),
        dest_table=gstr("dest_table", "destTable"),
        strategy=gstr("strategy"),
        incremental_key=gstr("incremental_key", "incrementalKey"),
        primary_key=glist("primary_key", "primaryKey"),
        interval_start=gstr("interval_start", "intervalStart"),
        interval_end=gstr("interval_end", "intervalEnd"),
        partition_by=gstr("partition_by", "partitionBy"),
        cluster_by=glist("cluster_by", "clusterBy"),
        schema_contract=gstr("schema_contract", "schemaContract"),
        schema_naming=gstr("schema_naming", "schemaNaming"),
        full_refresh=gbool("full_refresh", "fullRefresh"),
        extract_parallelism=gint("extract_parallelism", "extractParallelism"),
        page_size=gint("page_size", "pageSize"),
        yes=gbool("yes", default=True),
        debug=gbool("debug"),
        progress=gstr("progress"),
        mask=glist("mask"),
        columns=gstr("columns"),
    )


def from_args(args: argparse.Namespace) -> Plan:
    return Plan(
        source_uri=args.source_uri or "",
        dest_uri=args.dest_uri or "",
        source_table=args.source_table or "",
        dest_table=args.dest_table or "",
        strategy=args.strategy or "",
        incremental_key=args.incremental_key or "",
        primary_key=list(args.primary_key or []),
        interval_start=args.interval_start or "",
        interval_end=args.interval_end or "",
        partition_by=args.partition_by or "",
        cluster_by=list(args.cluster_by or []),
        schema_contract=args.schema_contract or "",
        schema_naming=args.schema_naming or "",
        full_refresh=bool(args.full_refresh),
        extract_parallelism=int(args.extract_parallelism or 0),
        page_size=int(args.page_size or 0),
        yes=not args.no_yes,
        debug=bool(args.debug),
        progress=args.progress or "",
        mask=list(args.mask or []),
        columns=args.columns or "",
    )


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="生成（可选执行）ingestr ingest 命令"
    )
    src = p.add_argument_group("source")
    src.add_argument("--source-uri")
    src.add_argument("--source-table")

    dst = p.add_argument_group("destination")
    dst.add_argument("--dest-uri")
    dst.add_argument("--dest-table")

    inc = p.add_argument_group("incremental")
    inc.add_argument("--strategy", "--incremental-strategy",
                     help="replace/truncate+insert/append/delete+insert/merge/scd2/none")
    inc.add_argument("--incremental-key")
    inc.add_argument("--primary-key", action="append", default=[])
    inc.add_argument("--interval-start")
    inc.add_argument("--interval-end")

    tbl = p.add_argument_group("table structure")
    tbl.add_argument("--partition-by")
    tbl.add_argument("--cluster-by", action="append", default=[])
    tbl.add_argument("--schema-contract")
    tbl.add_argument("--schema-naming")

    perf = p.add_argument_group("performance")
    perf.add_argument("--extract-parallelism", type=int, default=0)
    perf.add_argument("--page-size", type=int, default=0)
    perf.add_argument("--progress")

    data = p.add_argument_group("data handling")
    data.add_argument("--mask", action="append", default=[])
    data.add_argument("--columns")

    flags = p.add_argument_group("flags")
    flags.add_argument("--full-refresh", action="store_true")
    flags.add_argument("--debug", action="store_true")
    flags.add_argument("--no-yes", action="store_true", help="保留交互确认（默认自动 --yes）")

    io = p.add_argument_group("io")
    io.add_argument("--from-json", help="从 JSON 文件或 '-' (stdin) 读 plan")
    io.add_argument("--exec", action="store_true", help="直接执行（需要 ingestr 在 PATH）")
    io.add_argument("--dry", action="store_true", help="只打印命令，不执行（默认）")
    return p


def main(argv: list[str]) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.from_json:
        if args.from_json == "-":
            d = json.load(sys.stdin)
        else:
            with open(args.from_json, "r", encoding="utf-8") as f:
                d = json.load(f)
        plan = from_json(d)
    else:
        plan = from_args(args)

    errs = plan.validate()
    if errs:
        for e in errs:
            print(f"ERROR  {e}", file=sys.stderr)
        return 2

    cmd_str = plan.to_shell()
    print(cmd_str)

    if args.exec:
        import subprocess
        rc = subprocess.call(plan.to_command())
        return rc
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
