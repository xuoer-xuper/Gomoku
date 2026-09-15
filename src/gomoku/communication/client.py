"""Blocking TCP client that talks JSON lines on a background thread."""

from __future__ import annotations

import logging
import queue
import socket
import threading

from gomoku.communication.messages import Message, MessageType
from gomoku.config import ENCODING
from gomoku.exceptions import ProtocolError

logger = logging.getLogger(__name__)


class SocketTransport:
    """Reads and writes newline-delimited messages on a TCP socket."""

    def __init__(self, sock: socket.socket) -> None:
        self._sock = sock
        self._buffer = b""

    def send(self, message: Message) -> None:
        self._sock.sendall(message.to_bytes())

    def recv(self) -> Message | None:
        while b"\n" not in self._buffer:
            try:
                chunk = self._sock.recv(4096)
            except OSError:
                return None
            if not chunk:
                return None
            self._buffer += chunk
        line, self._buffer = self._buffer.split(b"\n", 1)
        if not line.strip():
            return self.recv()
        return Message.from_bytes(line)

    def close(self) -> None:
        try:
            self._sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        try:
            self._sock.close()
        except OSError:
            pass


class GameClient:
    """Outbound API used by the presentation layer."""

    def __init__(self) -> None:
        self._transport: SocketTransport | None = None
        self._inbox: queue.Queue[Message] = queue.Queue()
        self._running = False
        self._thread: threading.Thread | None = None

    def connect(self, host: str, port: int, timeout: float = 8.0) -> None:
        sock = socket.create_connection((host, port), timeout=timeout)
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        sock.settimeout(None)
        self._transport = SocketTransport(sock)
        self._running = True
        self._thread = threading.Thread(
            target=self._listen,
            name="gomoku-net",
            daemon=True,
        )
        self._thread.start()
        logger.info("connected to %s:%s", host, port)

    def join(self, name: str) -> None:
        self.send(Message.join(name))

    def place(self, row: int, col: int) -> None:
        self.send(Message.place(row, col))

    def chat(self, text: str) -> None:
        self.send(Message.chat("", text))

    def request_undo(self) -> None:
        self.send(Message(MessageType.UNDO_REQUEST, {}))

    def reply_undo(self, accepted: bool) -> None:
        self.send(Message.undo_reply(accepted))

    def request_rematch(self) -> None:
        self.send(Message(MessageType.REMATCH_REQUEST, {}))

    def reply_rematch(self, accepted: bool) -> None:
        self.send(Message.rematch_reply(accepted))

    def resign(self) -> None:
        self.send(Message.resign())

    def send(self, message: Message) -> None:
        if self._transport is None:
            raise RuntimeError("client is not connected")
        self._transport.send(message)

    def poll(self) -> list[Message]:
        """Drain inbound messages without blocking the UI thread."""
        messages: list[Message] = []
        while True:
            try:
                messages.append(self._inbox.get_nowait())
            except queue.Empty:
                break
        return messages

    def close(self) -> None:
        self._running = False
        if self._transport is not None:
            self._transport.close()
            self._transport = None
        if self._thread is not None:
            self._thread.join(timeout=1.0)
            self._thread = None

    def _listen(self) -> None:
        assert self._transport is not None
        while self._running:
            try:
                message = self._transport.recv()
            except ProtocolError as exc:
                logger.warning("protocol error: %s", exc)
                self._inbox.put(Message.error(str(exc)))
                continue
            except OSError:
                break
            if message is None:
                self._inbox.put(Message.opponent_left())
                break
            self._inbox.put(message)


def decode_preview(raw: str) -> Message:
    """Helper used by tests; decode a single JSON line."""
    return Message.from_bytes(raw.encode(ENCODING))
