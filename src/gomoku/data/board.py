"""In-memory Gomoku board. Stores occupancy only, no rules."""

from gomoku.data.position import Position
from gomoku.data.stone import Stone


class Board:
    """Square grid of intersections.

    The board does not judge legality or winning lines; that belongs
    to the service layer.
    """

    def __init__(self, size: int) -> None:
        if size < 5:
            raise ValueError("board size must be at least 5")
        self._size = size
        self._cells = [
            [Stone.EMPTY for _ in range(size)] for _ in range(size)
        ]

    @property
    def size(self) -> int:
        return self._size

    def in_bounds(self, position: Position) -> bool:
        return (
            0 <= position.row < self._size
            and 0 <= position.col < self._size
        )

    def get(self, position: Position) -> Stone:
        if not self.in_bounds(position):
            raise IndexError(f"position out of bounds: {position}")
        return self._cells[position.row][position.col]

    def is_empty(self, position: Position) -> bool:
        return self.get(position) is Stone.EMPTY

    def place(self, position: Position, stone: Stone) -> None:
        """Occupy an intersection. Does not validate game rules."""
        if stone is Stone.EMPTY:
            raise ValueError("cannot place an empty stone")
        if not self.in_bounds(position):
            raise IndexError(f"position out of bounds: {position}")
        self._cells[position.row][position.col] = stone

    def clear(self, position: Position) -> None:
        """Remove a stone without changing other cells."""
        if not self.in_bounds(position):
            raise IndexError(f"position out of bounds: {position}")
        self._cells[position.row][position.col] = Stone.EMPTY

    def is_full(self) -> bool:
        return all(
            cell is not Stone.EMPTY
            for row in self._cells
            for cell in row
        )

    def snapshot(self) -> list[list[Stone]]:
        """Return a shallow copy of occupancy rows."""
        return [row.copy() for row in self._cells]
