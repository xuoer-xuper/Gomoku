"""Pygame application: input, network pump and board rendering."""

from __future__ import annotations

import logging
import sys

try:
    import pygame
except ImportError:  # pragma: no cover - optional legacy UI
    pygame = None  # type: ignore[assignment]

from gomoku.communication.client import GameClient
from gomoku.communication.messages import Message, MessageType
from gomoku.config import (
    BOARD_MARGIN,
    BOARD_SIZE,
    CELL_SIZE,
    DEFAULT_HOST,
    DEFAULT_PORT,
    FPS,
    FOOTER_HEIGHT,
    HUD_HEIGHT,
    WINDOW_PADDING,
)
from gomoku.data.board import Board
from gomoku.data.position import Position
from gomoku.data.stone import Stone
from gomoku.presentation import colors
from gomoku.presentation.board_view import BoardView
from gomoku.presentation.hud import Hud

logger = logging.getLogger(__name__)


def _load_font(size: int, bold: bool = False) -> pygame.font.Font:
    candidates = (
        "microsoftyahei",
        "msyh",
        "simhei",
        "simsun",
        "notosanscjksc",
        "arial",
    )
    for name in candidates:
        path = pygame.font.match_font(name, bold=bold)
        if path:
            return pygame.font.Font(path, size)
    return pygame.font.Font(None, size)


