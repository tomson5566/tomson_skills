#!/usr/bin/env python3
from __future__ import annotations

"""
ThinkWiki Script: serve_outputs

Purpose:
- Serve the wiki HTML output directory over loopback HTTP for browser access in agent hosts.

Usage:
- Prefer `python scripts/thinkwiki serve ...`.
- Run `python scripts/<script> --help` for direct CLI details when the file exposes its own arguments.
"""


import argparse
import functools
import http.server
import socket
import socketserver
import sys
from pathlib import Path

from utils import (
    DEFAULT_SERVE_HOST,
    DEFAULT_SERVE_PORT,
    display_root_arg,
    find_repo_root,
    format_output_serve_lines,
    output_dir_has_browsable_pages,
)


class QuietHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        if getattr(self.server, "verbose", False):
            super().log_message(format, *args)


class ReusableTCPServer(socketserver.TCPServer):
    allow_reuse_address = True


def resolve_port(host: str, port: int) -> int:
    if port != 0:
        return port
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((host, 0))
        return int(sock.getsockname()[1])


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Serve ThinkWiki HTML outputs over loopback HTTP for browser access."
    )
    parser.add_argument("--root", default=".", help="Wiki root path")
    parser.add_argument(
        "--host",
        default=DEFAULT_SERVE_HOST,
        help=f"Bind host (default: {DEFAULT_SERVE_HOST})",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_SERVE_PORT,
        help=f"Bind port; use 0 to pick a free port (default: {DEFAULT_SERVE_PORT})",
    )
    parser.add_argument(
        "--print-urls",
        action="store_true",
        help="Print the HTTP URLs that this command would expose, then exit without starting a server",
    )
    parser.add_argument(
        "--allow-lan",
        action="store_true",
        help="Allow binding to non-loopback hosts such as 0.0.0.0",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Log each HTTP request to stderr",
    )
    args = parser.parse_args()

    loopback_hosts = {"127.0.0.1", "localhost", "::1"}
    if args.host not in loopback_hosts and not args.allow_lan:
        print(
            f"Refusing to bind to non-loopback host {args.host!r} without --allow-lan.",
            file=sys.stderr,
        )
        return 1
    if args.host not in loopback_hosts:
        print(
            f"Warning: serving ThinkWiki outputs on {args.host}:{args.port or DEFAULT_SERVE_PORT} "
            "may expose wiki HTML to your local network.",
            file=sys.stderr,
        )

    root = find_repo_root(Path(args.root))
    output_dir = root / "output"
    if not output_dir.is_dir():
        print(
            f"Output directory not found: {output_dir}\n"
            f"Run `python scripts/thinkwiki viewer --root {display_root_arg(root)}` "
            "or `graph` first to generate HTML outputs.",
            file=sys.stderr,
        )
        return 1

    if not output_dir_has_browsable_pages(output_dir):
        print(
            f"No browsable HTML outputs found under {output_dir}\n"
            f"Run `python scripts/thinkwiki viewer --root {display_root_arg(root)}` "
            "or `graph` first.",
            file=sys.stderr,
        )
        return 1

    port = resolve_port(args.host, args.port)
    lines = format_output_serve_lines(root, host=args.host, port=port)
    if args.print_urls:
        print("\n".join(lines))
        return 0

    handler = functools.partial(QuietHTTPRequestHandler, directory=str(output_dir.resolve()))
    try:
        with ReusableTCPServer((args.host, port), handler) as httpd:
            httpd.verbose = args.verbose
            print("\n".join(lines))
            print("")
            print("Press Ctrl+C to stop the server.")
            httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped ThinkWiki output server.")
        return 0
    except OSError as exc:
        print(f"Could not start output server on {args.host}:{port}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
