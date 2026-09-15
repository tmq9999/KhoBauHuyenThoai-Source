"""Loopback-only HTTP and Pomelo game-entry server recovered from the VN APK."""

from __future__ import annotations

import argparse
import asyncio
import base64
import hashlib
import json
from pathlib import Path
from typing import Any

from bootstrap_server import BootstrapHTTPServer, LOOPBACK_HOST
from game_state import PlayerStore, encode_player
from pomelo_codec import DATA, HANDSHAKE, HANDSHAKE_ACK, HEARTBEAT, REQUEST, RESPONSE, decode_data, decode_frames, encode_data, encode_frame
from probe_server import _ws_encode

_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
_MAX_FRAME = 1024 * 1024
_READ_TIMEOUT = 5
_ERROR = "Yêu cầu không hợp lệ"


async def _ws_read(reader: asyncio.StreamReader) -> tuple[int, bytes] | None:
    """None means an idle connection; a partial frame times out as malformed."""
    try:
        first = await asyncio.wait_for(reader.readexactly(1), _READ_TIMEOUT)
    except asyncio.TimeoutError:
        return None
    second = await asyncio.wait_for(reader.readexactly(1), _READ_TIMEOUT)
    lead, length_byte = first[0], second[0]
    fin, rsv, opcode = bool(lead & 0x80), lead & 0x70, lead & 0x0F
    if not fin or rsv or opcode == 0:
        raise ValueError("fragmentation/extensions unsupported")
    length = length_byte & 0x7F
    if length == 126:
        length = int.from_bytes(await asyncio.wait_for(reader.readexactly(2), _READ_TIMEOUT), "big")
    elif length == 127:
        length = int.from_bytes(await asyncio.wait_for(reader.readexactly(8), _READ_TIMEOUT), "big")
    if length > _MAX_FRAME or not length_byte & 0x80:
        raise ValueError("invalid client frame")
    if opcode >= 8 and length > 125:
        raise ValueError("invalid control frame")
    mask = await asyncio.wait_for(reader.readexactly(4), _READ_TIMEOUT)
    body = bytearray(await asyncio.wait_for(reader.readexactly(length), _READ_TIMEOUT))
    for index, value in enumerate(body):
        body[index] = value ^ mask[index % 4]
    return opcode, bytes(body)


