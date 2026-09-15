"""Asyncio TCP server that matches two players into a room."""

from __future__ import annotations

import asyncio
import logging
import threading
import uuid

from gomoku.communication.messages import Message, MessageType
from gomoku.config import BOARD_SIZE, DEFAULT_HOST, DEFAULT_PORT
from gomoku.data.stone import Stone
from gomoku.data.store import IGameStore, InMemoryGameStore
from gomoku.exceptions import GomokuError, ProtocolError
from gomoku.service.game_service import GameService

logger = logging.getLogger(__name__)


class ClientSession:
    """One accepted TCP connection."""

    def __init__(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        self.reader = reader
        self.writer = writer
        self.player_id = uuid.uuid4().hex[:8]
        self.name = "Player"
        self.color: Stone | None = None
        self.room: Room | None = None
        self.joined = False

    def peer(self) -> str:
        addr = self.writer.get_extra_info("peername")
        if not addr:
            return "unknown"
        return f"{addr[0]}:{addr[1]}"

    async def send(self, message: Message) -> None:
        try:
            self.writer.write(message.to_bytes())
            await self.writer.drain()
        except (ConnectionError, OSError):
            logger.debug("send failed to %s", self.player_id)

    async def close(self) -> None:
        try:
            self.writer.close()
            await self.writer.wait_closed()
        except OSError:
            pass


class Room:
    """One match between black and white, guarded by an asyncio lock."""

    def __init__(
        self,
        black: ClientSession,
        white: ClientSession,
        service: GameService,
        store: IGameStore,
        board_size: int = BOARD_SIZE,
    ) -> None:
        self.id = uuid.uuid4().hex[:8]
        self.black = black
        self.white = white
        self._service = service
        self._store = store
        self._lock = asyncio.Lock()
        self._store.put(self.id, service.create(board_size))
        black.color = Stone.BLACK
        white.color = Stone.WHITE
        black.room = self
        white.room = self

    async def start(self) -> None:
        state = self._store.get(self.id)
        if state is None:
            raise RuntimeError("room state missing")
        size = state.board.size
        await self.black.send(
            Message.game_start(Stone.BLACK, self.white.name, size)
        )
        await self.white.send(
            Message.game_start(Stone.WHITE, self.black.name, size)
        )
        logger.info(
            "room %s started: %s (black) vs %s (white)",
            self.id,
            self.black.name,
            self.white.name,
        )

    def other(self, session: ClientSession) -> ClientSession:
        return self.white if session is self.black else self.black

    async def handle_place(
        self,
        session: ClientSession,
        message: Message,
    ) -> None:
        async with self._lock:
            state = self._store.get(self.id)
            if state is None:
                await session.send(Message.error("对局不存在"))
                return
            if session.color is None:
                await session.send(Message.invalid("尚未分配执子颜色"))
                return
            try:
                position = message.position()
                result = self._service.apply_move(
                    state,
                    session.color,
                    position,
                )
            except (GomokuError, KeyError, TypeError, ValueError) as exc:
                reason = (
                    str(exc) if isinstance(exc, GomokuError)
                    else "落子数据无效"
                )
                await session.send(Message.invalid(reason))
                return
            self._store.put(self.id, state)
            move_msg = Message.from_move(result)
            await self.black.send(move_msg)
            await self.white.send(move_msg)
            if result.is_finished:
                over = Message.game_over(result)
                await self.black.send(over)
                await self.white.send(over)

    async def notify_leave(self, session: ClientSession) -> None:
        await self.other(session).send(Message.opponent_left())

    def dispose(self) -> None:
        self._store.delete(self.id)
        self.black.room = None
        self.white.room = None


class SessionManager:
    """Pairs waiting clients and routes messages into rooms."""

    def __init__(
        self,
        service: GameService | None = None,
        store: IGameStore | None = None,
        board_size: int = BOARD_SIZE,
    ) -> None:
        self._service = service or GameService()
        self._store = store or InMemoryGameStore()
        self._board_size = board_size
        self._waiting: list[ClientSession] = []
        self._rooms: dict[str, Room] = {}
        self._lock = asyncio.Lock()

    async def handle_connection(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        session = ClientSession(reader, writer)
        logger.info(
            "client connected %s (%s)",
            session.peer(),
            session.player_id,
        )
        try:
            await self._client_loop(session)
        except (ConnectionError, asyncio.IncompleteReadError, OSError):
            logger.info("client disconnected %s", session.player_id)
        finally:
            await self._disconnect(session)

    async def _client_loop(self, session: ClientSession) -> None:
        while True:
            raw = await session.reader.readline()
            if not raw:
                return
            try:
                message = Message.from_bytes(raw)
            except ProtocolError as exc:
                await session.send(Message.error(str(exc)))
                continue
            await self._dispatch(session, message)

    async def _dispatch(
        self,
        session: ClientSession,
        message: Message,
    ) -> None:
        if message.type == MessageType.PING.value:
            await session.send(Message(MessageType.PONG, {}))
            return
        if message.type == MessageType.JOIN.value:
            await self._on_join(session, message)
            return
        if not session.joined:
            await session.send(Message.error("请先发送 join"))
            return
        if message.type == MessageType.PLACE.value:
            if session.room is None:
                await session.send(Message.invalid("对局尚未开始"))
                return
            await session.room.handle_place(session, message)
            return
        await session.send(Message.error(f"未知消息类型: {message.type}"))

    async def _on_join(
        self,
        session: ClientSession,
        message: Message,
    ) -> None:
        if session.joined:
            await session.send(Message.error("已经加入"))
            return
        name = str(message.payload.get("name") or "Player").strip()
        session.name = name[:16] or "Player"
        session.joined = True
        await session.send(Message.joined(session.player_id, session.name))
        async with self._lock:
            self._waiting.append(session)
            if len(self._waiting) >= 2:
                black = self._waiting.pop(0)
                white = self._waiting.pop(0)
                room = Room(
                    black,
                    white,
                    self._service,
                    self._store,
                    self._board_size,
                )
                self._rooms[room.id] = room
                await room.start()
            else:
                await session.send(Message.waiting())

    async def _disconnect(self, session: ClientSession) -> None:
        async with self._lock:
            if session in self._waiting:
                self._waiting.remove(session)
            room = session.room
            if room is not None:
                self._rooms.pop(room.id, None)
                room.dispose()
                try:
                    await room.notify_leave(session)
                except OSError:
                    pass
        await session.close()


async def serve(
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
) -> None:
    manager = SessionManager()
    server = await asyncio.start_server(
        manager.handle_connection,
        host,
        port,
    )
    sockets = server.sockets or []
    for sock in sockets:
        logger.info("listening on %s", sock.getsockname())
    async with server:
        await server.serve_forever()


def run_server(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    logger.info("gomoku server %s:%s", host, port)
    try:
        asyncio.run(serve(host, port))
    except KeyboardInterrupt:
        logger.info("server stopped")


def start_embedded_server(
    host: str = "0.0.0.0",
    port: int = DEFAULT_PORT,
) -> int:
    """Run the match server in a daemon thread. Return the bound port.

    The player who clicks「创建房间」owns this process: they are the host,
    and no extra server window is required.
    """
    last_error: OSError | None = None
    for candidate in range(port, port + 16):
        try:
            return _spawn_server_thread(host, candidate)
        except OSError as exc:
            last_error = exc
            continue
    raise RuntimeError("无法启动房间服务，端口被占用") from last_error


def _spawn_server_thread(host: str, port: int) -> int:
    ready = threading.Event()
    error: list[BaseException] = []
    bound: list[int] = []

    def _run() -> None:
        try:
            asyncio.run(_serve_and_signal(host, port, ready, bound))
        except OSError as exc:
            error.append(exc)
            ready.set()
        except Exception as exc:  # pragma: no cover - unexpected
            error.append(exc)
            ready.set()

    thread = threading.Thread(
        target=_run,
        name="gomoku-host",
        daemon=True,
    )
    thread.start()
    if not ready.wait(timeout=5):
        raise RuntimeError("房主服务启动超时")
    if error:
        raise error[0]
    return bound[0]


async def _serve_and_signal(
    host: str,
    port: int,
    ready: threading.Event,
    bound: list[int],
) -> None:
    manager = SessionManager()
    server = await asyncio.start_server(
        manager.handle_connection,
        host,
        port,
    )
    sockets = server.sockets or []
    if not sockets:
        raise OSError("server has no bound socket")
    bound.append(int(sockets[0].getsockname()[1]))
    logger.info("embedded host listening on %s", sockets[0].getsockname())
    ready.set()
    async with server:
        await server.serve_forever()
