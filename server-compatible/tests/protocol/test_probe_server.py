import asyncio
import base64
import hashlib
import json
import pathlib
import struct
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).parents[2] / "src"))

from pomelo_codec import DATA, HANDSHAKE, REQUEST, decode_data, decode_frame, encode_data, encode_frame  # noqa: E402
from probe_server import ProbeServer, ProbeHTTPServer  # noqa: E402


def _ws_frame(payload: bytes, opcode: int = 2, *, fin: bool = True, rsv: int = 0) -> bytes:
    mask = b"\x01\x02\x03\x04"
    masked = bytes(value ^ mask[index % 4] for index, value in enumerate(payload))
    if len(masked) < 126:
        length = bytes((0x80 | len(masked),))
    else:
        length = bytes((0x80 | 126,)) + struct.pack(">H", len(masked))
    return bytes([(0x80 if fin else 0) | (rsv << 4) | opcode]) + length + mask + masked


async def _read_ws_frame(reader):
    head = await reader.readexactly(2)
    length = head[1] & 0x7F
    if length == 126:
        length = struct.unpack(">H", await reader.readexactly(2))[0]
    elif length == 127:
        length = struct.unpack(">Q", await reader.readexactly(8))[0]
    return head[0] & 0x0F, await reader.readexactly(length)


def test_websocket_probe_handshakes_and_returns_unknown_route():
    asyncio.run(_test_websocket_probe_handshakes_and_returns_unknown_route())


async def _test_websocket_probe_handshakes_and_returns_unknown_route():
    server = ProbeServer()
    await server.start()
    try:
        reader, writer = await asyncio.open_connection(server.host, server.port)
        key = base64.b64encode(b"0123456789abcdef").decode()
        writer.write(("GET / HTTP/1.1\r\nHost: localhost\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Version: 13\r\nSec-WebSocket-Key: " + key + "\r\n\r\n").encode())
        await writer.drain()
        response = await reader.readuntil(b"\r\n\r\n")
        assert b"101 Switching Protocols" in response
        handshake = encode_frame(HANDSHAKE, json.dumps({"sys": {"type": "js-websocket"}}).encode())
        writer.write(_ws_frame(handshake))
        await writer.drain()
        opcode, payload = await _read_ws_frame(reader)
        assert opcode == 2
        package_type, package_body = decode_frame(payload)
        assert package_type == HANDSHAKE
        handshake_body = json.loads(package_body)
        assert handshake_body["code"] == 200
        assert handshake_body["sys"]["heartbeat"] == 0

        request = encode_frame(DATA, encode_data(REQUEST, request_id=1, route="gate.gateHandler.queryEntry", payload={"uid": "u1"}))
        writer.write(_ws_frame(request))
        await writer.drain()
        _, payload = await _read_ws_frame(reader)
        package_type, package_body = decode_frame(payload)
        assert package_type == DATA
        message = decode_data(package_body)
        assert message.payload["code"] == 500
        assert message.payload["probeStatus"] == "UNKNOWN"
        assert message.payload["route"] == "gate.gateHandler.queryEntry"
        writer.close()
        await writer.wait_closed()
    finally:
        await server.close()


def test_http_probe_routes_are_http_200_application_unknown_without_secret_echo(capsys):
    server = ProbeHTTPServer.start_in_thread()
    try:
        import http.client

        conn = http.client.HTTPConnection(server.host, server.port)
        secret = "never-reflect-this-password"
        conn.request("POST", "/user/login", f"name=n&password={secret}", {"Content-Type": "application/x-www-form-urlencoded"})
        response = conn.getresponse()
        raw_body = response.read().decode()
        body = json.loads(raw_body)
        assert response.status == 200
        assert body["code"] == 500
        assert body["msg"] == "Chưa hỗ trợ route trong probe local"
        assert body["probeStatus"] == "UNKNOWN"
        assert body["route"] == "/user/login"
        assert secret not in raw_body
        assert secret not in capsys.readouterr().err
    finally:
        server.close()


