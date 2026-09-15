"""Local deterministic Pomelo/WebSocket and HTTP protocol probe.

The probe intentionally does not pretend to implement game routes. Every
application request receives an application code 500 UNKNOWN response, while
transport handshake and heartbeat behavior is implemented for client
integration tests.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading
from urllib.parse import parse_qs

from pomelo_codec import (
    DATA,
    HANDSHAKE,
    HANDSHAKE_ACK,
    HEARTBEAT,
    REQUEST,
    encode_data,
    decode_data,
    decode_frame,
    decode_frames,
    encode_frame,
)

_WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
_HTTP_ROUTES = {"/user/register", "/user/login", "/user/serverInfo", "/sdk/verifyToken"}
_MAX_TRANSPORT = 1024 * 1024
_READ_TIMEOUT = 5
_UNKNOWN_MSG = "Chưa hỗ trợ route trong probe local"


def _ws_encode(payload: bytes, opcode: int = 2) -> bytes:
    length = len(payload)
    if length < 126:
        header = bytes((0x80 | opcode, length))
    elif length <= 0xFFFF:
        header = bytes((0x80 | opcode, 126)) + length.to_bytes(2, "big")
    else:
        header = bytes((0x80 | opcode, 127)) + length.to_bytes(8, "big")
    return header + payload


async def _ws_read(reader: asyncio.StreamReader) -> tuple[int, bytes]:
    header = await reader.readexactly(2)
    first, second = header
    fin = bool(first & 0x80)
    rsv = first & 0x70
    opcode = first & 0x0F
    if rsv or not fin or opcode == 0:
        raise ValueError("probe supports unfragmented RFC6455 subset only")
    length = second & 0x7F
    if length == 126:
        length = int.from_bytes(await reader.readexactly(2), "big")
    elif length == 127:
        length = int.from_bytes(await reader.readexactly(8), "big")
    if length > 16 * 1024 * 1024:
        raise ValueError("websocket frame exceeds probe limit")
    if not second & 0x80:
        raise ValueError("client websocket frame must be masked")
    mask = await reader.readexactly(4)
    payload = bytearray(await reader.readexactly(length))
    for index in range(length):
        payload[index] ^= mask[index % 4]
    if opcode >= 8 and (not fin or length > 125):
        raise ValueError("invalid control frame")
    return opcode, bytes(payload)


class ProbeServer:
    def __init__(self, host: str = "127.0.0.1", port: int = 0, heartbeat_seconds: int = 0):
        if host not in ("127.0.0.1", "::1", "localhost"):
            raise ValueError("probe server must bind loopback")
        if heartbeat_seconds != 0:
            raise ValueError("probe heartbeat is disabled")
        self.host, self.port, self.heartbeat_seconds = host, port, heartbeat_seconds
        self._server: asyncio.AbstractServer | None = None

    async def start(self) -> "ProbeServer":
        self._server = await asyncio.start_server(self._handle_client, self.host, self.port)
        self.port = self._server.sockets[0].getsockname()[1]
        return self

    async def close(self) -> None:
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None

    async def _handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            request = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), _READ_TIMEOUT)
            headers = {}
            for line in request.decode("latin1").split("\r\n")[1:]:
                if ":" in line:
                    key, value = line.split(":", 1)
                    headers[key.strip().lower()] = value.strip()
            key = headers.get("sec-websocket-key")
            if not key or headers.get("upgrade", "").lower() != "websocket":
                writer.close()
                await writer.wait_closed()
                return
            accept = base64.b64encode(hashlib.sha1((key + _WS_GUID).encode("ascii")).digest()).decode("ascii")
            writer.write(("HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: " + accept + "\r\n\r\n").encode("ascii"))
            await writer.drain()
            while True:
                opcode, payload = await asyncio.wait_for(_ws_read(reader), _READ_TIMEOUT)
                if opcode == 8:
                    writer.write(_ws_encode(payload, 8))
                    await writer.drain()
                    break
                if opcode == 9:
                    writer.write(_ws_encode(payload, 10))
                    await writer.drain()
                    continue
                if opcode != 2:
                    continue
                if len(payload) > _MAX_TRANSPORT:
                    raise ValueError("transport payload exceeds 1MiB probe cap")
                for package_type, body in decode_frames(payload):
                    response = self._package_response(package_type, body)
                    if response is not None:
                        writer.write(_ws_encode(response))
                        await writer.drain()
        except (asyncio.IncompleteReadError, asyncio.LimitOverrunError, asyncio.TimeoutError, ConnectionError, ValueError):
            try:
                writer.write(_ws_encode((1002).to_bytes(2, "big"), 8))
                await writer.drain()
            except Exception:
                pass
            pass
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except ConnectionError:
                pass

    def _package_response(self, package_type: int, body: bytes) -> bytes | None:
        if package_type == HANDSHAKE:
            handshake = {"code": 200, "sys": {"heartbeat": self.heartbeat_seconds, "dict": {}, "protos": {"server": {}, "client": {}}}, "user": {}}
            return encode_frame(HANDSHAKE, json.dumps(handshake, separators=(",", ":")).encode())
        if package_type == HEARTBEAT:
            return encode_frame(HEARTBEAT, b"")
        if package_type == DATA:
            message = decode_data(body)
            if message.type != REQUEST:
                return None
            payload = {"code": 500, "msg": _UNKNOWN_MSG, "route": message.route, "probeStatus": "UNKNOWN"}
            return encode_frame(DATA, encode_data(2, request_id=message.request_id, payload=payload))
        if package_type == HANDSHAKE_ACK:
            return None
        return None


class _ProbeHandler(BaseHTTPRequestHandler):
    server_version = "PomeloProtocolProbe/0.1"

    def do_POST(self) -> None:  # noqa: N802
        content_type = self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
        length_header = self.headers.get("Content-Length")
        try:
            length = int(length_header) if length_header is not None else 0
        except (TypeError, ValueError):
            self._error(400, "invalid content length")
            return
        if length < 0:
            self._error(400, "invalid content length")
            return
        if length > 64 * 1024:
            self._error(413, "request body too large")
            return
        if content_type != "application/x-www-form-urlencoded":
            self._error(415, "form content type required")
            return
        self.connection.settimeout(_READ_TIMEOUT)
        try:
            raw = self.rfile.read(length)
        except TimeoutError:
            self._error(408, "request read timeout")
            return
        fields = {key: ["<redacted>"] for key in parse_qs(raw.decode("utf-8", "replace"), keep_blank_values=True)}
        if self.path in _HTTP_ROUTES:
            status, route = 200, self.path
        else:
            status, route = 404, self.path
        response = {"code": 500 if status == 200 else status, "msg": _UNKNOWN_MSG if status == 200 else "UNKNOWN", "route": route, "probeStatus": "UNKNOWN", "fields": fields}
        encoded = json.dumps(response, separators=(",", ":")).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _error(self, status: int, message: str) -> None:
        encoded = json.dumps({"code": status, "msg": message, "probeStatus": "UNKNOWN"}, separators=(",", ":")).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, *_args) -> None:
        return


class ProbeHTTPServer:
    def __init__(self, httpd: ThreadingHTTPServer, thread: threading.Thread):
        self._httpd, self._thread = httpd, thread
        self.host, self.port = httpd.server_address

    @classmethod
    def start_in_thread(cls, host: str = "127.0.0.1", port: int = 0) -> "ProbeHTTPServer":
        if host not in ("127.0.0.1", "::1", "localhost"):
            raise ValueError("probe server must bind loopback")
        httpd = ThreadingHTTPServer((host, port), _ProbeHandler)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        return cls(httpd, thread)

    def close(self) -> None:
        self._httpd.shutdown()
        self._httpd.server_close()
        self._thread.join(timeout=2)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Run local Pomelo protocol probe")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=3010)
    args = parser.parse_args()
    async def main() -> None:
        server = await ProbeServer(args.host, args.port).start()
        print(f"Pomelo WebSocket probe listening on ws://{server.host}:{server.port}")
        await asyncio.Event().wait()
    asyncio.run(main())
