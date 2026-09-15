"""Board occupancy tests."""

import pytest

from gomoku.data.board import Board
from gomoku.data.position import Position
from gomoku.data.stone import Stone


def test_empty_board_is_not_full() -> None:
    board = Board(15)
    assert board.size == 15
    assert board.is_empty(Position(7, 7))
    assert not board.is_full()


def test_place_and_get() -> None:
    board = Board(15)
    board.place(Position(0, 0), Stone.BLACK)
    assert board.get(Position(0, 0)) is Stone.BLACK
    assert not board.is_empty(Position(0, 0))


def test_place_empty_stone_rejected() -> None:
    board = Board(15)
    with pytest.raises(ValueError):
        board.place(Position(0, 0), Stone.EMPTY)


def test_out_of_bounds() -> None:
    board = Board(15)
    assert not board.in_bounds(Position(-1, 0))
    assert not board.in_bounds(Position(0, 15))
    with pytest.raises(IndexError):
        board.get(Position(15, 0))


def test_is_full() -> None:
    board = Board(5)
    for row in range(5):
        for col in range(5):
            color = Stone.BLACK if (row + col) % 2 == 0 else Stone.WHITE
            board.place(Position(row, col), color)
    assert board.is_full()
