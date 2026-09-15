"""Draws the 15-line board and maps mouse pixels to intersections."""

from __future__ import annotations

import pygame

from gomoku.config import BOARD_MARGIN, BOARD_SIZE, CELL_SIZE
from gomoku.data.board import Board
from gomoku.data.position import Position
from gomoku.data.stone import Stone
from gomoku.presentation import colors

_STAR_POINTS = (
    Position(3, 3),
    Position(3, 11),
    Position(7, 7),
    Position(11, 3),
    Position(11, 11),
)
_COLUMNS = "ABCDEFGHIJKLMNO"


class BoardView:
    """Renders occupancy and converts clicks to board coordinates."""

    def __init__(self, origin_x: int, origin_y: int) -> None:
        self.origin_x = origin_x
        self.origin_y = origin_y
        self.span = (BOARD_SIZE - 1) * CELL_SIZE
        self.radius = CELL_SIZE // 2 - 2

    def pixel_of(self, position: Position) -> tuple[int, int]:
        return (
            self.origin_x + position.col * CELL_SIZE,
            self.origin_y + position.row * CELL_SIZE,
        )

    def hit_test(self, pixel: tuple[int, int]) -> Position | None:
        col = round((pixel[0] - self.origin_x) / CELL_SIZE)
        row = round((pixel[1] - self.origin_y) / CELL_SIZE)
        candidate = Position(row, col)
        if not (0 <= row < BOARD_SIZE and 0 <= col < BOARD_SIZE):
            return None
        center = self.pixel_of(candidate)
        dx = pixel[0] - center[0]
        dy = pixel[1] - center[1]
        if dx * dx + dy * dy > (CELL_SIZE // 2) ** 2:
            return None
        return candidate

    def draw(
        self,
        surface: pygame.Surface,
        board: Board,
        last_move: Position | None,
        hover: Position | None,
        hover_stone: Stone | None,
        font: pygame.font.Font,
    ) -> None:
        pad = BOARD_MARGIN
        rect = pygame.Rect(
            self.origin_x - pad,
            self.origin_y - pad,
            self.span + pad * 2,
            self.span + pad * 2,
        )
        pygame.draw.rect(surface, colors.WOOD, rect, border_radius=8)
        pygame.draw.rect(surface, colors.WOOD_EDGE, rect, 3, border_radius=8)
        self._draw_grid(surface)
        self._draw_stars(surface)
        self._draw_labels(surface, font)
        if (
            hover is not None
            and hover_stone is not None
            and board.is_empty(hover)
        ):
            self._draw_ghost(surface, hover, hover_stone)
        for row in range(board.size):
            for col in range(board.size):
                pos = Position(row, col)
                stone = board.get(pos)
                if stone is Stone.EMPTY:
                    continue
                self._draw_stone(surface, pos, stone, pos == last_move)

    def _draw_grid(self, surface: pygame.Surface) -> None:
        for index in range(BOARD_SIZE):
            offset = index * CELL_SIZE
            start_h = (self.origin_x, self.origin_y + offset)
            end_h = (self.origin_x + self.span, self.origin_y + offset)
            start_v = (self.origin_x + offset, self.origin_y)
            end_v = (self.origin_x + offset, self.origin_y + self.span)
            pygame.draw.line(surface, colors.GRID, start_h, end_h, 1)
            pygame.draw.line(surface, colors.GRID, start_v, end_v, 1)

    def _draw_stars(self, surface: pygame.Surface) -> None:
        for point in _STAR_POINTS:
            pygame.draw.circle(surface, colors.STAR, self.pixel_of(point), 4)

    def _draw_labels(
        self,
        surface: pygame.Surface,
        font: pygame.font.Font,
    ) -> None:
        for index in range(BOARD_SIZE):
            col_text = font.render(_COLUMNS[index], True, colors.MUTED)
            row_text = font.render(str(index + 1), True, colors.MUTED)
            x = self.origin_x + index * CELL_SIZE
            y = self.origin_y + index * CELL_SIZE
            surface.blit(
                col_text,
                col_text.get_rect(center=(x, self.origin_y - 22)),
            )
            surface.blit(
                row_text,
                row_text.get_rect(center=(self.origin_x - 22, y)),
            )

    def _draw_stone(
        self,
        surface: pygame.Surface,
        position: Position,
        stone: Stone,
        is_last: bool,
    ) -> None:
        center = self.pixel_of(position)
        fill = (
            colors.BLACK_STONE
            if stone is Stone.BLACK
            else colors.WHITE_STONE
        )
        shadow = (center[0] + 2, center[1] + 2)
        pygame.draw.circle(surface, colors.STONE_EDGE, shadow, self.radius)
        pygame.draw.circle(surface, fill, center, self.radius)
        pygame.draw.circle(
            surface,
            colors.STONE_EDGE,
            center,
            self.radius,
            1,
        )
        highlight = (
            center[0] - self.radius // 3,
            center[1] - self.radius // 3,
        )
        pygame.draw.circle(surface, colors.HIGHLIGHT, highlight, 3)
        if is_last:
            pygame.draw.circle(surface, colors.LAST_MOVE, center, 5)

    def _draw_ghost(
        self,
        surface: pygame.Surface,
        position: Position,
        stone: Stone,
    ) -> None:
        color = (
            colors.BLACK_STONE
            if stone is Stone.BLACK
            else colors.WHITE_STONE
        )
        pygame.draw.circle(
            surface,
            color,
            self.pixel_of(position),
            self.radius,
            2,
        )
