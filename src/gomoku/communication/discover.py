"""UDP room announcement using a random room code."""

from __future__ import annotations

import asyncio
import logging
import socket
import time
from typing import Any

from gomoku.communication.lan import list_local_ipv4, subnet_broadcast
from gomoku.communication.room_code import normalize_room_code
from gomoku.config import DISCOVERY_PORT

logger = logging.getLogger(__name__)

_DISCOVER = "GOMOKU_DISCOVER"
_HOST = "GOMOKU_HOST"


class AnnounceProtocol(asyncio.DatagramProtocol):
    """Replies to guests probing for an open room."""

    def __init__(self, state: dict[str, Any]) -> None:
        self._state = state
        self.transport: asyncio.DatagramTransport | None = None

    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        self.transport = transport  # type: ignore[assignment]

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        code = str(self._state.get("code") or "")
        port = int(self._state.get("port") or 0)
        if not code or not port or self.transport is None:
            return
        text = data.decode("utf-8", "ignore").strip()
        expected = f"{_DISCOVER} {code}"
        if text != expected:
            return
        reply = f"{_HOST} {code} {port}".encode("utf-8")
        try:
            self.transport.sendto(reply, addr)
        except OSError:
            logger.debug("announce reply failed to %s", addr)


def set_announce_code(state: dict[str, Any], code: str) -> None:
    state["code"] = code


def discover_host(
    room_code: str,
    hint_ip: str = "",
    port: int = DISCOVERY_PORT,
    timeout: float = 2.5,
) -> tuple[str, int] | None:
    """Ask the LAN who owns ``room_code``. Return ``(ip, tcp_port)``."""
    compact = normalize_room_code(room_code)
    payload = f"{_DISCOVER} {compact}".encode("utf-8")
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.settimeout(0.25)
        targets = _probe_targets(hint_ip, port)
        deadline = time.time() + timeout
        while time.time() < deadline:
            for target in targets:
                try:
                    sock.sendto(payload, target)
                except OSError:
                    continue
            try:
                data, addr = sock.recvfrom(256)
            except TimeoutError:
                continue
            except OSError:
                continue
            parsed = _parse_reply(data, compact)
            if parsed is not None:
                _ip, found_port = parsed
                return addr[0], found_port
        return None
    finally:
        sock.close()


def _parse_reply(data: bytes, code: str) -> tuple[str, int] | None:
    text = data.decode("utf-8", "ignore").strip().split()
    if len(text) < 3 or text[0] != _HOST:
        return None
    if text[1].upper() != code.upper():
        return None
    try:
        found_port = int(text[2])
    except ValueError:
        return None
    return "0.0.0.0", found_port


def _probe_targets(hint_ip: str, port: int) -> list[tuple[str, int]]:
    targets: list[tuple[str, int]] = []
    seen: set[tuple[str, int]] = set()

    def add(ip: str) -> None:
        item = (ip, port)
        if item not in seen and ip:
            seen.add(item)
            targets.append(item)

    add(hint_ip)
    add("127.0.0.1")
    add("255.255.255.255")
    for ip in list_local_ipv4():
        add(subnet_broadcast(ip))
        add(ip)
    return targets
