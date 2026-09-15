"""UDP room discovery fallback when the encoded IP is wrong."""

from __future__ import annotations

import socket
import threading
import time

from gomoku.communication.discover import discover_host
from gomoku.communication.room_code import encode_endpoint


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def test_discover_host_receives_announcement() -> None:
    port = _free_port()
    code = encode_endpoint("127.0.0.1", port).upper()
    stop = threading.Event()

    def serve() -> None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(("127.0.0.1", port))
        sock.settimeout(0.2)
        try:
            while not stop.is_set():
                try:
                    data, addr = sock.recvfrom(256)
                except OSError:
                    continue
                text = data.decode("utf-8", "ignore")
                if code in text:
                    reply = f"GOMOKU_HOST {code} {port}".encode()
                    sock.sendto(reply, addr)
        finally:
            sock.close()

    thread = threading.Thread(target=serve, name="announce-test", daemon=True)
    thread.start()
    time.sleep(0.05)
    try:
        found = discover_host(code, "127.0.0.1", port, timeout=1.5)
        assert found is not None
        assert found[1] == port
    finally:
        stop.set()
        thread.join(timeout=1.0)
