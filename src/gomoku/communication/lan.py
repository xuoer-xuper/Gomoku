"""Discover a LAN IPv4 that other computers can actually reach."""

from __future__ import annotations

import socket
import struct
import sys
from collections.abc import Iterable

# Clash / sing-box fake-ip, RFC 2544, APIPA, loopback cannot be joined
# from another machine. Encoding them into a room code yields WinError 10061.
_SKIP_PREFIXES = (
    "0.",
    "127.",
    "169.254.",
    "198.18.",
    "198.19.",
    "224.",
    "255.",
)
_VIRTUAL_PREFIXES = (
    "192.168.56.",  # VirtualBox host-only
    "192.168.137.",  # Windows Internet Connection Sharing
    "172.17.",  # Docker
    "172.18.",
    "172.19.",
)
_PROBE_TARGETS = (
    ("114.114.114.114", 80),
    ("223.5.5.5", 80),
    ("1.1.1.1", 80),
    ("8.8.8.8", 80),
)


def is_usable_lan_ipv4(ip: str) -> bool:
    """Return True if another PC on the LAN might reach this address."""
    if not ip or ip.count(".") != 3:
        return False
    if ip.startswith(_SKIP_PREFIXES):
        return False
    if ip == "0.0.0.0":
        return False
    parts = ip.split(".")
    try:
        octets = [int(item) for item in parts]
    except ValueError:
        return False
    if any(item < 0 or item > 255 for item in octets):
        return False
    # Tailscale / CGNAT 100.64.0.0/10 — not the lab Ethernet.
    if octets[0] == 100 and 64 <= octets[1] <= 127:
        return False
    return True


def is_rfc1918(ip: str) -> bool:
    """Private IPv4 used by home Wi-Fi and computer-lab Ethernet."""
    if ip.startswith("10.") or ip.startswith("192.168."):
        return True
    if not ip.startswith("172."):
        return False
    second = int(ip.split(".")[1])
    return 16 <= second <= 31


def is_virtual_ipv4(ip: str) -> bool:
    return any(ip.startswith(prefix) for prefix in _VIRTUAL_PREFIXES)


def pick_lan_ipv4(candidates: Iterable[str]) -> str:
    """Choose the address most likely to work for a LAN room code."""
    unique: list[str] = []
    seen: set[str] = set()
    for ip in candidates:
        if ip in seen:
            continue
        seen.add(ip)
        if is_usable_lan_ipv4(ip):
            unique.append(ip)
    if not unique:
        return "127.0.0.1"
    unique.sort(key=_lan_sort_key)
    return unique[0]


def local_ipv4() -> str:
    """Best-effort LAN address used to generate a room code."""
    return pick_lan_ipv4(_collect_ipv4())


def list_local_ipv4() -> list[str]:
    """Usable local IPv4 addresses, best candidate first."""
    return pick_all(_collect_ipv4())


def pick_all(candidates: Iterable[str]) -> list[str]:
    unique = []
    seen: set[str] = set()
    for ip in candidates:
        if ip in seen or not is_usable_lan_ipv4(ip):
            continue
        seen.add(ip)
        unique.append(ip)
    unique.sort(key=_lan_sort_key)
    return unique


def subnet_broadcast(ip: str, mask: str = "255.255.255.0") -> str:
    """Directed broadcast for UDP room discovery."""
    ip_i = struct.unpack("!I", socket.inet_aton(ip))[0]
    mask_i = struct.unpack("!I", socket.inet_aton(mask))[0]
    broadcast = ip_i | (~mask_i & 0xFFFFFFFF)
    return socket.inet_ntoa(struct.pack("!I", broadcast))


def describe_connect_error(exc: OSError, host: str, port: int) -> str:
    """Human-readable join failure, especially WinError 10061."""
    winerr = getattr(exc, "winerror", None)
    errno = winerr if winerr is not None else getattr(exc, "errno", None)
    unusable = not is_usable_lan_ipv4(host)
    if unusable:
        return (
            f"连接失败：房间号解析出 {host}:{port}，"
            "这不是可从其他电脑访问的局域网地址。"
            "请让房主关掉代理/VPN 后重新创建房间。"
        )
    if errno in {10061, 111, 61}:
        return (
            f"连接失败：{host}:{port} 拒绝连接。"
            "请让房主在 Windows 防火墙弹窗点「允许」，"
            "并确认房间窗口还开着、双方在同一网段。"
        )
    if errno in {10060, 10065, 110, 113, 101, 51}:
        return (
            f"连接失败：无法到达 {host}:{port}。"
            "请确认同一机房/同一交换机，且房主防火墙未拦截。"
        )
    return f"连接失败：{exc}"


def _lan_sort_key(ip: str) -> tuple[int, int, str]:
    # Lower is better: real RFC1918 first, virtual adapters last.
    return (
        0 if is_rfc1918(ip) else 1,
        1 if is_virtual_ipv4(ip) else 0,
        ip,
    )


def _collect_ipv4() -> list[str]:
    found: list[str] = []
    found.extend(_windows_ipv4())
    found.extend(_probe_ipv4())
    found.extend(_hostname_ipv4())
    return found


def _probe_ipv4() -> list[str]:
    ips: list[str] = []
    for target in _PROBE_TARGETS:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.settimeout(0.3)
            sock.connect(target)
            ip = sock.getsockname()[0]
            if ip:
                ips.append(ip)
        except OSError:
            continue
        finally:
            sock.close()
    return ips


def _hostname_ipv4() -> list[str]:
    try:
        infos = socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET)
    except OSError:
        return []
    return [info[4][0] for info in infos]


def _windows_ipv4() -> list[str]:
    if sys.platform != "win32":
        return []
    try:
        return _windows_ip_addr_table()
    except OSError:
        return []


def _windows_ip_addr_table() -> list[str]:
    """Read IPv4 from iphlpapi.GetIpAddrTable (avoids TUN default route)."""
    import ctypes
    from ctypes import wintypes

    class MibIpAddrRow(ctypes.Structure):
        _fields_ = [
            ("dwAddr", wintypes.DWORD),
            ("dwIndex", wintypes.DWORD),
            ("dwMask", wintypes.DWORD),
            ("dwBCastAddr", wintypes.DWORD),
            ("dwReasmSize", wintypes.DWORD),
            ("unused1", ctypes.c_ushort),
            ("wType", ctypes.c_ushort),
        ]

    iphlpapi = ctypes.WinDLL("iphlpapi", use_last_error=True)
    size = wintypes.DWORD(0)
    iphlpapi.GetIpAddrTable(None, ctypes.byref(size), False)
    if size.value <= 4:
        return []
    buf = ctypes.create_string_buffer(size.value)
    result = iphlpapi.GetIpAddrTable(buf, ctypes.byref(size), False)
    if result != 0:
        raise OSError(result, "GetIpAddrTable failed")
    count = struct.unpack_from("I", buf, 0)[0]
    offset = 4
    row_size = ctypes.sizeof(MibIpAddrRow)
    ips: list[str] = []
    for _ in range(count):
        if offset + row_size > len(buf):
            break
        row = MibIpAddrRow.from_buffer_copy(buf, offset)
        offset += row_size
        ip = socket.inet_ntoa(struct.pack("L", row.dwAddr))
        ips.append(ip)
    return ips
