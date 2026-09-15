"""Turn order, win and draw settlement tests."""

import pytest

from gomoku.data.game_state import GameStatus
from gomoku.data.position import Position
from gomoku.data.stone import Stone
from gomoku.exceptions import (
    CannotUndoError,
    GameNotActiveError,
    NotYourTurnError,
)
from gomoku.service.game_service import GameService
from gomoku.service.referee import Referee


def test_black_moves_first_then_white() -> None:
    service = GameService()
    state = service.create(15)
    first = service.apply_move(state, Stone.BLACK, Position(7, 7))
    assert first.next_turn is Stone.WHITE
    assert state.current_turn is Stone.WHITE
    second = service.apply_move(state, Stone.WHITE, Position(7, 8))
    assert second.next_turn is Stone.BLACK


def test_wrong_turn_rejected() -> None:
    service = GameService()
    state = service.create(15)
    with pytest.raises(NotYourTurnError):
        service.apply_move(state, Stone.WHITE, Position(0, 0))


def test_win_finishes_match() -> None:
    service = GameService()
    state = service.create(15)
    black = [(7, 0), (7, 1), (7, 2), (7, 3), (7, 4)]
    white = [(8, 0), (8, 1), (8, 2), (8, 3)]
    for index in range(4):
        service.apply_move(state, Stone.BLACK, Position(*black[index]))
        service.apply_move(state, Stone.WHITE, Position(*white[index]))
    result = service.apply_move(state, Stone.BLACK, Position(*black[4]))
    assert result.is_finished
    assert result.winner is Stone.BLACK
    assert state.is_draw is False
    with pytest.raises(GameNotActiveError):
        service.apply_move(state, Stone.WHITE, Position(0, 0))


def test_undo_restores_turn_and_clears_stone() -> None:
    service = GameService()
    state = service.create(15)
    service.apply_move(state, Stone.BLACK, Position(7, 7))
    result = service.undo_last(state)
    assert result.next_turn is Stone.BLACK
    assert state.board.is_empty(Position(7, 7))
    assert state.history == []
    with pytest.raises(CannotUndoError):
        service.undo_last(state)


def test_undo_for_takes_back_own_move_after_reply() -> None:
    service = GameService()
    state = service.create(15)
    service.apply_move(state, Stone.BLACK, Position(7, 7))
    service.apply_move(state, Stone.WHITE, Position(7, 8))
    service.apply_move(state, Stone.BLACK, Position(8, 8))
    result = service.undo_for(state, Stone.WHITE)
    assert len(result.removed) == 2
    assert result.next_turn is Stone.WHITE
    assert state.current_turn is Stone.WHITE
    assert state.board.is_empty(Position(8, 8))
    assert state.board.is_empty(Position(7, 8))
    assert not state.board.is_empty(Position(7, 7))


def test_undo_after_win_resumes_match() -> None:
    service = GameService()
    state = service.create(15)
    black = [(7, 0), (7, 1), (7, 2), (7, 3), (7, 4)]
    white = [(8, 0), (8, 1), (8, 2), (8, 3)]
    for index in range(4):
        service.apply_move(state, Stone.BLACK, Position(*black[index]))
        service.apply_move(state, Stone.WHITE, Position(*white[index]))
    service.apply_move(state, Stone.BLACK, Position(*black[4]))
    service.undo_last(state)
    assert state.status is GameStatus.PLAYING
    assert state.winner is None
    assert state.current_turn is Stone.BLACK


def test_draw_when_board_full_without_winner() -> None:
    referee = Referee(win_length=6)
    service = GameService(referee)
    state = service.create(5)
    turn = Stone.BLACK
    for row in range(5):
        cols = range(5) if row % 2 == 0 else range(4, -1, -1)
        for col in cols:
            result = service.apply_move(state, turn, Position(row, col))
            turn = turn.opponent()
    assert result.is_finished
    assert result.is_draw
    assert state.winner is None
