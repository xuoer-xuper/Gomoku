"""Newline-delimited JSON protocol used by client and server."""

from __future__ import annotations

import json
from enum import Enum
from typing import Any

from gomoku.config import ENCODING
from gomoku.data.position import Position
from gomoku.data.stone import Stone
from gomoku.exceptions import ProtocolError
from gomoku.service.game_service import MoveResult


class MessageType(str, Enum):
    """Canonical message names on the wire."""

    JOIN = "join"
    JOINED = "joined"
    WAITING = "waiting"
    GAME_START = "game_start"
    PLACE = "place"
    MOVE = "move"
    INVALID = "invalid"
    GAME_OVER = "game_over"
    OPPONENT_LEFT = "opponent_left"
    ERROR = "error"
    PING = "ping"
    PONG = "pong"
    CHAT = "chat"
    UNDO_REQUEST = "undo_request"
    UNDO_REPLY = "undo_reply"
    UNDO = "undo"
    UNDO_REJECTED = "undo_rejected"
    REMATCH_REQUEST = "rematch_request"
    REMATCH_REPLY = "rematch_reply"


class Message:
    """Typed envelope with a string kind and JSON-object payload."""

    def __init__(
        self,
        msg_type: str | MessageType,
        payload: dict[str, Any] | None = None,
    ) -> None:
        if isinstance(msg_type, MessageType):
            self.type = msg_type.value
        else:
            self.type = msg_type
        self.payload = payload or {}

    def to_bytes(self) -> bytes:
        body = json.dumps(
            {"type": self.type, "payload": self.payload},
            ensure_ascii=False,
            separators=(",", ":"),
        )
        return (body + "\n").encode(ENCODING)

    @classmethod
    def from_bytes(cls, raw: bytes) -> Message:
        text = raw.decode(ENCODING).strip()
        if not text:
            raise ProtocolError("empty message")
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ProtocolError("message is not valid JSON") from exc
        if not isinstance(data, dict) or "type" not in data:
            raise ProtocolError("message missing type field")
        payload = data.get("payload") or {}
        if not isinstance(payload, dict):
            raise ProtocolError("payload must be an object")
        return cls(str(data["type"]), payload)

    @classmethod
    def join(cls, name: str) -> Message:
        return cls(MessageType.JOIN, {"name": name})

    @classmethod
    def joined(cls, player_id: str, name: str) -> Message:
        return cls(
            MessageType.JOINED,
            {"player_id": player_id, "name": name},
        )

    @classmethod
    def waiting(cls) -> Message:
        return cls(MessageType.WAITING, {"message": "等待对手加入"})

    @classmethod
    def game_start(
        cls,
        your_color: Stone,
        opponent_name: str,
        board_size: int,
    ) -> Message:
        return cls(
            MessageType.GAME_START,
            {
                "your_color": your_color.code,
                "opponent_name": opponent_name,
                "board_size": board_size,
            },
        )

    @classmethod
    def place(cls, row: int, col: int) -> Message:
        return cls(MessageType.PLACE, {"row": row, "col": col})

    @classmethod
    def from_move(cls, result: MoveResult) -> Message:
        payload: dict[str, Any] = {
            "row": result.position.row,
            "col": result.position.col,
            "color": result.stone.code,
            "next_turn": (
                result.next_turn.code if result.next_turn else None
            ),
        }
        return cls(MessageType.MOVE, payload)

    @classmethod
    def invalid(cls, reason: str) -> Message:
        return cls(MessageType.INVALID, {"reason": reason})

    @classmethod
    def game_over(cls, result: MoveResult) -> Message:
        winner = result.winner.code if result.winner else None
        reason = "draw" if result.is_draw else "five_in_a_row"
        return cls(
            MessageType.GAME_OVER,
            {
                "winner": winner,
                "reason": reason,
                "row": result.position.row,
                "col": result.position.col,
            },
        )

    @classmethod
    def opponent_left(cls) -> Message:
        return cls(MessageType.OPPONENT_LEFT, {})

    @classmethod
    def chat(cls, name: str, text: str, system: bool = False) -> Message:
        return cls(
            MessageType.CHAT,
            {"name": name, "text": text, "system": system},
        )

    @classmethod
    def undo_request(cls, name: str) -> Message:
        return cls(MessageType.UNDO_REQUEST, {"name": name})

    @classmethod
    def undo_reply(cls, accepted: bool) -> Message:
        return cls(MessageType.UNDO_REPLY, {"accepted": accepted})

    @classmethod
    def from_undo(cls, result: MoveResult) -> Message:
        return cls(
            MessageType.UNDO,
            {
                "row": result.position.row,
                "col": result.position.col,
                "color": result.stone.code,
                "next_turn": (
                    result.next_turn.code if result.next_turn else None
                ),
            },
        )

    @classmethod
    def undo_rejected(cls) -> Message:
        return cls(MessageType.UNDO_REJECTED, {})

    @classmethod
    def rematch_request(cls, name: str) -> Message:
        return cls(MessageType.REMATCH_REQUEST, {"name": name})

    @classmethod
    def rematch_reply(cls, accepted: bool) -> Message:
        return cls(
            MessageType.REMATCH_REPLY,
            {"accepted": accepted},
        )

    @classmethod
    def error(cls, message: str) -> Message:
        return cls(MessageType.ERROR, {"message": message})

    def position(self) -> Position:
        return Position(
            int(self.payload["row"]),
            int(self.payload["col"]),
        )
