"""Bounded stdlib asyncio WebSocket transport for the inventory adapter.

The transport deliberately owns only framing, negotiation and error mapping.
InventoryConnection remains the authenticated, durable domain boundary.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import ipaddress
import json
import struct
from urllib.parse import urlparse

from kbht_server.contracts import DomainFailure
from .inventory_connection import InventoryConnection
from .pomelo_codec import (
    DATA, HANDSHAKE, HANDSHAKE_ACK, HEARTBEAT, REQUEST, RESPONSE,
    decode_data, decode_frames, encode_data, encode_frame,
)

MAX_FRAME_SIZE = 64 * 1024
MAX_HEADER_SIZE = 16 * 1024
MAX_RESPONSE_SIZE = 1024 * 1024
MAX_CLIENTS = 32
READ_TIMEOUT = 10.0
MAX_PENDING_WORK = 32
_ALLOWED_ERRORS = {
    "VALIDATION_ERROR", "UNAUTHENTICATED", "FORBIDDEN", "NOT_FOUND", "CONFLICT",
    "INSUFFICIENT_FUNDS", "LIMIT_REACHED", "CONTENT_UNAVAILABLE", "NOT_IMPLEMENTED",
    "BATTLE_NOT_SETTLED", "RATE_LIMITED",
}


class _ProtocolError(Exception):
    pass


def _json_loads(value: bytes):
    def pairs(pairs):
        result = {}
        for key, item in pairs:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = item
        return result
    def invalid_constant(_value):
        raise ValueError("non-finite JSON number")
    return json.loads(value.decode("utf-8"), object_pairs_hook=pairs,
                      parse_constant=invalid_constant)


def _json_bytes(value) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _is_loopback_origin(value: str) -> bool:
    try:
        parsed = urlparse(value)
        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            return False
        if parsed.username or parsed.password or parsed.path not in ("", "/") or parsed.query or parsed.fragment:
            return False
        if parsed.hostname.casefold() == "localhost":
            return True
        return ipaddress.ip_address(parsed.hostname).is_loopback
    except ValueError:
        return False


class PomeloInventoryServer:
    websocket_path = '/inventory'

    def _connection(self):
        return InventoryConnection(self.engine)

    async def _ready(self, writer):
        """Optional protocol action after ACK; inventory has none."""

    def __init__(self, engine, *, host: str = "127.0.0.1", port: int = 21002):
        if host not in ("127.0.0.1", "::1"):
            raise ValueError("inventory transport is loopback-only")
        if type(port) is not int or not 0 <= port <= 65535:
            raise ValueError("invalid listen port")
        self.engine = engine
        self.host = host
        self.port = port
        self._server: asyncio.AbstractServer | None = None
        self._clients: set[asyncio.Task] = set()
        self._client_slots = asyncio.Semaphore(MAX_CLIENTS)
        self._work_slots = asyncio.Semaphore(MAX_PENDING_WORK)

    @property
    def address(self) -> tuple[str, int]:
        if self._server is None or not self._server.sockets:
            raise RuntimeError("server is not started")
        sock = self._server.sockets[0].getsockname()
        return sock[0], sock[1]

    async def start(self):
        if self._server is not None:
            return self
        self._server = await asyncio.start_server(self._accept, self.host, self.port)
        return self

    async def close(self):
        server, self._server = self._server, None
        if server is not None:
            server.close()
        clients = list(self._clients)
        for task in clients:
            task.cancel()
        if clients:
            await asyncio.gather(*clients, return_exceptions=True)
        self._clients.clear()
        if server is not None:
            await server.wait_closed()

    async def _accept(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        if self._client_slots.locked():
            writer.close()
            await writer.wait_closed()
            return
        await self._client_slots.acquire()
        task = asyncio.create_task(self._client(reader, writer))
        self._clients.add(task)
        task.add_done_callback(self._client_done)

    def _client_done(self, task: asyncio.Task):
        self._clients.discard(task)
        self._client_slots.release()
        # Retrieve every detached task result so asyncio never emits a
        # secret-bearing "Task exception was never retrieved" context.
        if not task.cancelled():
            try:
                task.exception()
            except (asyncio.CancelledError, Exception):
                pass

    async def _client(self, reader, writer):
        connection = None
        cancelled = False
        try:
            await asyncio.wait_for(self._upgrade(reader, writer), READ_TIMEOUT)
            connection = self._connection()
            state = "handshake"
            while True:
                opcode, payload = await asyncio.wait_for(self._read_ws(reader), READ_TIMEOUT)
                if opcode != 2:
                    raise _ProtocolError("unsupported websocket message")
                if len(payload) > MAX_FRAME_SIZE:
                    raise _ProtocolError("frame too large")
                packages = decode_frames(payload)
                if len(packages) != 1:
                    raise _ProtocolError("one package per websocket message required")
                package_type, body = packages[0]
                if len(body) > MAX_FRAME_SIZE:
                    raise _ProtocolError("package too large")
                if state == "handshake":
                    if package_type != HANDSHAKE:
                        raise _ProtocolError("handshake required")
                    response = await self._blocking(self._handshake, connection, body)
                    await self._send_package(writer, HANDSHAKE, response)
                    state = "ack"
                elif state == "ack":
                    if package_type != HANDSHAKE_ACK or body:
                        raise _ProtocolError("handshake ack required")
                    state = "ready"
                    await self._ready(writer)
                else:
                    if package_type == HEARTBEAT:
                        if body:
                            raise _ProtocolError("heartbeat body must be empty")
                        await self._send_package(writer, HEARTBEAT, b"")
                        continue
                    if package_type != DATA:
                        raise _ProtocolError("unsupported package type")
                    message = decode_data(body)
                    if message.type != REQUEST or not isinstance(message.request_id, int) or message.request_id == 0:
                        raise _ProtocolError("request required")
                    if not isinstance(message.route, str) or not isinstance(message.payload, dict):
                        raise _ProtocolError("invalid request")
                    await self._dispatch(writer, connection, message)
        except asyncio.CancelledError:
            cancelled = True
        except Exception:
            # Pre-authentication and transport failures fail closed. Exception
            # text is deliberately neither returned nor logged because DB/auth
            # dependencies may include SQL or credentials in their messages.
            pass
        finally:
            if connection is not None:
                try:
                    await self._blocking(connection.close)
                except asyncio.CancelledError:
                    cancelled = True
                except Exception:
                    pass
            try:
                writer.close()
                await writer.wait_closed()
            except asyncio.CancelledError:
                cancelled = True
            except Exception:
                pass
        if cancelled:
            raise asyncio.CancelledError

    async def _dispatch(self, writer, connection, message):
        try:
            payload = _json_loads(message.payload_bytes)
            if not isinstance(payload, dict):
                raise DomainFailure("VALIDATION_ERROR", "Invalid request payload")
            if message.route == "connector.inventoryHandler.resync":
                if payload != {}:
                    raise DomainFailure("VALIDATION_ERROR", "Invalid resync payload")
                result = await self._blocking(connection.resync)
                payload = {"code": 200, "result": result}
            elif message.route == "logic.playerHandler.useItem":
                envelope = payload
                if envelope.get("route") != message.route:
                    raise DomainFailure("VALIDATION_ERROR", "Route mismatch")
                result = await self._blocking(connection.execute, envelope)
                payload = {"code": 200, **result}
            else:
                raise DomainFailure("NOT_IMPLEMENTED", "Route is not registered")
        except (ValueError, UnicodeError, json.JSONDecodeError):
            payload = {"code": 500, "error": {"code": "VALIDATION_ERROR"}}
        except DomainFailure as failure:
            code = failure.code if failure.code in _ALLOWED_ERRORS else "VALIDATION_ERROR"
            payload = {"code": 500, "error": {"code": code}}
        except Exception:
            payload = {"code": 500, "error": {"code": "INTERNAL_ERROR"}}
            try:
                await self._send_response(writer, message.request_id, payload)
            finally:
                writer.close()
            return
        await self._send_response(writer, message.request_id, payload)

    async def _blocking(self, function, *args):
        """Run admitted DB work off-loop and drain it even during cancellation."""
        await self._work_slots.acquire()
        task = asyncio.create_task(asyncio.to_thread(function, *args))
        try:
            return await asyncio.shield(task)
        except asyncio.CancelledError:
            await asyncio.shield(task)
            raise
        finally:
            self._work_slots.release()

    async def _send_response(self, writer, request_id: int, payload: dict):
        body = encode_frame(DATA, encode_data(RESPONSE, request_id=request_id, payload=payload))
        if len(body) > MAX_RESPONSE_SIZE:
            raise _ProtocolError("response too large")
        await self._send_ws(writer, body)

    async def _send_package(self, writer, package_type: int, body: bytes):
        await self._send_ws(writer, encode_frame(package_type, body))

    async def _send_ws(self, writer, payload: bytes):
        if len(payload) > MAX_RESPONSE_SIZE:
            raise _ProtocolError("response too large")
        length = len(payload)
        if length < 126:
            header = bytes((0x82, length))
        elif length <= 0xFFFF:
            header = bytes((0x82, 126)) + struct.pack("!H", length)
        else:
            header = bytes((0x82, 127)) + struct.pack("!Q", length)
        writer.write(header + payload)
        await writer.drain()

    async def _upgrade(self, reader, writer):
        try:
            raw = await reader.readuntil(b"\r\n\r\n")
        except asyncio.LimitOverrunError as exc:
            raise _ProtocolError("headers too large") from exc
        if len(raw) > MAX_HEADER_SIZE:
            raise _ProtocolError("headers too large")
        lines = raw[:-4].split(b"\r\n")
        if not lines or lines[0].decode("ascii") != f"GET {self.websocket_path} HTTP/1.1":
            await self._http_error(writer, 400)
            raise _ProtocolError("invalid request")
        headers: dict[str, str] = {}
        for line in lines[1:]:
            if b":" not in line:
                await self._http_error(writer, 400)
                raise _ProtocolError("invalid header")
            name, value = line.split(b":", 1)
            key = name.decode("ascii").strip().casefold()
            if not key or key in headers:
                await self._http_error(writer, 400)
                raise _ProtocolError("duplicate header")
            headers[key] = value.decode("ascii").strip()
        connection_tokens = {
            token.strip() for token in headers.get("connection", "").casefold().split(",")
        }
        if headers.get("upgrade", "").casefold() != "websocket" or "upgrade" not in connection_tokens:
            await self._http_error(writer, 400)
            raise _ProtocolError("invalid upgrade")
        if headers.get("sec-websocket-version") != "13":
            await self._http_error(writer, 426)
            raise _ProtocolError("invalid websocket version")
        if not headers.get("host"):
            await self._http_error(writer, 400)
            raise _ProtocolError("host header required")
        try:
            key = base64.b64decode(headers["sec-websocket-key"], validate=True)
            if len(key) != 16:
                raise ValueError
        except (KeyError, ValueError, base64.binascii.Error):
            await self._http_error(writer, 400)
            raise _ProtocolError("invalid websocket key") from None
        origin = headers.get("origin")
        if origin and not _is_loopback_origin(origin):
            await self._http_error(writer, 403)
            raise _ProtocolError("origin denied")
        key_header = headers["sec-websocket-key"].encode("ascii")
        accept = base64.b64encode(hashlib.sha1(key_header + b"258EAFA5-E914-47DA-95CA-C5AB0DC85B11").digest()).decode()
        writer.write(("HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
                      f"Sec-WebSocket-Accept: {accept}\r\n\r\n").encode())
        await writer.drain()

    async def _http_error(self, writer, code: int):
        writer.write(f"HTTP/1.1 {code} Error\r\nConnection: close\r\nContent-Length: 0\r\n\r\n".encode())
        await writer.drain()

    async def _read_ws(self, reader):
        first, second = await reader.readexactly(2)
        if first & 0x70:
            raise _ProtocolError("websocket extensions are unsupported")
        if not first & 0x80:
            raise _ProtocolError("fragmented frame")
        opcode = first & 0x0F
        if opcode != 2:
            raise _ProtocolError("unsupported opcode")
        if not second & 0x80:
            raise _ProtocolError("unmasked client frame")
        marker = second & 0x7F
        length = marker
        if marker == 126:
            length = struct.unpack("!H", await reader.readexactly(2))[0]
            if length < 126:
                raise _ProtocolError("non-canonical websocket length")
        elif marker == 127:
            length = struct.unpack("!Q", await reader.readexactly(8))[0]
            if length & (1 << 63) or length < 65536:
                raise _ProtocolError("invalid websocket length")
        if length > MAX_FRAME_SIZE:
            raise _ProtocolError("frame too large")
        mask = await reader.readexactly(4)
        payload = await reader.readexactly(length)
        return opcode, bytes(value ^ mask[index % 4] for index, value in enumerate(payload))

    @staticmethod
    def _handshake(connection: InventoryConnection, body: bytes) -> bytes:
        obj = _json_loads(body)
        if not isinstance(obj, dict) or set(obj) != {"sys", "user"}:
            raise _ProtocolError("invalid handshake")
        sys = obj["sys"]
        user = obj["user"]
        if (not isinstance(sys, dict) or set(sys) != {"type", "version"} or
                sys.get("type") != "kbht-inventory" or sys.get("version") != "1" or
                not isinstance(user, dict) or set(user) != {"token", "hello"} or
                not isinstance(user.get("token"), str) or not isinstance(user.get("hello"), dict)):
            raise _ProtocolError("invalid handshake")
        negotiation = connection.negotiate(user["token"], user["hello"])
        return _json_bytes({"code": 200, "sys": {"heartbeat": 0, "dict": {}, "protos": {}}, "user": negotiation})