class GameApp:
    """Presentation facade. Talks to GameClient, never to GameService."""

    def __init__(
        self,
        host: str,
        port: int,
        name: str,
        room_code: str | None = None,
        is_host: bool = False,
    ) -> None:
        self._host = host
        self._port = port
        self._name = name
        self._room_code = room_code
        self._is_host = is_host
        self._client = GameClient()
        self._board = Board(BOARD_SIZE)
        self._my_color: Stone | None = None
        self._current_turn: Stone | None = None
        self._last_move: Position | None = None
        self._hover: Position | None = None
        self._opponent_name = "等待中"
        self._status = "正在连接…"
        self._detail = self._waiting_detail()
        self._hint = "ESC 退出"
        self._status_color = colors.ACCENT
        self._finished = False
        self._can_place = False
        self._overlay = ""

    def connect(self) -> None:
        self._client.connect(self._host, self._port)
        self._client.join(self._name)
        self._status = (
            f"房间 {self._room_code}" if self._room_code else "已连接"
        )
        if self._is_host:
            self._hint = "房间号已复制，发给同一 Wi-Fi 的朋友即可加入"
        else:
            self._hint = "正在进入房间…"
        self._status_color = colors.ACCENT

    def _waiting_detail(self) -> str:
        if self._room_code:
            role = "房主" if self._is_host else "客人"
            return f"{role}  {self._name}  ·  房间 {self._room_code}"
        return f"{self._name}  {self._host}:{self._port}"

    def run(self) -> None:
        pygame.init()
        caption = "联机五子棋"
        if self._room_code:
            caption = f"联机五子棋  {self._room_code}"
        pygame.display.set_caption(caption)
        board_span = (BOARD_SIZE - 1) * CELL_SIZE
        width = WINDOW_PADDING * 2 + BOARD_MARGIN * 2 + board_span
        height = (
            HUD_HEIGHT
            + WINDOW_PADDING
            + BOARD_MARGIN * 2
            + board_span
            + FOOTER_HEIGHT
        )
        running = True
        try:
            screen = pygame.display.set_mode((width, height))
            origin_x = WINDOW_PADDING + BOARD_MARGIN
            origin_y = HUD_HEIGHT + BOARD_MARGIN
            board_view = BoardView(origin_x, origin_y)
            title_font = _load_font(22, bold=True)
            body_font = _load_font(16)
            label_font = _load_font(13)
            hud = Hud(
                width,
                HUD_HEIGHT,
                height - FOOTER_HEIGHT,
                FOOTER_HEIGHT,
                title_font,
                body_font,
            )
            clock = pygame.time.Clock()
            while running:
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        running = False
                    elif event.type == pygame.KEYDOWN:
                        if event.key == pygame.K_ESCAPE:
                            running = False
                    elif event.type == pygame.MOUSEMOTION:
                        self._hover = board_view.hit_test(event.pos)
                    elif (
                        event.type == pygame.MOUSEBUTTONDOWN
                        and event.button == 1
                    ):
                        self._on_click(board_view.hit_test(event.pos))
                self._pump()
                screen.fill(colors.BG)
                board_view.draw(
                    screen,
                    self._board,
                    self._last_move,
                    self._hover,
                    self._my_color if self._is_my_turn() else None,
                    label_font,
                )
                title = "联机五子棋"
                hud.draw(
                    screen,
                    title,
                    self._status,
                    self._detail,
                    self._hint,
                    self._status_color,
                )
                if self._overlay:
                    self._draw_overlay(screen, title_font, width, height)
                pygame.display.flip()
                clock.tick(FPS)
        finally:
            self._client.close()
            pygame.quit()

    def _on_click(self, position: Position | None) -> None:
        if position is None or not self._can_place or self._finished:
            return
        if not self._is_my_turn():
            self._hint = "还没轮到你落子"
            return
        if not self._board.is_empty(position):
            self._hint = "该位置已有棋子"
            return
        self._client.place(position.row, position.col)

    def _is_my_turn(self) -> bool:
        return (
            self._can_place
            and not self._finished
            and self._my_color is not None
            and self._current_turn is self._my_color
        )

    def _pump(self) -> None:
        for message in self._client.poll():
            self._dispatch(message)

    def _dispatch(self, message: Message) -> None:
        handlers = {
            MessageType.JOINED.value: self._on_joined,
            MessageType.WAITING.value: self._on_waiting,
            MessageType.GAME_START.value: self._on_game_start,
            MessageType.MOVE.value: self._on_move,
            MessageType.INVALID.value: self._on_invalid,
            MessageType.GAME_OVER.value: self._on_game_over,
            MessageType.OPPONENT_LEFT.value: self._on_opponent_left,
            MessageType.ERROR.value: self._on_error,
        }
        handler = handlers.get(message.type)
        if handler is not None:
            handler(message)

    def _on_joined(self, message: Message) -> None:
        player_id = message.payload.get("player_id", "")
        self._detail = f"{self._name}  #{player_id}"

    def _on_waiting(self, _message: Message) -> None:
        if self._room_code:
            self._status = f"房间 {self._room_code}  ·  等待对手"
            self._hint = "把房间号发给同一 Wi-Fi 的朋友"
        else:
            self._status = "等待对手加入"
            self._hint = "等待第二位玩家加入"

    def _on_game_start(self, message: Message) -> None:
        color = Stone.from_code(str(message.payload["your_color"]))
        self._my_color = color
        self._opponent_name = str(
            message.payload.get("opponent_name") or "对手"
        )
        self._current_turn = Stone.BLACK
        self._board = Board(BOARD_SIZE)
        self._last_move = None
        self._finished = False
        self._can_place = True
        self._overlay = ""
        self._status = (
            "轮到你落子" if color is Stone.BLACK else "等待对手落子"
        )
        self._status_color = (
            colors.WIN if color is Stone.BLACK else colors.MUTED
        )
        self._detail = (
            f"你：{color.label}（{self._name}）  "
            f"对手：{color.opponent().label}（{self._opponent_name}）"
        )
        self._hint = "点击交叉点落子，红点标记最新一手"

    def _on_move(self, message: Message) -> None:
        row = int(message.payload["row"])
        col = int(message.payload["col"])
        stone = Stone.from_code(str(message.payload["color"]))
        position = Position(row, col)
        if self._board.is_empty(position):
            self._board.place(position, stone)
        self._last_move = position
        next_code = message.payload.get("next_turn")
        self._current_turn = (
            Stone.from_code(str(next_code)) if next_code else None
        )
        if self._finished:
            return
        if self._is_my_turn():
            self._status = "轮到你落子"
            self._status_color = colors.WIN
        else:
            self._status = "等待对手落子"
            self._status_color = colors.MUTED

    def _on_invalid(self, message: Message) -> None:
        reason = str(message.payload.get("reason") or "非法落子")
        self._hint = reason

    def _on_game_over(self, message: Message) -> None:
        self._finished = True
        self._can_place = False
        winner_code = message.payload.get("winner")
        if not winner_code:
            self._status = "和棋"
            self._status_color = colors.ACCENT
            self._overlay = "和棋"
            return
        winner = Stone.from_code(str(winner_code))
        if winner is self._my_color:
            self._status = "你赢了"
            self._status_color = colors.WIN
            self._overlay = "你赢了"
        else:
            self._status = "你输了"
            self._status_color = colors.LOSE
            self._overlay = "你输了"
        self._hint = "ESC 退出  ·  重新开一局请重启客户端"

    def _on_opponent_left(self, _message: Message) -> None:
        if self._finished:
            return
        self._finished = True
        self._can_place = False
        self._status = "对手已离开"
        self._status_color = colors.LOSE
        self._overlay = "对手已离开"
        self._hint = "ESC 退出"

    def _on_error(self, message: Message) -> None:
        text = str(message.payload.get("message") or "通讯错误")
        self._hint = text
        logger.warning("server error: %s", text)

    def _draw_overlay(
        self,
        surface: pygame.Surface,
        font: pygame.font.Font,
        width: int,
        height: int,
    ) -> None:
        veil = pygame.Surface((width, height), pygame.SRCALPHA)
        veil.fill((0, 0, 0, 110))
        surface.blit(veil, (0, 0))
        text = font.render(self._overlay, True, colors.TEXT)
        rect = text.get_rect(center=(width // 2, height // 2))
        pygame.draw.rect(
            surface,
            colors.HUD_BG,
            rect.inflate(48, 28),
            border_radius=8,
        )
        surface.blit(text, rect)


def run_client(
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    name: str = "Player",
    room_code: str | None = None,
    is_host: bool = False,
) -> None:
    if pygame is None:
        raise SystemExit("请使用 python -m gomoku 启动桌面版")
    app = GameApp(
        host,
        port,
        name,
        room_code=room_code,
        is_host=is_host,
    )
    try:
        app.connect()
    except OSError as exc:
        raise SystemExit(f"无法连接 {host}:{port} — {exc}") from exc
    app.run()


def _ensure_utf8() -> None:
    if sys.platform != "win32":
        return
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8")


if __name__ == "__main__":  # pragma: no cover
    _ensure_utf8()
    run_client()
