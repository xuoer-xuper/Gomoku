"""Helpers for discovering the local LAN IPv4 address."""

from __future__ import annotations

import socket


def local_ipv4() -> str:
    """Best-effort LAN address used to generate a room code."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        ip = sock.getsockname()[0]
    except OSError:
        ip = "127.0.0.1"
    finally:
        sock.close()
    if not ip or ip.startswith("127."):
        return _first_non_loopback() or "127.0.0.1"
    return ip


def _first_non_loopback() -> str | None:
    hostname = socket.gethostname()
    try:
        infos = socket.getaddrinfo(hostname, None, socket.AF_INET)
    except OSError:
        return None
    for info in infos:
        ip = info[4][0]
        if not ip.startswith("127."):
            return ip
    return None
