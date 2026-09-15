"""Pure rule engine: move legality and five-in-a-row detection."""

from collections.abc import Sequence

from gomoku.config import WIN_LENGTH
from gomoku.data.board import Board
from gomoku.data.position import Position
from gomoku.data.stone import Stone
from gomoku.exceptions import InvalidMoveError

_DIRECTIONS: Sequence[tuple[int, int]] = (
    (0, 1),
    (1, 0),
    (1, 1),
    (1, -1),
)


class Referee:
    """Judges placements and winning lines. Holds no match state."""

    def __init__(self, win_length: int = WIN_LENGTH) -> None:
        if win_length < 3:
            raise ValueError("win_length must be at least 3")
        self._win_length = win_length

    @property
    def win_length(self) -> int:
        return self._win_length

    def validate_move(self, board: Board, position: Position) -> None:
        """Raise InvalidMoveError when the intersection cannot be used."""
        if not board.in_bounds(position):
            raise InvalidMoveError("落子超出棋盘范围")
        if not board.is_empty(position):
            raise InvalidMoveError("该位置已有棋子")

    def winner_from(
        self,
        board: Board,
        last_move: Position,
    ) -> Stone | None:
        """Return the winner if last_move completes a winning line."""
        stone = board.get(last_move)
        if stone is Stone.EMPTY:
            return None
        for delta_row, delta_col in _DIRECTIONS:
            total = 1
            total += self._count_ray(
                board, last_move, stone, delta_row, delta_col
            )
            total += self._count_ray(
                board, last_move, stone, -delta_row, -delta_col
            )
            if total >= self._win_length:
                return stone
        return None

    def _count_ray(
        self,
        board: Board,
        origin: Position,
        stone: Stone,
        delta_row: int,
        delta_col: int,
    ) -> int:
        count = 0
        row = origin.row + delta_row
        col = origin.col + delta_col
        while True:
            current = Position(row, col)
            if not board.in_bounds(current):
                break
            if board.get(current) is not stone:
                break
            count += 1
            row += delta_row
            col += delta_col
        return count
