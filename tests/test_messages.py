"""JSON protocol encode/decode tests."""

import pytest

from gomoku.communication.messages import Message, MessageType
from gomoku.data.position import Position
from gomoku.data.stone import Stone
from gomoku.exceptions import ProtocolError
from gomoku.service.game_service import MoveResult


def test_roundtrip_join() -> None:
    original = Message.join("Alice")
    restored = Message.from_bytes(original.to_bytes())
    assert restored.type == MessageType.JOIN.value
    assert restored.payload["name"] == "Alice"


def test_move_message_from_result() -> None:
    result = MoveResult(
        position=Position(7, 7),
        stone=Stone.BLACK,
        next_turn=Stone.WHITE,
        winner=None,
        is_finished=False,
        is_draw=False,
    )
    message = Message.from_move(result)
    assert message.type == MessageType.MOVE.value
    assert message.position() == Position(7, 7)


def test_invalid_json_raises() -> None:
    with pytest.raises(ProtocolError):
        Message.from_bytes(b"not-json\n")
