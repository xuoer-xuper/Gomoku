"""Communication layer: JSON protocol, TCP server and client."""

from gomoku.communication.messages import Message, MessageType
from gomoku.communication.room_code import decode_endpoint, encode_endpoint

__all__ = [
    "Message",
    "MessageType",
    "decode_endpoint",
    "encode_endpoint",
]