def _raw_http(host, port, request: bytes):
    import socket

    with socket.create_connection((host, port), timeout=2) as sock:
        sock.sendall(request)
        sock.shutdown(socket.SHUT_WR)
        chunks = []
        while True:
            chunk = sock.recv(4096)
            if not chunk:
                return b"".join(chunks)
            chunks.append(chunk)


@pytest.mark.parametrize(
    ("headers", "expected"),
    [
        (b"Content-Length: nope\r\nContent-Type: application/x-www-form-urlencoded\r\n", b" 400 "),
        (b"Content-Length: -1\r\nContent-Type: application/x-www-form-urlencoded\r\n", b" 400 "),
        (b"Content-Length: 65537\r\nContent-Type: application/x-www-form-urlencoded\r\n", b" 413 "),
        (b"Content-Length: 0\r\nContent-Type: application/json\r\n", b" 415 "),
    ],
)
def test_http_rejects_invalid_length_oversize_and_non_form_before_read(headers, expected):
    server = ProbeHTTPServer.start_in_thread()
    try:
        response = _raw_http(server.host, server.port, b"POST /user/login HTTP/1.1\r\nHost: localhost\r\n" + headers + b"Connection: close\r\n\r\n")
        assert expected in response.split(b"\r\n", 1)[0]
    finally:
        server.close()


def test_probe_servers_reject_non_loopback_bind_and_positive_heartbeat():
    with pytest.raises(ValueError, match="loopback"):
        ProbeServer("0.0.0.0")
    with pytest.raises(ValueError, match="disabled"):
        ProbeServer(heartbeat_seconds=1)
    with pytest.raises(ValueError, match="loopback"):
        ProbeHTTPServer.start_in_thread("0.0.0.0")


def test_websocket_rejects_fragment_and_echoes_close():
    asyncio.run(_test_websocket_rejects_fragment_and_echoes_close())


async def _open_websocket(server):
    reader, writer = await asyncio.open_connection(server.host, server.port)
    key = base64.b64encode(b"0123456789abcdef").decode()
    writer.write(("GET / HTTP/1.1\r\nHost: localhost\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Version: 13\r\nSec-WebSocket-Key: " + key + "\r\n\r\n").encode())
    await writer.drain()
    await reader.readuntil(b"\r\n\r\n")
    return reader, writer


async def _test_websocket_rejects_fragment_and_echoes_close():
    server = await ProbeServer().start()
    try:
        malformed = [
            _ws_frame(b"fragment", fin=False),
            _ws_frame(b"rsv", rsv=1),
            _ws_frame(b"continuation", opcode=0),
            _ws_frame(b"control-fragment", opcode=9, fin=False),
            _ws_frame(b"x" * 126, opcode=9),
        ]
        for frame in malformed:
            reader, writer = await _open_websocket(server)
            writer.write(frame)
            await writer.drain()
            opcode, payload = await _read_ws_frame(reader)
            assert opcode == 8
            assert payload[:2] == b"\x03\xea"  # RFC6455 protocol error 1002
            writer.close()
            await writer.wait_closed()

        reader, writer = await _open_websocket(server)
        close_payload = b"\x03\xe8bye"
        writer.write(_ws_frame(close_payload, opcode=8))
        await writer.drain()
        opcode, payload = await _read_ws_frame(reader)
        assert (opcode, payload) == (8, close_payload)
        writer.close()
        await writer.wait_closed()
    finally:
        await server.close()


def test_websocket_processes_concatenated_pomelo_packages():
    asyncio.run(_test_websocket_processes_concatenated_pomelo_packages())


async def _test_websocket_processes_concatenated_pomelo_packages():
    server = await ProbeServer().start()
    try:
        reader, writer = await _open_websocket(server)
        packages = encode_frame(HANDSHAKE, b"{}") + encode_frame(DATA, encode_data(REQUEST, request_id=9, route="r", payload={}))
        writer.write(_ws_frame(packages))
        await writer.drain()
        _, first = await _read_ws_frame(reader)
        _, second = await _read_ws_frame(reader)
        assert decode_frame(first)[0] == HANDSHAKE
        response = decode_data(decode_frame(second)[1])
        assert response.request_id == 9
        assert response.payload["code"] == 500
        writer.close()
        await writer.wait_closed()
    finally:
        await server.close()
