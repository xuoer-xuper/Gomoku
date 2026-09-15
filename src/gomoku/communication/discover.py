"""UDP room announcement so guests can find the host if the room code IP is wrong."""

from __future__ import annotations

import asyncio
import logging
import socket
import time
from typing import Any

from gomoku.communication.lan import list_local_ipv4, subnet_broadcast

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
        if text != expected and text != _DISCOVER:
            return
        if text == _DISCOVER:
            # Ignore unscoped probes so two rooms in one lab do not collide.
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
    hint_ip: str,
    port: int,
    timeout: float = 2.0,
) -> tuple[str, int] | None:
    """Ask the LAN who owns ``room_code``. Return ``(ip, port)`` or None."""
    compact = room_code.strip().upper().replace(" ", "")
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
            parsed = _parse_reply(data, compact, port)
            if parsed is not None:
                ip, found_port = parsed
                return addr[0] or ip, found_port
        return None
    finally:
        sock.close()


def _parse_reply(
    data: bytes,
    code: str,
    fallback_port: int,
) -> tuple[str, int] | None:
    text = data.decode("utf-8", "ignore").strip().split()
    if len(text) < 2 or text[0] != _HOST:
        return None
    if text[1].upper() != code:
        return None
    found_port = fallback_port
    if len(text) >= 3:
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
    add("255.255.255.255")
    for ip in list_local_ipv4():
        add(subnet_broadcast(ip))
    return targets
