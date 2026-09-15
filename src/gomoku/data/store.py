"""Game-state persistence port and in-memory adapter."""

from typing import Protocol, runtime_checkable

from gomoku.data.game_state import GameState


@runtime_checkable
class IGameStore(Protocol):
    """Storage port for match snapshots (DIP)."""

    def put(self, game_id: str, state: GameState) -> None:
        """Insert or replace a match snapshot."""

    def get(self, game_id: str) -> GameState | None:
        """Return a snapshot or None when missing."""

    def delete(self, game_id: str) -> None:
        """Remove a snapshot if it exists."""


class InMemoryGameStore:
    """Process-local dictionary store. Suitable for live matches."""

    def __init__(self) -> None:
        self._items: dict[str, GameState] = {}

    def put(self, game_id: str, state: GameState) -> None:
        self._items[game_id] = state

    def get(self, game_id: str) -> GameState | None:
        return self._items.get(game_id)

    def delete(self, game_id: str) -> None:
        self._items.pop(game_id, None)
