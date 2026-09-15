"""Win detection and move validation tests."""

import pytest

from gomoku.data.board import Board
from gomoku.data.position import Position
from gomoku.data.stone import Stone
from gomoku.exceptions import InvalidMoveError
from gomoku.service.referee import Referee


def _line(board: Board, cells: list[tuple[int, int]], stone: Stone) -> None:
    for row, col in cells:
        board.place(Position(row, col), stone)


def test_horizontal_five_wins() -> None:
    board = Board(15)
    referee = Referee()
    cells = [(7, 3), (7, 4), (7, 5), (7, 6), (7, 7)]
    _line(board, cells, Stone.BLACK)
    assert referee.winner_from(board, Position(7, 7)) is Stone.BLACK


def test_vertical_five_wins() -> None:
    board = Board(15)
    referee = Referee()
    cells = [(2, 8), (3, 8), (4, 8), (5, 8), (6, 8)]
    _line(board, cells, Stone.WHITE)
    assert referee.winner_from(board, Position(4, 8)) is Stone.WHITE


def test_diagonal_down_five_wins() -> None:
    board = Board(15)
    referee = Referee()
    cells = [(1, 1), (2, 2), (3, 3), (4, 4), (5, 5)]
    _line(board, cells, Stone.BLACK)
    assert referee.winner_from(board, Position(3, 3)) is Stone.BLACK


def test_diagonal_up_five_wins() -> None:
    board = Board(15)
    referee = Referee()
    cells = [(8, 2), (7, 3), (6, 4), (5, 5), (4, 6)]
    _line(board, cells, Stone.WHITE)
    assert referee.winner_from(board, Position(6, 4)) is Stone.WHITE


def test_four_in_a_row_is_not_win() -> None:
    board = Board(15)
    referee = Referee()
    _line(board, [(0, 0), (0, 1), (0, 2), (0, 3)], Stone.BLACK)
    assert referee.winner_from(board, Position(0, 3)) is None


def test_occupied_cell_is_invalid() -> None:
    board = Board(15)
    referee = Referee()
    board.place(Position(0, 0), Stone.BLACK)
    with pytest.raises(InvalidMoveError):
        referee.validate_move(board, Position(0, 0))


def test_out_of_board_is_invalid() -> None:
    board = Board(15)
    referee = Referee()
    with pytest.raises(InvalidMoveError):
        referee.validate_move(board, Position(20, 0))
