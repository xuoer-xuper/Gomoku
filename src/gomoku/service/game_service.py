"""Application service that applies moves to a GameState."""

from dataclasses import dataclass

from gomoku.data.game_state import GameState, GameStatus
from gomoku.data.position import Position
from gomoku.data.stone import Stone
from gomoku.exceptions import (
    CannotUndoError,
    GameNotActiveError,
    NotYourTurnError,
)
from gomoku.service.referee import Referee


@dataclass(frozen=True, slots=True)
class MoveResult:
    """Outcome of a single placement, consumed by the communication layer."""

    position: Position
    stone: Stone
    next_turn: Stone | None
    winner: Stone | None
    is_finished: bool
    is_draw: bool
    reason: str = ""


@dataclass(frozen=True, slots=True)
class UndoResult:
    """Stones removed to take back ``stone``'s last move."""

    removed: tuple[tuple[Position, Stone], ...]
    next_turn: Stone


class GameService:
    """Orchestrates turn order, validation and win/draw settlement.

    Depends on Referee (abstraction of rules) rather than embedding
    detection logic, following SRP and DIP.
    """

    def __init__(self, referee: Referee | None = None) -> None:
        self._referee = referee or Referee()

    def create(self, board_size: int) -> GameState:
        return GameState.new(board_size)

    def apply_move(
        self,
        state: GameState,
        stone: Stone,
        position: Position,
    ) -> MoveResult:
        """Place a stone, mutate state, and return a structured result."""
        if state.status is not GameStatus.PLAYING:
            raise GameNotActiveError("对局尚未开始或已经结束")
        if stone not in (Stone.BLACK, Stone.WHITE):
            raise NotYourTurnError("无效的执子颜色")
        if state.current_turn is not stone:
            raise NotYourTurnError("当前不是该玩家的回合")

        self._referee.validate_move(state.board, position)
        state.board.place(position, stone)
        state.last_move = position
        state.history.append(position)
        state.move_count = len(state.history)

        winner = self._referee.winner_from(state.board, position)
        if winner is not None:
            state.status = GameStatus.FINISHED
            state.winner = winner
            state.current_turn = stone
            return MoveResult(
                position=position,
                stone=stone,
                next_turn=None,
                winner=winner,
                is_finished=True,
                is_draw=False,
            )

        if state.board.is_full():
            state.status = GameStatus.FINISHED
            state.winner = None
            state.current_turn = stone
            return MoveResult(
                position=position,
                stone=stone,
                next_turn=None,
                winner=None,
                is_finished=True,
                is_draw=True,
            )

        state.current_turn = stone.opponent()
        return MoveResult(
            position=position,
            stone=stone,
            next_turn=state.current_turn,
            winner=None,
            is_finished=False,
            is_draw=False,
        )

    def undo_last(self, state: GameState) -> MoveResult:
        """Revert the latest stone and restore that player's turn."""
        result = self.undo_for(state, self._last_stone(state))
        position, stone = result.removed[0]
        return MoveResult(
            position=position,
            stone=stone,
            next_turn=result.next_turn,
            winner=None,
            is_finished=False,
            is_draw=False,
        )

    def undo_for(self, state: GameState, stone: Stone) -> UndoResult:
        """Take back ``stone``'s last move (and the reply after it, if any).

        White to move after Black just answered: undoing White removes both
        stones so it is White's turn again.
        """
        if not state.history:
            raise CannotUndoError("没有可悔的棋")
        if stone not in (Stone.BLACK, Stone.WHITE):
            raise CannotUndoError("无效的执子颜色")
        last_color = self._last_stone(state)
        count = 1 if last_color is stone else 2
        if len(state.history) < count:
            raise CannotUndoError("还没有你的落子")
        if count == 2 and self._stone_at(state, -2) is not stone:
            raise CannotUndoError("还没有你的落子")
        removed: list[tuple[Position, Stone]] = []
        for _ in range(count):
            position = state.history.pop()
            color = state.board.get(position)
            state.board.clear(position)
            removed.append((position, color))
        state.move_count = len(state.history)
        state.last_move = state.history[-1] if state.history else None
        state.status = GameStatus.PLAYING
        state.winner = None
        state.current_turn = stone
        return UndoResult(removed=tuple(removed), next_turn=stone)

    def finish(
        self,
        state: GameState,
        winner: Stone,
        reason: str,
    ) -> MoveResult:
        """End the match by resign, timeout or disconnect."""
        if state.status is not GameStatus.PLAYING:
            raise GameNotActiveError("对局尚未开始或已经结束")
        state.status = GameStatus.FINISHED
        state.winner = winner
        position = state.last_move or Position(0, 0)
        stone = winner
        return MoveResult(
            position=position,
            stone=stone,
            next_turn=None,
            winner=winner,
            is_finished=True,
            is_draw=False,
            reason=reason,
        )

    def _last_stone(self, state: GameState) -> Stone:
        return self._stone_at(state, -1)

    def _stone_at(self, state: GameState, index: int) -> Stone:
        if not state.history:
            raise CannotUndoError("没有可悔的棋")
        real = index if index >= 0 else len(state.history) + index
        if real < 0 or real >= len(state.history):
            raise CannotUndoError("没有可悔的棋")
        return Stone.BLACK if real % 2 == 0 else Stone.WHITE

    def restart(self, board_size: int) -> GameState:
        return GameState.new(board_size)
