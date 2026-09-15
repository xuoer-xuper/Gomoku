"""Tkinter canvas that draws the 15-line board with stone animation."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable

from gomoku.config import BOARD_SIZE
from gomoku.data.board import Board
from gomoku.data.position import Position
from gomoku.data.stone import Stone
from gomoku.presentation import theme
from gomoku.presentation.stones import sphere_image

CELL = 42
MARGIN = 46
STAR = ((3, 3), (3, 11), (7, 7), (11, 3), (11, 11))
COLUMNS = "ABCDEFGHIJKLMNO"
_PLACE_SCALES = (0.42, 0.62, 0.82, 1.06, 1.0)


class BoardCanvas(tk.Canvas):
    """Renders occupancy and maps clicks to intersections."""

    def __init__(
        self,
        master: tk.Misc,
        on_place: Callable[[Position], None] | None = None,
        cell: int = CELL,
        margin: int = MARGIN,
        interactive: bool = True,
    ) -> None:
        self._cell = cell
        self._margin = margin
        span = (BOARD_SIZE - 1) * cell
        size = span + margin * 2
        super().__init__(
            master,
            width=size,
            height=size,
            bg=theme.WOOD_DARK,
            highlightthickness=0,
        )
        self._on_place = on_place
        self._interactive = interactive
        self._board = Board(BOARD_SIZE)
        self._last: Position | None = None
        self._hover: Position | None = None
        self._ghost: Stone | None = None
        self._enabled = False
        self._win_line: list[Position] = []
        self._anim_pos: Position | None = None
        self._anim_stone: Stone | None = None
        self._anim_frame = -1
        self._pulse = 0
        self._tick_id: str | None = None
        self._static_ready = False
        self._photos: dict[tuple, tk.PhotoImage] = {}
        if interactive:
            self.bind("<Button-1>", self._click)
            self.bind("<Motion>", self._motion)
            self.bind("<Leave>", lambda _e: self._clear_hover())
        self.bind("<Destroy>", self._cancel_tick)
        self.redraw()
        self._tick()

    @property
    def pixel_size(self) -> int:
        return (BOARD_SIZE - 1) * self._cell + self._margin * 2

    def set_board(
        self,
        board: Board,
        last_move: Position | None,
        ghost: Stone | None,
        enabled: bool,
        win_line: list[Position] | None = None,
        animate: bool = True,
    ) -> None:
        prev_last = self._last
        new_stone = (
            board.get(last_move)
            if last_move is not None
            else Stone.EMPTY
        )
        should_animate = (
            animate
            and last_move is not None
            and last_move != prev_last
            and new_stone is not Stone.EMPTY
        )
        self._board = board
        self._last = last_move
        self._ghost = ghost
        self._enabled = enabled
        self._win_line = list(win_line or [])
        if should_animate and last_move is not None:
            self._anim_pos = last_move
            self._anim_stone = new_stone
            self._anim_frame = 0
        else:
            self._anim_pos = None
            self._anim_frame = -1
        self.redraw()

    def reset(self) -> None:
        self._board = Board(BOARD_SIZE)
        self._last = None
        self._hover = None
        self._win_line = []
        self._anim_pos = None
        self._anim_frame = -1
        self._static_ready = False
        self.redraw()

    def hit_test(self, x: int, y: int) -> Position | None:
        col = round((x - self._margin) / self._cell)
        row = round((y - self._margin) / self._cell)
        if not (0 <= row < BOARD_SIZE and 0 <= col < BOARD_SIZE):
            return None
        px, py = self._pixel(Position(row, col))
        radius = self._cell // 2
        if (x - px) ** 2 + (y - py) ** 2 > radius ** 2:
            return None
        return Position(row, col)

    def redraw(self) -> None:
        if not self._static_ready:
            self.delete("all")
            self._draw_table()
            self._draw_grid()
            self._static_ready = True
        else:
            self.delete("dyn")
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
                if stone is Stone.EMPTY:
                    continue
                scale = 1.0
                if pos == self._anim_pos and self._anim_frame >= 0:
                    index = min(self._anim_frame, len(_PLACE_SCALES) - 1)
                    scale = _PLACE_SCALES[index]
                glowing = pos in self._win_line
                self._draw_stone(pos, stone, pos == self._last, scale, glowing)

    def _draw_table(self) -> None:
        size = self.pixel_size
        self.create_rectangle(0, 0, size, size, fill=theme.WOOD_EDGE, outline="")
        self.create_rectangle(
            6,
            6,
            size - 6,
            size - 6,
            fill=theme.WOOD,
            outline=theme.WOOD_MID,
            width=2,
        )
        for index in range(8, size - 8, 7):
            shade = theme.WOOD_MID if index % 14 == 8 else theme.WOOD
            self.create_line(10, index, size - 10, index, fill=shade)

    def _draw_grid(self) -> None:
        span = (BOARD_SIZE - 1) * self._cell
        margin = self._margin
        inner = 12
        self.create_rectangle(
            margin - inner,
            margin - inner,
            margin + span + inner,
            margin + span + inner,
            outline=theme.WOOD_EDGE,
            width=3,
        )
        for index in range(BOARD_SIZE):
            offset = margin + index * self._cell
            self.create_line(
                margin,
                offset,
                margin + span,
                offset,
                fill=theme.WOOD_DARK,
            )
            self.create_line(
                offset,
                margin,
                offset,
                margin + span,
                fill=theme.WOOD_DARK,
            )
            if self._cell >= 28:
                self.create_text(
                    offset,
                    margin - 22,
                    text=COLUMNS[index],
                    fill=theme.WOOD_EDGE,
                    font=theme.CAPTION_FONT,
                )
                self.create_text(
                    margin - 22,
                    offset,
                    text=str(index + 1),
                    fill=theme.WOOD_EDGE,
                    font=theme.CAPTION_FONT,
                )
        star_r = 4 if self._cell >= 32 else 3
        for row, col in STAR:
            x, y = self._pixel(Position(row, col))
            self.create_oval(
                x - star_r,
                y - star_r,
                x + star_r,
                y + star_r,
                fill=theme.WOOD_EDGE,
                outline="",
            )

    def _pixel(self, position: Position) -> tuple[int, int]:
        return (
            self._margin + position.col * self._cell,
            self._margin + position.row * self._cell,
        )

    def _draw_stone(
        self,
        position: Position,
        stone: Stone,
        is_last: bool,
        scale: float,
        glowing: bool,
    ) -> None:
        x, y = self._pixel(position)
        radius = max(6, int((self._cell // 2 - 2) * scale))
        self.create_oval(
            x - radius + 3,
            y - radius + 5,
            x + radius + 3,
            y + radius + 6,
            fill="#3d2410",
            outline="",
            tags="dyn",
        )
        kind = "black" if stone is Stone.BLACK else "white"
        try:
            image = sphere_image(self, radius, kind, self._photos)
            self.create_image(x, y, image=image, tags="dyn")
        except tk.TclError:
            fill = theme.BLACK if stone is Stone.BLACK else theme.WHITE
            self.create_oval(
                x - radius,
                y - radius,
                x + radius,
                y + radius,
                fill=fill,
                outline="#111111",
                tags="dyn",
            )
        if glowing:
            ring = 3 + (self._pulse % 6) // 2
            self.create_oval(
                x - radius - ring,
                y - radius - ring,
                x + radius + ring,
                y + radius + ring,
                outline=theme.GOLD,
                width=2,
                tags="dyn",
            )
        elif is_last:
            ring = 2 + (self._pulse % 8) // 3
            self.create_oval(
                x - 5 - ring,
                y - 5 - ring,
                x + 5 + ring,
                y + 5 + ring,
                outline=theme.GOLD,
                width=2,
                tags="dyn",
            )

    def _draw_ghost(self, position: Position, stone: Stone) -> None:
        x, y = self._pixel(position)
        radius = self._cell // 2 - 4
        color = "#2a2a2a" if stone is Stone.BLACK else "#f3eee4"
        self.create_oval(
            x - radius,
            y - radius,
            x + radius,
            y + radius,
            outline=color,
            width=2,
            dash=(3, 2),
            tags="dyn",
        )
        self.create_oval(
            x - 3,
            y - 3,
            x + 3,
            y + 3,
            fill=color,
            outline="",
            tags="dyn",
        )

    def _click(self, event: tk.Event) -> None:
        if not self._enabled or self._on_place is None:
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

    def _tick(self) -> None:
        if not self.winfo_exists():
            return
        dirty = False
        if self._anim_frame >= 0:
            self._anim_frame += 1
            if self._anim_frame >= len(_PLACE_SCALES):
                self._anim_frame = -1
                self._anim_pos = None
            dirty = True
        if self.winfo_ismapped() and (self._last or self._win_line):
            self._pulse = (self._pulse + 1) % 24
            dirty = True
        if dirty:
            self.redraw()
        self._tick_id = self.after(45, self._tick)

    def _cancel_tick(self, _event: tk.Event | None = None) -> None:
        if self._tick_id is not None:
            try:
                self.after_cancel(self._tick_id)
            except tk.TclError:
                pass
            self._tick_id = None
