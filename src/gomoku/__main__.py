"""Command-line entry: python -m gomoku {server|client}."""

from __future__ import annotations

import argparse
import logging
import sys

from gomoku import __version__
from gomoku.config import DEFAULT_HOST, DEFAULT_PORT


def _configure_stdio() -> None:
    if sys.platform != "win32":
        return
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8")


def _configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gomoku",
        description="局域网双人联机五子棋",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"gomoku {__version__}",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    server = sub.add_parser("server", help="启动房主对局服务")
    server.add_argument("--host", default="0.0.0.0")
    server.add_argument("--port", type=int, default=DEFAULT_PORT)

    client = sub.add_parser("client", help="启动棋盘客户端")
    client.add_argument("--host", default=DEFAULT_HOST)
    client.add_argument("--port", type=int, default=DEFAULT_PORT)
    client.add_argument("--name", default="Player")
    return parser


def main(argv: list[str] | None = None) -> int:
    _configure_stdio()
    _configure_logging()
    args = build_parser().parse_args(argv)
    if args.command == "server":
        from gomoku.communication.server import run_server

        run_server(args.host, args.port)
        return 0
    from gomoku.presentation.app import run_client

    run_client(args.host, args.port, args.name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
