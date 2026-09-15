import json
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).parents[2] / "src"))

from pomelo_codec import (  # noqa: E402
    DATA,
    NOTIFY,
    REQUEST,
    RESPONSE,
    HANDSHAKE,
    decode_data,
    decode_frame,
    decode_frames,
    encode_data,
    encode_frame,
)


def test_outer_frame_uses_type_and_uint24_big_endian_length():
    frame = encode_frame(HANDSHAKE, b"abc")
    assert frame == b"\x01\x00\x00\x03abc"
    assert decode_frame(frame) == (HANDSHAKE, b"abc")


def test_request_round_trip_with_json_route_and_varint_id():
    body = encode_data(REQUEST, request_id=300, route="gate.gateHandler.queryEntry", payload={"uid": "u1"})
    msg = decode_data(body)
    assert msg.type == REQUEST
    assert msg.request_id == 300
    assert msg.route == "gate.gateHandler.queryEntry"
    assert msg.payload == {"uid": "u1"}
    assert json.loads(msg.payload_bytes) == {"uid": "u1"}


def test_response_round_trip_omits_route():
    body = encode_data(RESPONSE, request_id=7, payload={"code": 501, "msg": "UNKNOWN"})
    msg = decode_data(body)
    assert msg.type == RESPONSE
    assert msg.request_id == 7
    assert msg.route is None
    assert msg.payload["code"] == 501


def test_notify_requires_route_and_rejects_overlong_outer_body():
    with pytest.raises(ValueError):
        encode_data(NOTIFY, payload={})
    with pytest.raises(ValueError):
        encode_frame(DATA, b"x" * 0x1000000)


def test_decode_rejects_truncated_or_invalid_message():
    with pytest.raises(ValueError):
        decode_frame(b"\x01\x00")
    with pytest.raises(ValueError):
        decode_data(b"\x00")


def test_decode_frames_accepts_concatenated_packages_but_single_decode_stays_strict():
    first = encode_frame(HANDSHAKE, b"one")
    second = encode_frame(DATA, b"two")
    assert decode_frames(first + second) == [(HANDSHAKE, b"one"), (DATA, b"two")]
    with pytest.raises(ValueError, match="length mismatch"):
        decode_frame(first + second)


@pytest.mark.parametrize("request_id", [True, False, -1, 2**32])
def test_request_id_rejects_bool_negative_and_values_above_uint32(request_id):
    with pytest.raises(ValueError):
        encode_data(REQUEST, request_id=request_id, route="r", payload={})


def test_request_id_accepts_uint32_max_and_decoder_rejects_larger_value():
    assert decode_data(encode_data(REQUEST, request_id=2**32 - 1, route="r")).request_id == 2**32 - 1
    with pytest.raises(ValueError, match="uint32"):
        decode_data(bytes((REQUEST << 1, 0x80, 0x80, 0x80, 0x80, 0x10, 1)) + b"r")
