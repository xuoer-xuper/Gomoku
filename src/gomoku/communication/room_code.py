"""Room codes: random public codes, plus legacy IP encoding."""

from __future__ import annotations

import secrets

# 32 symbols, skip 0/O/1/I to reduce misreading.
_ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"
_CODE_LEN = 10
_RANDOM_LEN = 6


class RoomCodeError(ValueError):
    """Raised when a room code cannot be parsed."""


def generate_room_code() -> str:
    """Random ``XXX-XXX`` code, unique per room rather than per machine."""
    raw = "".join(secrets.choice(_ALPHABET) for _ in range(_RANDOM_LEN))
    return f"{raw[:3]}-{raw[3:]}"


def normalize_room_code(code: str) -> str:
    """Strip spaces and unify dashes; raise if empty."""
    compact = (
        code.strip()
        .upper()
        .replace(" ", "")
        .replace("—", "-")
        .replace("_", "")
    )
    if "-" not in compact and len(compact) == _RANDOM_LEN:
        compact = f"{compact[:3]}-{compact[3:]}"
    if len(compact.replace("-", "")) < 4:
        raise RoomCodeError("请输入房间号")
    return compact


def encode_endpoint(ip: str, port: int) -> str:
    """Turn IPv4 + port into ``XXXXX-XXXXX``."""
    parts = ip.split(".")
    if len(parts) != 4:
        raise RoomCodeError("无效的 IP 地址")
    try:
        octets = [int(item) for item in parts]
    except ValueError as exc:
        raise RoomCodeError("无效的 IP 地址") from exc
    if any(item < 0 or item > 255 for item in octets):
        raise RoomCodeError("无效的 IP 地址")
    if not 0 <= port <= 65535:
        raise RoomCodeError("无效的端口")
    value = (
        (octets[0] << 40)
        | (octets[1] << 32)
        | (octets[2] << 24)
        | (octets[3] << 16)
        | port
    )
    raw = _encode_int(value, _CODE_LEN)
    return f"{raw[:5]}-{raw[5:]}"


def decode_endpoint(code: str) -> tuple[str, int]:
    """Parse a room code back to ``(ip, port)``."""
    compact = (
        code.strip()
        .upper()
        .replace("-", "")
        .replace(" ", "")
        .replace("—", "")
    )
    if len(compact) != _CODE_LEN:
        raise RoomCodeError("房间号应为 10 位（中间可带横线）")
    value = 0
    for char in compact:
        index = _ALPHABET.find(char)
        if index < 0:
            raise RoomCodeError("房间号包含无效字符")
        value = value * 32 + index
    port = value & 0xFFFF
    octet_d = (value >> 16) & 0xFF
    octet_c = (value >> 24) & 0xFF
    octet_b = (value >> 32) & 0xFF
    octet_a = (value >> 40) & 0xFF
    return f"{octet_a}.{octet_b}.{octet_c}.{octet_d}", port


def _encode_int(value: int, length: int) -> str:
    chars: list[str] = []
    current = value
    for _ in range(length):
        chars.append(_ALPHABET[current % 32])
        current //= 32
    if current:
        raise RoomCodeError("地址超出房间号编码范围")
    return "".join(reversed(chars))
