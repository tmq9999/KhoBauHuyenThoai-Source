"""Strict stdlib Pomelo package/message framing helpers.

This module implements the framing recovered from the VN APK statically. It
does not implement protobuf schemas; payloads are JSON UTF-8 bytes by default.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Optional

HANDSHAKE = 1
HANDSHAKE_ACK = 2
HEARTBEAT = 3
DATA = 4
KICK = 5

REQUEST = 0
NOTIFY = 1
RESPONSE = 2
PUSH = 3

_MAX_FRAME_LENGTH = 0xFFFFFF
_MAX_VARINT_BYTES = 5
_MAX_REQUEST_ID = 0xFFFFFFFF


@dataclass(frozen=True)
class DataMessage:
    type: int
    request_id: Optional[int]
    route: Optional[str]
    payload: Any
    payload_bytes: bytes
    compressed_route: bool = False
    route_code: Optional[int] = None


def encode_frame(package_type: int, body: bytes) -> bytes:
    if not isinstance(package_type, int) or not 0 <= package_type <= 0xFF:
        raise ValueError("package_type must be an unsigned byte")
    if not isinstance(body, (bytes, bytearray, memoryview)):
        raise TypeError("body must be bytes-like")
    body = bytes(body)
    if len(body) > _MAX_FRAME_LENGTH:
        raise ValueError("body exceeds uint24 frame length")
    return bytes((package_type, (len(body) >> 16) & 0xFF, (len(body) >> 8) & 0xFF, len(body) & 0xFF)) + body


def decode_frame(frame: bytes) -> tuple[int, bytes]:
    if len(frame) < 4:
        raise ValueError("truncated outer frame header")
    package_type = frame[0]
    length = int.from_bytes(frame[1:4], "big")
    if len(frame) != 4 + length:
        raise ValueError("outer frame length mismatch")
    return package_type, frame[4:]


def decode_frames(data: bytes) -> list[tuple[int, bytes]]:
    """Decode one or more concatenated Pomelo package frames."""
    frames = []
    offset = 0
    while offset < len(data):
        if len(data) - offset < 4:
            raise ValueError("truncated outer frame header")
        length = int.from_bytes(data[offset + 1:offset + 4], "big")
        end = offset + 4 + length
        if end > len(data):
            raise ValueError("outer frame length mismatch")
        frames.append((data[offset], data[offset + 4:end]))
        offset = end
    return frames


def _encode_varint(value: int) -> bytes:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= _MAX_REQUEST_ID:
        raise ValueError("request_id must be an unsigned uint32")
    out = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        out.append(byte | (0x80 if value else 0))
        if not value:
            return bytes(out)


def _decode_varint(data: bytes, offset: int) -> tuple[int, int]:
    value = 0
    shift = 0
    for count in range(_MAX_VARINT_BYTES):
        if offset >= len(data):
            raise ValueError("truncated varint")
        byte = data[offset]
        offset += 1
        value |= (byte & 0x7F) << shift
        if not byte & 0x80:
            if value > _MAX_REQUEST_ID:
                raise ValueError("varint exceeds uint32")
            return value, offset
        shift += 7
    raise ValueError("varint exceeds uint64")


def _payload_bytes(payload: Any) -> bytes:
    if payload is None:
        return b""
    if isinstance(payload, (bytes, bytearray, memoryview)):
        return bytes(payload)
    try:
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ValueError("payload must be JSON-serializable or bytes") from exc


def encode_data(
    message_type: int,
    *,
    request_id: Optional[int] = None,
    route: Optional[str] = None,
    payload: Any = None,
    compressed_route: bool = False,
    route_code: Optional[int] = None,
) -> bytes:
    if message_type not in (REQUEST, NOTIFY, RESPONSE, PUSH):
        raise ValueError("unknown Pomelo message type")
    needs_id = message_type in (REQUEST, RESPONSE)
    needs_route = message_type in (REQUEST, NOTIFY, PUSH)
    if needs_id and request_id is None:
        raise ValueError("request/response requires request_id")
    if not needs_id and request_id is not None:
        raise ValueError("notify/push cannot carry request_id")
    if needs_route and compressed_route:
        if route_code is None or not 0 <= route_code <= 0xFFFF:
            raise ValueError("compressed route requires uint16 route_code")
        if route is not None:
            raise ValueError("compressed route cannot include route string")
    elif needs_route and not route:
        raise ValueError("message requires route")
    elif not needs_route and (route is not None or compressed_route or route_code is not None):
        raise ValueError("response cannot carry route")

    out = bytearray(((message_type << 1) | (1 if compressed_route else 0),))
    if needs_id:
        out.extend(_encode_varint(request_id))
    if needs_route:
        if compressed_route:
            out.extend(route_code.to_bytes(2, "big"))
        else:
            route_bytes = route.encode("utf-8")
            if len(route_bytes) > 255:
                raise ValueError("route exceeds one-byte length")
            out.append(len(route_bytes))
            out.extend(route_bytes)
    out.extend(_payload_bytes(payload))
    return bytes(out)


def decode_data(data: bytes, route_dict: Optional[dict[int, str]] = None) -> DataMessage:
    if not data:
        raise ValueError("empty data message")
    flag = data[0]
    message_type = flag >> 1
    compressed_route = bool(flag & 1)
    if message_type not in (REQUEST, NOTIFY, RESPONSE, PUSH):
        raise ValueError("unknown Pomelo message type")
    offset = 1
    request_id = None
    if message_type in (REQUEST, RESPONSE):
        request_id, offset = _decode_varint(data, offset)
    route = None
    route_code = None
    if message_type in (REQUEST, NOTIFY, PUSH):
        if compressed_route:
            if offset + 2 > len(data):
                raise ValueError("truncated compressed route")
            route_code = int.from_bytes(data[offset:offset + 2], "big")
            offset += 2
            route = (route_dict or {}).get(route_code)
        else:
            if offset >= len(data):
                raise ValueError("truncated route length")
            route_length = data[offset]
            offset += 1
            if offset + route_length > len(data):
                raise ValueError("truncated route")
            try:
                route = data[offset:offset + route_length].decode("utf-8")
            except UnicodeDecodeError as exc:
                raise ValueError("route is not valid UTF-8") from exc
            offset += route_length
    payload_bytes = data[offset:]
    payload: Any
    if payload_bytes:
        try:
            payload = json.loads(payload_bytes.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            payload = payload_bytes
    else:
        payload = None
    return DataMessage(message_type, request_id, route, payload, payload_bytes, compressed_route, route_code)

