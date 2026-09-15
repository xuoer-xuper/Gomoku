"""Room-code encoding tests."""

import pytest

from gomoku.communication.room_code import (
    RoomCodeError,
    decode_endpoint,
    encode_endpoint,
    generate_room_code,
    normalize_room_code,
)


def test_random_room_codes_differ() -> None:
    codes = {generate_room_code() for _ in range(20)}
    assert len(codes) >= 18
    for code in codes:
        assert normalize_room_code(code) == code
        assert len(code.replace("-", "")) == 6


def test_roundtrip_lan_address() -> None:
    code = encode_endpoint("192.168.1.8", 8765)
    assert "-" in code
    ip, port = decode_endpoint(code)
    assert ip == "192.168.1.8"
    assert port == 8765


def test_decode_accepts_lowercase_and_spaces() -> None:
    code = encode_endpoint("10.0.0.12", 9000)
    ip, port = decode_endpoint(f"  {code.lower()}  ")
    assert ip == "10.0.0.12"
    assert port == 9000


def test_invalid_code_rejected() -> None:
    with pytest.raises(RoomCodeError):
        decode_endpoint("ABC")
    with pytest.raises(RoomCodeError):
        decode_endpoint("!!!!!-----")