class GameServer:
    def __init__(self, manifest: Path, state: Path, *, http_port: int = 20003, static_port: int = 20001, gate_port: int = 20100, connector_port: int = 20101):
        self.store = PlayerStore(state)
        self.metadata_server: BootstrapHTTPServer | None = None
        self.http_server: BootstrapHTTPServer | None = None
        try:
            self.metadata_server = BootstrapHTTPServer.start_in_thread(manifest, static_port)
            self.http_server = BootstrapHTTPServer.start_in_thread(manifest, http_port, account_service=self.store)
        except Exception:
            if self.http_server is not None:
                self.http_server.close()
            if self.metadata_server is not None:
                self.metadata_server.close()
            self.store.close()
            raise
        self.host, self.http_port = self.http_server.host, self.http_server.port
        self.static_port = self.metadata_server.port
        self.gate_port, self.connector_port = gate_port, connector_port
        self._gate: asyncio.AbstractServer | None = None
        self._connector: asyncio.AbstractServer | None = None
        self._writers: set[asyncio.StreamWriter] = set()

    @classmethod
    async def start(cls, manifest: Path, state: Path, *, http_port: int = 20003, static_port: int = 0, gate_port: int = 20100, connector_port: int = 20101) -> "GameServer":
        server = cls(manifest, state, http_port=http_port, static_port=static_port, gate_port=gate_port, connector_port=connector_port)
        try:
            server._gate = await asyncio.start_server(lambda r, w: server._handle(r, w, "gate"), LOOPBACK_HOST, gate_port)
            server.gate_port = server._gate.sockets[0].getsockname()[1]
            server._connector = await asyncio.start_server(lambda r, w: server._handle(r, w, "connector"), LOOPBACK_HOST, connector_port)
            server.connector_port = server._connector.sockets[0].getsockname()[1]
            return server
        except Exception:
            await server.close()
            raise

    async def close(self) -> None:
        for service in (self._gate, self._connector):
            if service is not None:
                service.close()
                await service.wait_closed()
        self._gate = self._connector = None
        writers = tuple(self._writers)
        for writer in writers:
            writer.close()
        if writers:
            await asyncio.gather(*(writer.wait_closed() for writer in writers), return_exceptions=True)
        self._writers.clear()
        if self.http_server is not None:
            self.http_server.close()
        if self.metadata_server is not None:
            self.metadata_server.close()
        self.store.close()

    async def _upgrade(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> bool:
        try:
            raw = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), _READ_TIMEOUT)
            if len(raw) > 16 * 1024:
                return False
            lines = raw.decode("latin1").split("\r\n")
            if lines[0] != "GET / HTTP/1.1":
                return False
            headers: dict[str, str] = {}
            for line in lines[1:]:
                if ":" not in line:
                    continue
                key, value = line.split(":", 1)
                headers[key.strip().lower()] = value.strip()
            key = headers.get("sec-websocket-key", "")
            if headers.get("upgrade", "").lower() != "websocket" or "upgrade" not in headers.get("connection", "").lower() or headers.get("sec-websocket-version") != "13":
                return False
            if len(base64.b64decode(key.encode("ascii"), validate=True)) != 16:
                return False
            accept = base64.b64encode(hashlib.sha1((key + _GUID).encode("ascii")).digest()).decode("ascii")
            writer.write(("HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: " + accept + "\r\n\r\n").encode("ascii"))
            await writer.drain()
            return True
        except (asyncio.IncompleteReadError, asyncio.LimitOverrunError, asyncio.TimeoutError, UnicodeError, ValueError):
            return False

    async def _handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter, service: str) -> None:
        self._writers.add(writer)
        handshaken, ready, owner = False, False, None
        try:
            if not await self._upgrade(reader, writer):
                return
            while True:
                frame = await _ws_read(reader)
                if frame is None:
                    continue
                opcode, payload = frame
                if opcode == 8:
                    writer.write(_ws_encode(payload, 8)); await writer.drain(); return
                if opcode == 9:
                    writer.write(_ws_encode(payload, 10)); await writer.drain(); continue
                if opcode != 2:
                    raise ValueError("binary messages required")
                for package_type, body in decode_frames(payload):
                    if package_type == HANDSHAKE:
                        handshaken = True
                        response = {"code": 200, "sys": {"heartbeat": 0, "dict": {}, "protos": {"version": 0, "server": {}, "client": {}}}, "user": {}}
                        writer.write(_ws_encode(encode_frame(HANDSHAKE, json.dumps(response, separators=(",", ":")).encode("utf-8"))))
                        await writer.drain()
                    elif package_type == HANDSHAKE_ACK:
                        if not handshaken:
                            raise ValueError("ack before handshake")
                        ready = True
                    elif package_type == HEARTBEAT:
                        writer.write(_ws_encode(encode_frame(HEARTBEAT, b""))); await writer.drain()
                    elif package_type == DATA and ready:
                        message = decode_data(body)
                        if message.type != REQUEST or message.request_id is None or message.request_id <= 0:
                            raise ValueError("invalid request")
                        if not isinstance(message.payload, dict):
                            encoded = encode_frame(DATA, encode_data(RESPONSE, request_id=message.request_id, payload=self._error()))
                            writer.write(_ws_encode(encoded)); await writer.drain()
                            continue
                        payload_out, owner = self._dispatch(service, message.route, message.payload, owner)
                        encoded = encode_frame(DATA, encode_data(RESPONSE, request_id=message.request_id, payload=payload_out))
                        writer.write(_ws_encode(encoded)); await writer.drain()
                    elif package_type == DATA:
                        raise ValueError("data before handshake acknowledgement")
        except (asyncio.IncompleteReadError, asyncio.TimeoutError, ConnectionError, ValueError, json.JSONDecodeError):
            try:
                writer.write(_ws_encode((1002).to_bytes(2, "big"), 8)); await writer.drain()
            except (ConnectionError, RuntimeError):
                pass
        finally:
            self._writers.discard(writer)
            writer.close()
            try:
                await writer.wait_closed()
            except ConnectionError:
                pass

    def _error(self) -> dict[str, Any]:
        return {"code": 500, "msg": _ERROR}

    def _dispatch(self, service: str, route: str | None, body: dict[str, Any], owner: dict[str, str] | None) -> tuple[dict[str, Any], dict[str, str] | None]:
        if service == "gate" and route == "gate.gateHandler.queryEntry":
            uid = body.get("uid")
            if isinstance(uid, str) and uid and self.http_server is not None and self.http_server.has_uid(uid):
                print("WS gate.queryEntry 200", file=__import__("sys").stderr)
                return {"host": LOOPBACK_HOST, "port": self.connector_port}, owner
            print("WS gate.queryEntry 500", file=__import__("sys").stderr)
            return self._error(), owner
        if service != "connector":
            return self._error(), owner
        if route == "connector.entryHandler.entry":
            token, server_id, old_server_id = body.get("token"), body.get("serverId"), body.get("oldServerId")
            if isinstance(token, str) and type(server_id) is int and server_id == 1 and type(old_server_id) is int and old_server_id == 1:
                account = self.http_server.authenticate_token(token) if self.http_server is not None else None
                if account is not None:
                    print("WS connector.entry 200", file=__import__("sys").stderr)
                    return {}, account
            print("WS connector.entry 500", file=__import__("sys").stderr)
            return self._error(), None
        if owner is None:
            return self._error(), owner
        if route == "connector.playerHandler.getPlayers" and not body:
            return {"players": self.store.list_players(owner["uid"])}, owner
        if route == "connector.playerHandler.createPlayer":
            if body.get("name") != owner["name"] or not isinstance(body.get("name"), str):
                return self._error(), owner
            player = self.store.create(owner["uid"], owner["name"], 1, 1)
            owner["playerId"] = str(player["id"])
            return {"player": encode_player(player)}, owner
        if route == "connector.playerHandler.entry":
            owner.pop("playerId", None)
            player_id = body.get("playerId")
            if type(player_id) is not int or type(body.get("isReconnect")) is not bool:
                return self._error(), owner
            player = self.store.get_owned(owner["uid"], player_id)
            if player is not None:
                owner["playerId"] = str(player_id)
            return ({"player": encode_player(player)} if player is not None else self._error()), owner
        if route == "logic.playerHandler.rename":
            name = body.get("name")
            if set(body) != {"name"} or not isinstance(name, str):
                return self._error(), owner
            player_id = owner.get("playerId")
            result = self.store.rename(owner["uid"], int(player_id) if player_id is not None else 0, name)
            return (result if result is not None else self._error()), owner
        if route in ("logic.pointHandler.coin", "logic.pointHandler.gem"):
            if body:
                return self._error(), owner
            player_id = owner.get("playerId")
            result = self.store.award_recruit(owner["uid"], int(player_id) if player_id is not None else 0, route.rsplit(".", 1)[-1])
            return (result if result is not None else self._error()), owner
        return self._error(), owner


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--static-port", type=int, default=20001)
    parser.add_argument("--http-port", type=int, default=20003)
    parser.add_argument("--gate-port", type=int, default=20100)
    parser.add_argument("--connector-port", type=int, default=20101)
    args = parser.parse_args()
    async def run() -> None:
        server = await GameServer.start(args.manifest, args.state, http_port=args.http_port, static_port=args.static_port, gate_port=args.gate_port, connector_port=args.connector_port)
        print(f"game entry listening on http://{server.host}:{server.http_port}")
        try:
            await asyncio.Event().wait()
        finally:
            await server.close()
    try:
        asyncio.run(run())
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
