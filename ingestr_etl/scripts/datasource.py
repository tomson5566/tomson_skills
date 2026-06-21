#!/usr/bin/env python3
"""
datasource.py - 数据源管理 CLI
================================
基于本机 MySQL `datahub.db_source` 表，统一管理所有数据源连接信息。

子命令：
  list        列出所有数据源
  show        查看详情（含密码可选）
  add         新增数据源
  delete      删除（软删除：改 status=archived；加 --force 硬删）
  update      更新字段
  search      按关键字搜索
  status      改状态（active/inactive/archived/error）
  count       统计数量

环境变量覆盖：
  DATAHUB_HOST       本机 MySQL Host (默认 127.0.0.1)
  DATAHUB_PORT       Port (默认 3306)
  DATAHUB_USER       User (默认 root)
  DATAHUB_PASSWORD   Password (默认空)
  DATAHUB_DB         数据库名 (默认 datahub)
  DATAHUB_TABLE      表名 (默认 db_source)

示例：
  datasource list
  datasource list --type mysql --status active
  datasource show MSSQL_HR_133_14 --show-password
  datasource add --code XXX --name 'name' --type mysql --host 1.2.3.4 --port 3306 \
                 --database db --username root --password pwd --description '...'
  datasource delete MSSQL_HR_133_14 --force
  datasource search 'hr'
  datasource count --type sqlserver
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Optional

# ============================================================
# 默认连接配置（可通过环境变量覆盖）
# 本机 MySQL 默认走 Unix socket（/var/lib/mysql/mysql.sock），
# 因为 MySQL 配置禁用了 TCP（@@port=0）。
# 要走 TCP 时显式给 --host 1.2.3.4 或环境变量 DATAHUB_HOST
# ============================================================
DEFAULTS = {
    "host": os.environ.get("DATAHUB_HOST", ""),  # 空表示走 socket
    "port": int(os.environ.get("DATAHUB_PORT", "3306")),
    "user": os.environ.get("DATAHUB_USER", "root"),
    "password": os.environ.get("DATAHUB_PASSWORD", ""),
    "database": os.environ.get("DATAHUB_DB", "datahub"),
    "table": os.environ.get("DATAHUB_TABLE", "db_source"),
    "socket": os.environ.get("DATAHUB_SOCKET", "/var/lib/mysql/mysql.sock"),
}

DB_TYPES = [
    "mysql", "sqlserver", "postgresql", "oracle",
    "redis", "mongodb", "clickhouse", "doris", "kafka", "other",
]
ENV_VALUES = ["dev", "test", "staging", "prod", "unknown"]
STATUS_VALUES = ["active", "inactive", "archived", "error"]


def get_connection():
    """获取 pymysql 连接（默认走 Unix socket）"""
    try:
        import pymysql
    except ImportError:
        print("❌ 缺 pymysql，运行：pip install pymysql", file=sys.stderr)
        sys.exit(2)
    kwargs = dict(
        user=DEFAULTS["user"],
        password=DEFAULTS["password"],
        database=DEFAULTS["database"],
        charset="utf8mb4",
    )
    if DEFAULTS["host"]:
        kwargs["host"] = DEFAULTS["host"]
        kwargs["port"] = DEFAULTS["port"]
    else:
        # Unix socket 方式（pymysql 用 unix_socket）
        sock = DEFAULTS["socket"]
        if os.path.exists(sock):
            kwargs["unix_socket"] = sock
        else:
            # socket 不存在 → 尝试 TCP 回退
            kwargs["host"] = "127.0.0.1"
            kwargs["port"] = DEFAULTS["port"]
    return pymysql.connect(**kwargs)


def _table():
    return DEFAULTS["table"]


# ============================================================
# 子命令实现
# ============================================================

def cmd_list(args) -> int:
    """列出数据源"""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            sql = (
                f"SELECT id, source_code, source_name, db_type, host, port, "
                f"database_name, username, charset, environment, status, owner "
                f"FROM {_table()}"
            )
            conditions = []
            params = []
            if args.type:
                conditions.append("db_type = %s")
                params.append(args.type)
            if args.status:
                conditions.append("status = %s")
                params.append(args.status)
            if args.environment:
                conditions.append("environment = %s")
                params.append(args.environment)
            if conditions:
                sql += " WHERE " + " AND ".join(conditions)
            sql += " ORDER BY id"
            cur.execute(sql, params)
            rows = cur.fetchall()
            cols = [d[0] for d in cur.description]

            if args.json:
                out = [dict(zip(cols, row)) for row in rows]
                print(json.dumps(out, default=str, indent=2, ensure_ascii=False))
                return 0

            if not rows:
                print("(空)")
                return 0

            # 表格输出
            hdr = f"{'ID':<4} {'CODE':<30} {'NAME':<22} {'TYPE':<11} {'HOST:PORT':<24} {'DB':<14} {'USER':<12} {'ENV':<8} {'STATUS':<10}"
            print(hdr)
            print("-" * len(hdr))
            for r in rows:
                (rid, code, name, typ, host, port, db, user, charset, env, status, owner) = r
                hostport = f"{host}:{port}"
                print(
                    f"{rid:<4} {code:<30} {name[:20]:<22} {typ:<11} {hostport:<24} "
                    f"{(db or '-'):<14} {(user or '-'):<12} {env:<8} {status:<10}"
                )
            print(f"\n共 {len(rows)} 条")
    finally:
        conn.close()
    return 0


def cmd_show(args) -> int:
    """查看详情"""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT * FROM {_table()} WHERE source_code = %s",
                (args.code,),
            )
            row = cur.fetchone()
            if not row:
                print(f"❌ 未找到 source_code = {args.code}", file=sys.stderr)
                return 1
            cols = [d[0] for d in cur.description]
            data = dict(zip(cols, row))
            # 密码遮掩
            show_pwd = args.show_password
            for k, v in data.items():
                if k == "password" and not show_pwd:
                    v = "****(隐藏)"
                if v is None:
                    v = "NULL"
                print(f"{k:<22}: {v}")
    finally:
        conn.close()
    return 0


def cmd_add(args) -> int:
    """新增数据源"""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            sql = f"""INSERT INTO {_table()}
                (source_code, source_name, db_type, host, port,
                 database_name, username, password, charset,
                 environment, status, description, owner)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"""
            cur.execute(sql, (
                args.code, args.name, args.type, args.host, args.port,
                args.database, args.username, args.password,
                args.charset or "utf8mb4",
                args.environment or "unknown",
                args.status or "active",
                args.description,
                args.owner,
            ))
            conn.commit()
            print(f"✅ 已添加：{args.code} (id={cur.lastrowid})")
    finally:
        conn.close()
    return 0


def cmd_delete(args) -> int:
    """删除数据源"""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT id, source_name FROM {_table()} WHERE source_code = %s",
                (args.code,),
            )
            row = cur.fetchone()
            if not row:
                print(f"❌ 未找到 source_code = {args.code}", file=sys.stderr)
                return 1
            rid, name = row
            if args.force:
                cur.execute(f"DELETE FROM {_table()} WHERE source_code = %s", (args.code,))
                conn.commit()
                print(f"🗑️  硬删除：{args.code} (id={rid}, name={name})")
            else:
                cur.execute(
                    f"UPDATE {_table()} SET status='archived' WHERE source_code = %s",
                    (args.code,),
                )
                conn.commit()
                print(f"📦 软删除：{args.code} (id={rid}, name={name}, status=archived)")
    finally:
        conn.close()
    return 0


def cmd_update(args) -> int:
    """更新字段"""
    field_map = {
        "name": "source_name",
        "host": "host",
        "port": "port",
        "database": "database_name",
        "username": "username",
        "password": "password",
        "charset": "charset",
        "environment": "environment",
        "status": "status",
        "description": "description",
        "owner": "owner",
    }
    sets = []
    params = []
    for argname, dbcol in field_map.items():
        v = getattr(args, argname, None)
        if v is not None:
            sets.append(f"{dbcol} = %s")
            params.append(v)
    if not sets:
        print("❌ 没有要更新的字段", file=sys.stderr)
        return 1
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            sql = f"UPDATE {_table()} SET {', '.join(sets)} WHERE source_code = %s"
            params.append(args.code)
            cur.execute(sql, params)
            conn.commit()
            print(f"✅ 已更新：{args.code} (rows={cur.rowcount})")
    finally:
        conn.close()
    return 0


def cmd_search(args) -> int:
    """搜索"""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            kw = f"%{args.keyword}%"
            cur.execute(
                f"""SELECT id, source_code, source_name, db_type, host, port, status
                    FROM {_table()}
                    WHERE source_code LIKE %s
                       OR source_name LIKE %s
                       OR description LIKE %s
                       OR host LIKE %s
                    ORDER BY id""",
                (kw, kw, kw, kw),
            )
            rows = cur.fetchall()
            if not rows:
                print(f"(无匹配：{args.keyword})")
                return 0
            print(f"{'ID':<4} {'CODE':<30} {'NAME':<25} {'TYPE':<11} {'HOST:PORT':<22} {'STATUS':<10}")
            print("-" * 110)
            for r in rows:
                rid, code, name, typ, host, port, status = r
                print(f"{rid:<4} {code:<30} {name[:23]:<25} {typ:<11} {host}:{port:<10} {status:<10}")
            print(f"\n共 {len(rows)} 条匹配")
    finally:
        conn.close()
    return 0


def cmd_count(args) -> int:
    """统计"""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            sql = f"SELECT COUNT(*) FROM {_table()}"
            params = []
            if args.type or args.status or args.environment:
                conds = []
                if args.type:
                    conds.append("db_type = %s")
                    params.append(args.type)
                if args.status:
                    conds.append("status = %s")
                    params.append(args.status)
                if args.environment:
                    conds.append("environment = %s")
                    params.append(args.environment)
                sql += " WHERE " + " AND ".join(conds)
            cur.execute(sql, params)
            n = cur.fetchone()[0]
            filters = []
            if args.type:
                filters.append(f"type={args.type}")
            if args.status:
                filters.append(f"status={args.status}")
            if args.environment:
                filters.append(f"env={args.environment}")
            f = " " + ",".join(filters) if filters else ""
            print(f"{n}{f}")
    finally:
        conn.close()
    return 0


def cmd_status(args) -> int:
    """改状态"""
    if args.new_status not in STATUS_VALUES:
        print(f"❌ 状态必须是 {STATUS_VALUES}", file=sys.stderr)
        return 1
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"UPDATE {_table()} SET status = %s WHERE source_code = %s",
                (args.new_status, args.code),
            )
            conn.commit()
            print(f"✅ {args.code} → status={args.new_status} (rows={cur.rowcount})")
    finally:
        conn.close()
    return 0


# ============================================================
# CLI 入口
# ============================================================

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="datasource",
        description="数据源管理 CLI（基于本机 MySQL datahub.db_source）",
    )
    parser.add_argument(
        "--db-host",
        default=None,
        help="连接本机 datahub 用的 MySQL Host (空=Unix socket)",
    )
    parser.add_argument(
        "--db-port",
        type=int,
        default=None,
        help=f"连接本机 datahub 用的 Port (默认 {DEFAULTS['port']})",
    )
    parser.add_argument(
        "--db-user",
        default=None,
        help=f"连接本机 datahub 用的 User (默认 {DEFAULTS['user']})",
    )
    parser.add_argument(
        "--db-socket",
        dest="db_socket",
        default=None,
        help=f"连接本机 datahub 用的 Unix socket 路径 (默认 {DEFAULTS['socket']})",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    # list
    p = sub.add_parser("list", help="列出数据源")
    p.add_argument("--type", choices=DB_TYPES)
    p.add_argument("--status", choices=STATUS_VALUES)
    p.add_argument("--environment", choices=ENV_VALUES)
    p.add_argument("--json", action="store_true", help="JSON 输出")
    p.set_defaults(func=cmd_list)

    # show
    p = sub.add_parser("show", help="查看详情")
    p.add_argument("code", help="source_code")
    p.add_argument("--show-password", action="store_true", help="显示明文密码")
    p.set_defaults(func=cmd_show)

    # add
    p = sub.add_parser("add", help="新增数据源")
    p.add_argument("--code", required=True)
    p.add_argument("--name", required=True)
    p.add_argument("--type", required=True, choices=DB_TYPES)
    p.add_argument("--host", required=True)
    p.add_argument("--port", type=int, required=True)
    p.add_argument("--database")
    p.add_argument("--username")
    p.add_argument("--password")
    p.add_argument("--charset", default="utf8mb4")
    p.add_argument("--environment", choices=ENV_VALUES, default="unknown")
    p.add_argument("--status", choices=STATUS_VALUES, default="active")
    p.add_argument("--description")
    p.add_argument("--owner")
    p.set_defaults(func=cmd_add)

    # delete
    p = sub.add_parser("delete", help="删除数据源")
    p.add_argument("code")
    p.add_argument("--force", action="store_true", help="硬删除（默认软删除）")
    p.set_defaults(func=cmd_delete)

    # update
    p = sub.add_parser("update", help="更新字段")
    p.add_argument("code")
    p.add_argument("--name")
    p.add_argument("--host")
    p.add_argument("--port", type=int)
    p.add_argument("--database")
    p.add_argument("--username")
    p.add_argument("--password")
    p.add_argument("--charset")
    p.add_argument("--environment", choices=ENV_VALUES)
    p.add_argument("--status", choices=STATUS_VALUES)
    p.add_argument("--description")
    p.add_argument("--owner")
    p.set_defaults(func=cmd_update)

    # search
    p = sub.add_parser("search", help="搜索")
    p.add_argument("keyword")
    p.set_defaults(func=cmd_search)

    # count
    p = sub.add_parser("count", help="统计")
    p.add_argument("--type", choices=DB_TYPES)
    p.add_argument("--status", choices=STATUS_VALUES)
    p.add_argument("--environment", choices=ENV_VALUES)
    p.set_defaults(func=cmd_count)

    # status
    p = sub.add_parser("status", help="改状态")
    p.add_argument("code")
    p.add_argument("new_status", choices=STATUS_VALUES)
    p.set_defaults(func=cmd_status)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    # CLI 级 --host/--port/--user 覆盖
    if args.db_host is not None:
        DEFAULTS["host"] = args.db_host
    if args.db_port is not None:
        DEFAULTS["port"] = args.db_port
    if args.db_user is not None:
        DEFAULTS["user"] = args.db_user
    if args.db_socket is not None:
        DEFAULTS["socket"] = args.db_socket

    try:
        return args.func(args) or 0
    except Exception as e:
        print(f"❌ {type(e).__name__}: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())