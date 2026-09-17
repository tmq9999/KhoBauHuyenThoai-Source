"""Wire contract tests for the bounded Pomelo inventory transport."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import os
import struct
from contextlib import asynccontextmanager
from dataclasses import asdict

import pytest

from kbht_server.adapters.pomelo_codec import (
    DATA,
    HANDSHAKE,
    HANDSHAKE_ACK,
    REQUEST,
    RESPONSE,
    decode_data,
    decode_frames,
    encode_data,
    encode_frame,
)
from kbht_server.adapters.pomelo_transport import PomeloInventoryServer
from kbht_server.auth import SessionService
from pg_lab import ACCOUNT_IDS, CONTENT_ID
from test_fixed_boxes import box_lab, draft_boxes
from test_native_inventory import envelope


def _ws_frame(payload: bytes, *, opcode: int = 2, mask: bytes = b"test") -> bytes:
    length = len(payload)
    if length < 126:
        head = bytes([0x80 | opcode, 0x80 | length])
    elif length <= 0xFFFF:
        head = bytes([0x80 | opcode, 0x80 | 126]) + struct.pack("!H", length)
    else:
        head = bytes([0x80 | opcode, 0x80 | 127]) + struct.pack("!Q", length)
    return head + mask + bytes(value ^ mask[index % 4] for index, value in enumerate(payload))


def _ws_extended(payload: bytes, marker: int, encoded_length: int,
                 *, mask: bytes = b"test") -> bytes:
    size = struct.pack("!H", encoded_length) if marker == 126 else struct.pack("!Q", encoded_length)
    return bytes((0x82, 0x80 | marker)) + size + mask + bytes(
        value ^ mask[index % 4] for index, value in enumerate(payload)
    )


async def _read_exact(reader: asyncio.StreamReader, size: int) -> bytes:
    value = await reader.readexactly(size)
    return value


async def _read_ws(reader: asyncio.StreamReader) -> tuple[int, bytes]:
    first, second = await _read_exact(reader, 2)
    assert not (first & 0x80) == 0, "server replies must not be fragmented"
    opcode = first & 0x0F
    length = second & 0x7F
    if length == 126:
        length = struct.unpack("!H", await _read_exact(reader, 2))[0]
    elif length == 127:
        length = struct.unpack("!Q", await _read_exact(reader, 8))[0]
    return opcode, await _read_exact(reader, length)


async def _connect(server, *, origin: str | None = None):
    reader, writer = await asyncio.open_connection(*server.address)
    key = base64.b64encode(os.urandom(16)).decode()
    headers = [
        "GET /inventory HTTP/1.1",
        "Host: 127.0.0.1",
        "Upgrade: websocket",
        "Connection: Upgrade",
        "Sec-WebSocket-Version: 13",
        f"Sec-WebSocket-Key: {key}",
    ]
    if origin:
        headers.append(f"Origin: {origin}")
    writer.write(("\r\n".join(headers) + "\r\n\r\n").encode())
    await writer.drain()
    response = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), 2)
    assert response.startswith(b"HTTP/1.1 101")
    expected = base64.b64encode(hashlib.sha1(
        key.encode() + b"258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
    ).digest())
    assert b"Sec-WebSocket-Accept: " + expected + b"\r\n" in response
    return reader, writer


def _handshake(token: str, hello: dict) -> bytes:
    return encode_frame(HANDSHAKE, json.dumps({
        "sys": {"type": "kbht-inventory", "version": "1"},
        "user": {"token": token, "hello": hello},
    }, separators=(",", ":")).encode())


def _hello(player: int = 10001) -> dict:
    return {
        "protocolVersion": 1,
        "capabilities": ["native-inventory-v1"],
        "playerId": player,
        "serverId": 1,
        "contentVersionId": str(CONTENT_ID),
    }


def _player_envelope(lab, player: int, *, key: str, count: int = 1) -> dict:
    bag = str(next(row["id"] for row in lab.items(player) if row["kind_id"] == 321))
    command = lab.inventory_command(
        player, {"bagIndex": bag, "itemCount": count}, key=key,
        route="logic.playerHandler.useItem",
    )
    result = json.loads(json.dumps(asdict(command), default=str))
    result.pop("account_id")
    return result


async def _ready(server, token: str, *, player: int = 10001):
    reader, writer = await _connect(server)
    writer.write(_ws_frame(_handshake(token, _hello(player))))
    await writer.drain()
    _, body = await _read_ws(reader)
    assert json.loads(decode_frames(body)[0][1])["code"] == 200
    writer.write(_ws_frame(encode_frame(HANDSHAKE_ACK, b"")))
    await writer.drain()
    return reader, writer


async def _request(reader, writer, request_id: int, route: str, payload: dict):
    writer.write(_ws_frame(encode_frame(DATA, encode_data(
        REQUEST, request_id=request_id, route=route, payload=payload,
    ))))
    await writer.drain()
    _, body = await _read_ws(reader)
    message = decode_data(decode_frames(body)[0][1])
    assert message.request_id == request_id
    return message.payload


@asynccontextmanager
async def _running(lab):
    server = PomeloInventoryServer(lab.engine, host="127.0.0.1", port=0)
    await server.start()
    try:
        yield server
    finally:
        await server.close()


def test_handshake_ack_use_item_and_request_id_echo(box_lab):
    asyncio.run(_test_handshake_ack_use_item_and_request_id_echo(box_lab))


async def _test_handshake_ack_use_item_and_request_id_echo(box_lab):
    token = SessionService(box_lab.engine).issue(ACCOUNT_IDS[10001])
    request = envelope(box_lab)
    async with _running(box_lab) as server:
        reader, writer = await _connect(server)
        writer.write(_ws_frame(_handshake(token, _hello())))
        await writer.drain()
        opcode, body = await _read_ws(reader)
        assert opcode == 2
        package_type, payload = decode_frames(body)[0]
        assert package_type == HANDSHAKE
        negotiation = json.loads(payload)
        assert negotiation["code"] == 200
        assert negotiation["sys"] == {"heartbeat": 0, "dict": {}, "protos": {}}
        assert negotiation["user"]["allowedRoutes"] == ["logic.playerHandler.useItem"]

        writer.write(_ws_frame(encode_frame(HANDSHAKE_ACK, b"")))
        await writer.drain()
        writer.write(_ws_frame(encode_frame(3, b"")))
        await writer.drain()
        _, heartbeat = await _read_ws(reader)
        assert decode_frames(heartbeat) == [(3, b"")]
        writer.write(_ws_frame(encode_frame(DATA, encode_data(
            REQUEST, request_id=41, route=request["route"], payload=request,
        ))))
        await writer.drain()
        _, body = await _read_ws(reader)
        package_type, payload = decode_frames(body)[0]
        assert package_type == DATA
        message = decode_data(payload)
        assert message.type == RESPONSE and message.request_id == 41
        assert message.payload["code"] == 200
        assert message.payload["result"]["_temp"]["entityCountMap"]["49902"] == 6
        writer.close()
        await writer.wait_closed()


def test_data_before_ack_and_non_loopback_origin_fail_closed(box_lab):
    asyncio.run(_test_data_before_ack_and_non_loopback_origin_fail_closed(box_lab))


async def _test_data_before_ack_and_non_loopback_origin_fail_closed(box_lab):
    token = SessionService(box_lab.engine).issue(ACCOUNT_IDS[10001])
    async with _running(box_lab) as server:
        reader, writer = await _connect(server)
        writer.write(_ws_frame(_handshake(token, _hello())))
        await writer.drain()
        await _read_ws(reader)
        writer.write(_ws_frame(encode_frame(DATA, encode_data(
            REQUEST, request_id=1, route="connector.inventoryHandler.resync", payload={},
        ))))
        await writer.drain()
        assert await reader.read(2) == b""
        writer.close()
        await writer.wait_closed()

        bad_reader, bad_writer = await asyncio.open_connection(*server.address)
        bad_writer.write(("GET /inventory HTTP/1.1\r\nHost: 127.0.0.1\r\n"
                          "Upgrade: websocket\r\nConnection: Upgrade\r\n"
                          "Sec-WebSocket-Version: 13\r\nSec-WebSocket-Key: "
                          + base64.b64encode(os.urandom(16)).decode()
                          + "\r\nOrigin: https://evil.example\r\n\r\n").encode())
        await bad_writer.drain()
        assert b" 403 " in await bad_reader.read(1024)
        bad_writer.close()
        await bad_writer.wait_closed()

        denied_reader, denied_writer = await _connect(server)
        denied_writer.write(_ws_frame(_handshake("invalid-session", _hello())))
        await denied_writer.drain()
        assert await denied_reader.read(2) == b""
        denied_writer.close()
        await denied_writer.wait_closed()


def test_resync_route_and_cli_argument_safety(box_lab):
    asyncio.run(_test_resync_route_and_cli_argument_safety(box_lab))


async def _test_resync_route_and_cli_argument_safety(box_lab):
    from kbht_server.cli import main

    with pytest.raises(SystemExit):
        main(["serve-inventory", "--environment", "test", "--host", "0.0.0.0"])
    defaults = PomeloInventoryServer(box_lab.engine)
    assert defaults.host == "127.0.0.1" and defaults.port == 21002
    token = SessionService(box_lab.engine).issue(ACCOUNT_IDS[10001])
    async with _running(box_lab) as server:
        reader, writer = await _connect(server, origin="http://localhost:8080")
        writer.write(_ws_frame(_handshake(token, _hello())))
        await writer.drain()
        await _read_ws(reader)
        writer.write(_ws_frame(encode_frame(HANDSHAKE_ACK, b"")))
        writer.write(_ws_frame(encode_frame(DATA, encode_data(
            REQUEST, request_id=2, route="connector.inventoryHandler.resync", payload={},
        ))))
        await writer.drain()
        _, body = await _read_ws(reader)
        message = decode_data(decode_frames(body)[0][1])
        assert message.payload["code"] == 200
        assert message.payload["result"]["snapshotMode"] == "replace-bag"
        writer.close()
        await writer.wait_closed()


def test_malformed_unmasked_and_oversized_frames_fail_closed(box_lab):
    asyncio.run(_test_malformed_unmasked_and_oversized_frames_fail_closed(box_lab))


async def _test_malformed_unmasked_and_oversized_frames_fail_closed(box_lab):
    async with _running(box_lab) as server:
        for frame in (
            b"\x82\x04nope",  # client frame is not masked
            bytes((0x02, 0x80)) + b"test",  # fragmented frame
            bytes((0x81, 0x80)) + b"test",  # text frame
            bytes((0xC2, 0x80)) + b"test",  # RSV1 set without an extension
            bytes((0x82, 0xFF)) + struct.pack("!Q", 65537) + b"test",  # oversized
        ):
            reader, writer = await _connect(server)
            writer.write(frame)
            await writer.drain()
            assert await reader.read(2) == b""
            writer.close()
            await writer.wait_closed()

        reader, writer = await asyncio.open_connection(*server.address)
        writer.write((b"GET /inventory HTTP/1.1\r\nHost: 127.0.0.1\r\n"
                      b"X-Fill: " + b"x" * 17000 + b"\r\n\r\n"))
        await writer.drain()
        assert await reader.read(1024) == b""
        writer.close()
        await writer.wait_closed()

        token = SessionService(box_lab.engine).issue(ACCOUNT_IDS[10001])
        handshake = _handshake(token, _hello())

        # RFC 6455 requires the shortest available length encoding.
        reader, writer = await _connect(server)
        writer.write(_ws_extended(handshake, 127, len(handshake)))
        await writer.drain()
        assert await asyncio.wait_for(reader.read(2), 2) == b""
        writer.close()
        await writer.wait_closed()

        reader, writer = await _connect(server)
        writer.write(_ws_frame(handshake))
        await writer.drain()
        await _read_ws(reader)
        ack = encode_frame(HANDSHAKE_ACK, b"")
        writer.write(_ws_extended(ack, 126, len(ack)))
        await writer.drain()
        assert await asyncio.wait_for(reader.read(2), 2) == b""
        writer.close()
        await writer.wait_closed()

        reader, writer = await _connect(server)
        writer.write(bytes((0x82, 0xFF)) + struct.pack("!Q", 1 << 63) + b"test")
        await writer.drain()
        assert await asyncio.wait_for(reader.read(2), 2) == b""
        writer.close()
        await writer.wait_closed()

        # Duplicate keys and JavaScript's non-standard NaN token are not valid
        # boundary JSON even though the stdlib decoder accepts them by default.
        for invalid in (
            b'{"sys":{"type":"kbht-inventory","version":"1"},'
            b'"user":{"token":"x","token":"y","hello":{}}}',
            b'{"sys":{"type":"kbht-inventory","version":"1"},'
            b'"user":{"token":"x","hello":{"protocolVersion":NaN}}}',
        ):
            reader, writer = await _connect(server)
            writer.write(_ws_frame(encode_frame(HANDSHAKE, invalid)))
            await writer.drain()
            assert await reader.read(2) == b""
            writer.close()
            await writer.wait_closed()


def test_reconnect_replay_revocation_and_two_account_isolation(box_lab):
    asyncio.run(_test_reconnect_replay_revocation_and_two_account_isolation(box_lab))


async def _test_reconnect_replay_revocation_and_two_account_isolation(box_lab):
    sessions = SessionService(box_lab.engine)
    token_a = sessions.issue(ACCOUNT_IDS[10001])
    token_b = sessions.issue(ACCOUNT_IDS[10002])
    request_a = _player_envelope(box_lab, 10001, key="wire-replay", count=2)
    request_b = _player_envelope(box_lab, 10002, key="wire-account-b")
    route = "logic.playerHandler.useItem"
    async with _running(box_lab) as server:
        reader, writer = await _ready(server, token_a)
        first = await _request(reader, writer, 8, route, request_a)
        assert first["code"] == 200
        bag_a = request_a["payload"]["bagIndex"]
        assert first["result"]["bag"]["items"][bag_a] is None
        writer.close()
        await writer.wait_closed()

        reader, writer = await _ready(server, token_a)
        replay = await _request(reader, writer, 99, route, request_a)
        assert replay == first
        assert box_lab.item_quantity(10001, 49902) == 12
        sessions.revoke(token_a)
        denied = await _request(
            reader, writer, 100, "connector.inventoryHandler.resync", {},
        )
        assert denied == {"code": 500, "error": {"code": "UNAUTHENTICATED"}}
        assert token_a not in json.dumps(denied)
        writer.close()
        await writer.wait_closed()

        reader, writer = await _ready(server, token_b, player=10002)
        result_b = await _request(reader, writer, 7, route, request_b)
        assert result_b["code"] == 200
        assert box_lab.item_quantity(10002, 49902) == 6
        assert box_lab.item_quantity(10001, 49902) == 12
        gm = await _request(reader, writer, 9, "logic.gmHandler.addItem", {})
        assert gm == {"code": 500, "error": {"code": "NOT_IMPLEMENTED"}}
        writer.close()
        await writer.wait_closed()


def test_close_cancels_idle_client_cleanly(box_lab):
    asyncio.run(_test_close_cancels_idle_client_cleanly(box_lab))


async def _test_close_cancels_idle_client_cleanly(box_lab):
    server = PomeloInventoryServer(box_lab.engine, host="127.0.0.1", port=0)
    await server.start()
    reader, writer = await _connect(server)
    await server.close()
    assert await asyncio.wait_for(reader.read(), 2) == b""
    writer.close()
    await writer.wait_closed()


def test_disconnect_does_not_cancel_or_repeat_admitted_command(box_lab):
    asyncio.run(_test_disconnect_does_not_cancel_or_repeat_admitted_command(box_lab))


async def _test_disconnect_does_not_cancel_or_repeat_admitted_command(box_lab):
    from threading import Event
    from sqlalchemy import event

    entered, release = Event(), Event()
    token = SessionService(box_lab.engine).issue(ACCOUNT_IDS[10001])
    request = _player_envelope(box_lab, 10001, key="wire-disconnect")

    def pause(_connection, _cursor, statement, _parameters, _context, _executemany):
        if statement.startswith("INSERT INTO command_receipts"):
            entered.set()
            assert release.wait(5)

    event.listen(box_lab.engine, "before_cursor_execute", pause)
    try:
        async with _running(box_lab) as server:
            reader, writer = await _ready(server, token)
            writer.write(_ws_frame(encode_frame(DATA, encode_data(
                REQUEST, request_id=17, route=request["route"], payload=request,
            ))))
            await writer.drain()
            assert await asyncio.to_thread(entered.wait, 5)
            writer.close()
            await writer.wait_closed()
            release.set()

            # The exact durable envelope, not request id 17, controls replay.
            reader, writer = await _ready(server, token)
            replay = await _request(reader, writer, 88, request["route"], request)
            assert replay["code"] == 200
            assert box_lab.item_quantity(10001, 49902) == 6
            writer.close()
            await writer.wait_closed()
    finally:
        release.set()
        event.remove(box_lab.engine, "before_cursor_execute", pause)


def test_unexpected_fault_is_sanitized_then_connection_closes(box_lab, monkeypatch):
    asyncio.run(_test_unexpected_fault_is_sanitized_then_connection_closes(box_lab, monkeypatch))


async def _test_unexpected_fault_is_sanitized_then_connection_closes(box_lab, monkeypatch):
    from kbht_server.adapters.inventory_connection import InventoryConnection

    token = SessionService(box_lab.engine).issue(ACCOUNT_IDS[10001])
    request = _player_envelope(box_lab, 10001, key="wire-internal-error")

    def fail(_self, _envelope):
        raise RuntimeError("SELECT secret FROM sessions token=" + token)

    monkeypatch.setattr(InventoryConnection, "execute", fail)
    async with _running(box_lab) as server:
        reader, writer = await _ready(server, token)
        response = await _request(reader, writer, 3, request["route"], request)
        assert response == {"code": 500, "error": {"code": "INTERNAL_ERROR"}}
        assert token not in json.dumps(response) and "SELECT" not in json.dumps(response)
        assert await asyncio.wait_for(reader.read(), 2) == b""
        writer.close()
        await writer.wait_closed()


def test_unexpected_handshake_fault_never_reaches_loop_exception_context(box_lab, monkeypatch):
    asyncio.run(_test_unexpected_handshake_fault_never_reaches_loop_exception_context(box_lab, monkeypatch))


async def _test_unexpected_handshake_fault_never_reaches_loop_exception_context(box_lab, monkeypatch):
    from kbht_server.adapters.inventory_connection import InventoryConnection

    token = SessionService(box_lab.engine).issue(ACCOUNT_IDS[10001])
    secret = "SELECT password_hash token=" + token
    contexts = []
    loop = asyncio.get_running_loop()
    previous = loop.get_exception_handler()

    def fail(_self, _token, _hello):
        raise RuntimeError(secret)

    monkeypatch.setattr(InventoryConnection, "negotiate", fail)
    loop.set_exception_handler(lambda _loop, context: contexts.append(context))
    try:
        server = PomeloInventoryServer(box_lab.engine, host="127.0.0.1", port=0)
        await server.start()
        reader, writer = await _connect(server)
        writer.write(_ws_frame(_handshake(token, _hello())))
        await writer.drain()
        assert await asyncio.wait_for(reader.read(), 2) == b""
        writer.close()
        await writer.wait_closed()
        await server.close()
        await asyncio.sleep(0)
        assert contexts == []
        assert secret not in repr(contexts) and token not in repr(contexts)
    finally:
        loop.set_exception_handler(previous)
