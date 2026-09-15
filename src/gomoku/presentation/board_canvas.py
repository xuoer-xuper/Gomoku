"""Tkinter canvas that draws the 15-line board."""

from __future__ import annotations

import tkinter as tk

from gomoku.config import BOARD_SIZE
from gomoku.data.board import Board
from gomoku.data.position import Position
from gomoku.data.stone import Stone
from gomoku.presentation import theme

CELL = 38
MARGIN = 40
STAR = ((3, 3), (3, 11), (7, 7), (11, 3), (11, 11))
COLUMNS = "ABCDEFGHIJKLMNO"


class BoardCanvas(tk.Canvas):
    """Renders occupancy and maps clicks to intersections."""

    def __init__(self, master: tk.Misc, on_place) -> None:
        span = (BOARD_SIZE - 1) * CELL
        size = span + MARGIN * 2
        super().__init__(
            master,
            width=size,
            height=size,
            bg=theme.WOOD,
            highlightthickness=0,
        )
        self._on_place = on_place
        self._board = Board(BOARD_SIZE)
        self._last: Position | None = None
        self._hover: Position | None = None
        self._ghost: Stone | None = None
        self._enabled = False
        self.bind("<Button-1>", self._click)
        self.bind("<Motion>", self._motion)
        self.bind("<Leave>", lambda _e: self._clear_hover())
        self.redraw()

    @property
    def pixel_size(self) -> int:
        return (BOARD_SIZE - 1) * CELL + MARGIN * 2

    def set_board(
        self,
        board: Board,
        last_move: Position | None,
        ghost: Stone | None,
        enabled: bool,
    ) -> None:
        changed = (
            self._board is not board
            or self._last != last_move
            or self._ghost is not ghost
            or self._enabled != enabled
        )
        self._board = board
        self._last = last_move
        self._ghost = ghost
        self._enabled = enabled
        if changed:
            self.redraw()

    def reset(self) -> None:
        self._board = Board(BOARD_SIZE)
        self._last = None
        self._hover = None
        self.redraw()

    def hit_test(self, x: int, y: int) -> Position | None:
        col = round((x - MARGIN) / CELL)
        row = round((y - MARGIN) / CELL)
        if not (0 <= row < BOARD_SIZE and 0 <= col < BOARD_SIZE):
            return None
        px, py = self._pixel(Position(row, col))
        if (x - px) ** 2 + (y - py) ** 2 > (CELL // 2) ** 2:
            return None
        return Position(row, col)

    def redraw(self) -> None:
        self.delete("all")
        span = (BOARD_SIZE - 1) * CELL
        self.create_rectangle(
            8,
            8,
            span + MARGIN * 2 - 8,
            span + MARGIN * 2 - 8,
            outline=theme.WOOD_DARK,
            width=3,
        )
        for index in range(BOARD_SIZE):
            offset = MARGIN + index * CELL
            self.create_line(
                MARGIN,
                offset,
                MARGIN + span,
                offset,
                fill=theme.WOOD_DARK,
            )
            self.create_line(
                offset,
                MARGIN,
                offset,
                MARGIN + span,
                fill=theme.WOOD_DARK,
            )
            self.create_text(
                offset,
                18,
                text=COLUMNS[index],
                fill=theme.WOOD_DARK,
                font=theme.BODY_FONT,
            )
            self.create_text(
                16,
                offset,
                text=str(index + 1),
                fill=theme.WOOD_DARK,
                font=theme.BODY_FONT,
            )
        for row, col in STAR:
            x, y = self._pixel(Position(row, col))
            self.create_oval(x - 4, y - 4, x + 4, y + 4, fill=theme.WOOD_DARK)
        if (
            self._hover is not None
            and self._ghost is not None
            and self._enabled
            and self._board.is_empty(self._hover)
        ):
            self._draw_ghost(self._hover, self._ghost)
        for row in range(self._board.size):
            for col in range(self._board.size):
                pos = Position(row, col)
                stone = self._board.get(pos)
                if stone is not Stone.EMPTY:
                    self._draw_stone(pos, stone, pos == self._last)

    def _pixel(self, position: Position) -> tuple[int, int]:
        return (
            MARGIN + position.col * CELL,
            MARGIN + position.row * CELL,
        )

    def _draw_stone(
        self,
        position: Position,
        stone: Stone,
        is_last: bool,
    ) -> None:
        x, y = self._pixel(position)
        radius = CELL // 2 - 3
        fill = theme.BLACK if stone is Stone.BLACK else theme.WHITE
        self.create_oval(
            x - radius + 2,
            y - radius + 2,
            x + radius + 2,
            y + radius + 2,
            fill="#5a3a18",
            outline="",
        )
        self.create_oval(
            x - radius,
            y - radius,
            x + radius,
            y + radius,
            fill=fill,
            outline="#1a120c",
        )
        self.create_oval(
            x - radius + 4,
            y - radius + 3,
            x - radius + 11,
            y - radius + 10,
            fill="#ffffff",
            outline="",
        )
        if is_last:
            self.create_oval(
                x - 5,
                y - 5,
                x + 5,
                y + 5,
                fill=theme.LOSE,
                outline="",
            )

    def _draw_ghost(self, position: Position, stone: Stone) -> None:
        x, y = self._pixel(position)
        radius = CELL // 2 - 3
        color = theme.BLACK if stone is Stone.BLACK else theme.WHITE
        self.create_oval(
            x - radius,
            y - radius,
            x + radius,
            y + radius,
            outline=color,
            width=2,
        )

    def _click(self, event: tk.Event) -> None:
        if not self._enabled:
            return
        position = self.hit_test(event.x, event.y)
        if position is not None:
            self._on_place(position)

    def _motion(self, event: tk.Event) -> None:
        hover = self.hit_test(event.x, event.y)
        if hover != self._hover:
            self._hover = hover
            self.redraw()

    def _clear_hover(self) -> None:
        if self._hover is not None:
            self._hover = None
            self.redraw()
