"""LAN address picking — skip VPN/TUN so room codes work across PCs."""

from gomoku.communication.lan import (
    describe_connect_error,
    is_usable_lan_ipv4,
    local_ipv4,
    pick_lan_ipv4,
    subnet_broadcast,
)


def test_skips_loopback_apipa_and_clash_fake_ip() -> None:
    assert not is_usable_lan_ipv4("127.0.0.1")
    assert not is_usable_lan_ipv4("169.254.12.4")
    assert not is_usable_lan_ipv4("198.18.0.1")
    assert not is_usable_lan_ipv4("198.19.0.2")
    assert not is_usable_lan_ipv4("100.64.1.2")
    assert is_usable_lan_ipv4("192.168.81.28")
    assert is_usable_lan_ipv4("10.12.0.8")
    assert is_usable_lan_ipv4("172.16.1.9")


def test_pick_prefers_real_lan_over_tun() -> None:
    chosen = pick_lan_ipv4(
        ["198.18.0.1", "127.0.0.1", "192.168.81.28", "169.254.1.1"]
    )
    assert chosen == "192.168.81.28"


def test_pick_falls_back_to_loopback_when_nothing_usable() -> None:
    assert pick_lan_ipv4(["127.0.0.1", "198.18.0.1"]) == "127.0.0.1"


def test_local_ipv4_not_clash_fake_ip() -> None:
    ip = local_ipv4()
    assert not ip.startswith("198.18.")
    assert not ip.startswith("198.19.")


def test_subnet_broadcast() -> None:
    assert subnet_broadcast("192.168.81.28", "255.255.255.0") == (
        "192.168.81.255"
    )


def test_connect_error_explains_refused_and_unusable_ip() -> None:
    refused = OSError(10061, "refused")
    refused.winerror = 10061  # type: ignore[attr-defined]
    text = describe_connect_error(refused, "192.168.81.28", 8765)
    assert "拒绝连接" in text
    tun = describe_connect_error(refused, "198.18.0.1", 8765)
    assert "代理" in tun or "局域网" in tun
