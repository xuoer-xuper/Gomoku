"""Application service that applies moves to a GameState."""

from dataclasses import dataclass

from gomoku.data.game_state import GameState, GameStatus
from gomoku.data.position import Position
from gomoku.data.stone import Stone
from gomoku.exceptions import GameNotActiveError, NotYourTurnError
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
        state.move_count += 1

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
