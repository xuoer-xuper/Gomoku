"""Two-client match over the local TCP server."""

from __future__ import annotations

import socket
import threading
import time

from gomoku.communication.client import GameClient
from gomoku.communication.messages import MessageType
from gomoku.communication.room_code import decode_endpoint, encode_endpoint
from gomoku.communication.server import serve, start_embedded_server


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait(client: GameClient, msg_type: str, timeout: float = 3.0):
    deadline = time.time() + timeout
    inbox = []
    while time.time() < deadline:
        inbox.extend(client.poll())
        for message in inbox:
            if message.type == msg_type:
                return message
        time.sleep(0.02)
    types = [item.type for item in inbox]
    raise AssertionError(f"timed out waiting for {msg_type}, got {types}")


def test_two_players_black_wins_horizontal() -> None:
    port = _free_port()
    thread = threading.Thread(
        target=lambda: _run_server(port),
        name="gomoku-test-server",
        daemon=True,
    )
    thread.start()
    _wait_port(port)

    black = GameClient()
    white = GameClient()
    try:
        black.connect("127.0.0.1", port)
        white.connect("127.0.0.1", port)
        black.join("Black")
        white.join("White")
        start_b = _wait(black, MessageType.GAME_START.value)
        start_w = _wait(white, MessageType.GAME_START.value)
        assert start_b.payload["your_color"] == "black"
        assert start_w.payload["your_color"] == "white"

        black_moves = [(7, 0), (7, 1), (7, 2), (7, 3), (7, 4)]
        white_moves = [(8, 0), (8, 1), (8, 2), (8, 3)]
        for index in range(4):
            black.place(*black_moves[index])
            _wait(black, MessageType.MOVE.value)
            _wait(white, MessageType.MOVE.value)
            white.place(*white_moves[index])
            _wait(black, MessageType.MOVE.value)
            _wait(white, MessageType.MOVE.value)
        black.place(*black_moves[4])
        over_b = _wait(black, MessageType.GAME_OVER.value)
        over_w = _wait(white, MessageType.GAME_OVER.value)
        assert over_b.payload["winner"] == "black"
        assert over_w.payload["reason"] == "five_in_a_row"
    finally:
        black.close()
        white.close()


def test_embedded_host_and_room_code() -> None:
    port = start_embedded_server("127.0.0.1", _free_port())
    code = encode_endpoint("127.0.0.1", port)
    host, decoded_port = decode_endpoint(code)
    assert host == "127.0.0.1"
    assert decoded_port == port

    black = GameClient()
    white = GameClient()
    try:
        black.connect("127.0.0.1", port)
        white.connect("127.0.0.1", port)
        black.join("Host")
        white.join("Guest")
        start_b = _wait(black, MessageType.GAME_START.value)
        start_w = _wait(white, MessageType.GAME_START.value)
        assert start_b.payload["your_color"] == "black"
        assert start_w.payload["your_color"] == "white"
    finally:
        black.close()
        white.close()


def _run_server(port: int) -> None:
    import asyncio

    asyncio.run(serve("127.0.0.1", port))


def _wait_port(port: int, timeout: float = 3.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                return
        except OSError:
            time.sleep(0.05)
    raise AssertionError(f"server did not start on {port}")
