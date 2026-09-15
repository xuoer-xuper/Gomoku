"""Host-chosen rules for one room."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RoomSettings:
    """Parameters set when creating a room, then sent on game_start."""

    allow_undo: bool = True
    think_seconds: int = 0

    def label(self) -> str:
        think = (
            "思考不限"
            if self.think_seconds <= 0
            else f"每手 {self.think_seconds} 秒"
        )
        undo = "可悔棋" if self.allow_undo else "不可悔棋"
        return f"{undo}  ·  {think}"
