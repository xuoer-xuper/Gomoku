"""Mutable snapshot of a single match."""

from dataclasses import dataclass
from enum import Enum

from gomoku.config import BOARD_SIZE
from gomoku.data.board import Board
from gomoku.data.position import Position
from gomoku.data.stone import Stone


class GameStatus(Enum):
    """Lifecycle of a match."""

    PLAYING = "playing"
    FINISHED = "finished"


@dataclass
class GameState:
    """Aggregates board occupancy and turn information."""

    board: Board
    current_turn: Stone = Stone.BLACK
    status: GameStatus = GameStatus.PLAYING
    winner: Stone | None = None
    last_move: Position | None = None
    move_count: int = 0

    @classmethod
    def new(cls, board_size: int = BOARD_SIZE) -> "GameState":
        """Create a fresh match with an empty board, black to move."""
        return cls(board=Board(board_size))

    @property
    def is_draw(self) -> bool:
        return self.status is GameStatus.FINISHED and self.winner is None
