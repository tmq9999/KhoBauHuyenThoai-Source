import asyncio
import base64
import gzip
import http.client
import json
import pathlib
import struct
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parents[2] / "src"))

from game_server import GameServer  # noqa: E402
from pomelo_codec import DATA, HANDSHAKE, HANDSHAKE_ACK, REQUEST, decode_data, decode_frame, encode_data, encode_frame  # noqa: E402


def _manifest():
    return {
        "version": "1.0.0.02", "host": "127.0.0.1:20001",
        "remoteVersionUrl": "http://127.0.0.1:20001/update/version.manifest",
        "remoteManifestUrl": "http://127.0.0.1:20001/update/project.manifest",
        "packageUrl": "http://127.0.0.1:20001/update/1.0.0.02", "assets": {},
    }


def _login(server, name="alice", password="secret"):
    connection = http.client.HTTPConnection(server.host, server.http_port, timeout=2)
    try:
        connection.request("POST", "/user/login", f"name={name}&password={password}", {"Content-Type": "application/x-www-form-urlencoded"})
        response = connection.getresponse()
        assert response.status == 200
        return json.loads(response.read())
    finally:
        connection.close()


def _masked_frame(payload, opcode=2):
    mask = b"\x01\x02\x03\x04"
    masked = bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))
    if len(masked) < 126:
        length = bytes((0x80 | len(masked),))
    else:
        length = bytes((0x80 | 126,)) + struct.pack(">H", len(masked))
    return bytes((0x80 | opcode,)) + length + mask + masked


async def _read_frame(reader):
    head = await reader.readexactly(2)
    length = head[1] & 0x7F
    if length == 126:
        length = int.from_bytes(await reader.readexactly(2), "big")
    elif length == 127:
        length = int.from_bytes(await reader.readexactly(8), "big")
    return head[0] & 0x0F, await reader.readexactly(length)


async def _open_and_ack(port):
    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    key = base64.b64encode(b"0123456789abcdef").decode()
    writer.write(("GET / HTTP/1.1\r\nHost: localhost\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Version: 13\r\nSec-WebSocket-Key: " + key + "\r\n\r\n").encode())
    await writer.drain()
    assert b"101 Switching Protocols" in await reader.readuntil(b"\r\n\r\n")
    writer.write(_masked_frame(encode_frame(HANDSHAKE, b'{"sys":{"protoVersion":0}}')))
    await writer.drain()
    opcode, reply = await _read_frame(reader)
    assert opcode == 2
    package_type, body = decode_frame(reply)
    assert package_type == HANDSHAKE
    handshake = json.loads(body)
    assert handshake == {"code": 200, "sys": {"heartbeat": 0, "dict": {}, "protos": {"version": 0, "server": {}, "client": {}}}, "user": {}}
    writer.write(_masked_frame(encode_frame(HANDSHAKE_ACK, b"")))
    await writer.drain()
    return reader, writer


async def _request(reader, writer, request_id, route, payload):
    package = encode_frame(DATA, encode_data(REQUEST, request_id=request_id, route=route, payload=payload))
    writer.write(_masked_frame(package))
    await writer.drain()
    opcode, raw = await _read_frame(reader)
    assert opcode == 2
    kind, body = decode_frame(raw)
    assert kind == DATA
    result = decode_data(body)
    assert result.request_id == request_id
    return result.payload


def test_http_login_then_gate_connector_create_and_reconnect_over_real_sockets(tmp_path):
    asyncio.run(_game_flow(tmp_path))


async def _game_flow(tmp_path):
    manifest = tmp_path / "project.manifest"
    manifest.write_text(json.dumps(_manifest()), encoding="utf-8")
    server = await GameServer.start(manifest, tmp_path / "players.sqlite3", http_port=0, gate_port=0, connector_port=0)
    try:
        account = _login(server)
        gate_reader, gate_writer = await _open_and_ack(server.gate_port)
        lookup = await _request(gate_reader, gate_writer, 41, "gate.gateHandler.queryEntry", {"uid": account["uid"]})
        assert lookup == {"host": "127.0.0.1", "port": server.connector_port}
        gate_writer.close(); await gate_writer.wait_closed()

        reader, writer = await _open_and_ack(server.connector_port)
        assert await _request(reader, writer, 79, "connector.entryHandler.entry", {"token": account["token"], "serverId": 1, "oldServerId": 1}) == {}
        assert await _request(reader, writer, 83, "connector.playerHandler.getPlayers", {}) == {"players": []}
        created = await _request(reader, writer, 131, "connector.playerHandler.createPlayer", {"name": "alice"})
        player = json.loads(gzip.decompress(base64.b64decode(created["player"])).decode("utf-8"))
        assert player["userName"] == player["name"] == "alice"
        assert (player["gem"], player["coin"], player["level"]) == (50, 0, 1)
        assert await _request(reader, writer, 257, "connector.playerHandler.getPlayers", {}) == {"players": [{"id": player["id"]}]}
        again = await _request(reader, writer, 512, "connector.playerHandler.createPlayer", {"name": "alice"})
        assert json.loads(gzip.decompress(base64.b64decode(again["player"])).decode())["id"] == player["id"]
        writer.close(); await writer.wait_closed()
    finally:
        await server.close()


def test_rejects_bad_auth_cross_owner_and_malformed_body_without_mutation(tmp_path):
    asyncio.run(_rejection_flow(tmp_path))


async def _rejection_flow(tmp_path):
    manifest = tmp_path / "project.manifest"
    manifest.write_text(json.dumps(_manifest()), encoding="utf-8")
    server = await GameServer.start(manifest, tmp_path / "players.sqlite3", http_port=0, gate_port=0, connector_port=0)
    try:
        alice, bob = _login(server, "alice"), _login(server, "bob", "pw")
        gate_reader, gate_writer = await _open_and_ack(server.gate_port)
        assert (await _request(gate_reader, gate_writer, 3, "gate.gateHandler.queryEntry", {"uid": "missing"}))["code"] == 500
        gate_writer.close(); await gate_writer.wait_closed()
        reader, writer = await _open_and_ack(server.connector_port)
        assert (await _request(reader, writer, 4, "connector.entryHandler.entry", {"token": "bad", "serverId": 1, "oldServerId": 1}))["code"] == 500
        assert (await _request(reader, writer, 5, "connector.playerHandler.getPlayers", {}))["code"] == 500
        assert (await _request(reader, writer, 6, "unknown.route", {}))["code"] == 500
        writer.close(); await writer.wait_closed()
        alice_reader, alice_writer = await _open_and_ack(server.connector_port)
        await _request(alice_reader, alice_writer, 7, "connector.entryHandler.entry", {"token": alice["token"], "serverId": 1, "oldServerId": 1})
        created = await _request(alice_reader, alice_writer, 8, "connector.playerHandler.createPlayer", {"name": "alice"})
        player_id = json.loads(gzip.decompress(base64.b64decode(created["player"])).decode())["id"]
        bob_reader, bob_writer = await _open_and_ack(server.connector_port)
        await _request(bob_reader, bob_writer, 9, "connector.entryHandler.entry", {"token": bob["token"], "serverId": 1, "oldServerId": 1})
        assert (await _request(bob_reader, bob_writer, 10, "connector.playerHandler.entry", {"playerId": player_id, "isReconnect": False}))["code"] == 500
        assert (await _request(bob_reader, bob_writer, 11, "connector.playerHandler.createPlayer", {"name": "alice"}))["code"] == 500
        alice_writer.close(); await alice_writer.wait_closed()
        bob_writer.close(); await bob_writer.wait_closed()
    finally:
        await server.close()


def test_restart_keeps_player_but_requires_the_original_password(tmp_path):
    asyncio.run(_restart_flow(tmp_path))


async def _restart_flow(tmp_path):
    manifest = tmp_path / "project.manifest"
    state = tmp_path / "players.sqlite3"
    manifest.write_text(json.dumps(_manifest()), encoding="utf-8")
    first = await GameServer.start(manifest, state, http_port=0, gate_port=0, connector_port=0)
    try:
        alice = _login(first)
        reader, writer = await _open_and_ack(first.connector_port)
        await _request(reader, writer, 1, "connector.entryHandler.entry", {"token": alice["token"], "serverId": 1, "oldServerId": 1})
        await _request(reader, writer, 2, "connector.playerHandler.createPlayer", {"name": "alice"})
        writer.close(); await writer.wait_closed()
    finally:
        await first.close()
    second = await GameServer.start(manifest, state, http_port=0, gate_port=0, connector_port=0)
    try:
        reader, writer = await _open_and_ack(second.connector_port)
        expired = await _request(reader, writer, 90, "connector.entryHandler.entry", {"token": alice["token"], "serverId": 1, "oldServerId": 1})
        assert expired == {"code": 500, "msg": "Yêu cầu không hợp lệ"}
        writer.close(); await writer.wait_closed()
        bad = _login(second, "alice", "wrong")
        assert bad["code"] == 500
        alice = _login(second)
        reader, writer = await _open_and_ack(second.connector_port)
        await _request(reader, writer, 3, "connector.entryHandler.entry", {"token": alice["token"], "serverId": 1, "oldServerId": 1})
        assert len((await _request(reader, writer, 4, "connector.playerHandler.getPlayers", {}))["players"]) == 1
        writer.close(); await writer.wait_closed()
    finally:
        await second.close()


def test_malformed_application_payloads_return_fixed_error_with_echoed_positive_id(tmp_path):
    asyncio.run(_malformed_payload_flow(tmp_path))


async def _malformed_payload_flow(tmp_path):
    manifest = tmp_path / "project.manifest"
    manifest.write_text(json.dumps(_manifest()), encoding="utf-8")
    server = await GameServer.start(manifest, tmp_path / "players.sqlite3", http_port=0, gate_port=0, connector_port=0)
    try:
        reader, writer = await _open_and_ack(server.connector_port)
        for request_id, payload in ((21, []), (22, None), (23, "scalar")):
            response = await _request(reader, writer, request_id, "connector.playerHandler.getPlayers", payload)
            assert response == {"code": 500, "msg": "Yêu cầu không hợp lệ"}
        writer.close(); await writer.wait_closed()
    finally:
        await server.close()


def test_connector_requires_handshake_ack_positive_ids_and_clears_owner_after_bad_reauth(tmp_path):
    asyncio.run(_auth_order_flow(tmp_path))


def test_first_rename_uses_current_player_and_persists_across_entry(tmp_path):
    asyncio.run(asyncio.wait_for(_rename_flow(tmp_path), 10))


def test_point_routes_return_merged_roles_drop_list_and_map_fixture(tmp_path):
    asyncio.run(asyncio.wait_for(_point_flow(tmp_path), 10))


async def _point_flow(tmp_path):
    manifest = tmp_path / "project.manifest"
    manifest.write_text(json.dumps(_manifest()), encoding="utf-8")
    server = await GameServer.start(manifest, tmp_path / "players.sqlite3", http_port=0, gate_port=0, connector_port=0)
    try:
        account = _login(server)
        reader, writer = await _open_and_ack(server.connector_port)
        await _request(reader, writer, 1, "connector.entryHandler.entry", {"token": account["token"], "serverId": 1, "oldServerId": 1})
        created = await _request(reader, writer, 2, "connector.playerHandler.createPlayer", {"name": "alice"})
        player = json.loads(gzip.decompress(base64.b64decode(created["player"])))
        coin = await _request(reader, writer, 3, "logic.pointHandler.coin", {})
        assert coin["code"] == 200 and coin["team"]["roles"]["2"]["kindId"] == 100201
        assert coin["_temp"]["dropList"] == [{"entityId": 100201, "count": 1, "extra": {"star": 1}}]
        assert await _request(reader, writer, 4, "logic.pointHandler.coin", {}) == coin
        gem = await _request(reader, writer, 5, "logic.pointHandler.gem", {})
        assert gem["team"]["roles"]["3"]["kindId"] == 100301
        assert gem["_temp"]["dropList"][0]["entityId"] == 100301
        assert (await _request(reader, writer, 6, "logic.pointHandler.coin", {"x": 1}))["code"] == 500
        stored = server.store.get_owned(account["uid"], player["id"])
        assert set(stored["team"]["roles"]) == {"1", "2", "3"}
        assert stored["smapStarMap"] == {"1": {"101": {"10101": 0, "10106": 0}}}
        writer.close(); await writer.wait_closed()
    finally:
        await server.close()


def test_rename_requires_selected_owned_player_and_resets_after_failed_entry(tmp_path, capsys):
    asyncio.run(asyncio.wait_for(_rename_session_flow(tmp_path), 10))
    captured = capsys.readouterr()
    for value in ("alice", "secret", "Nami", "Robin"):
        assert value not in captured.out + captured.err


async def _rename_session_flow(tmp_path):
    manifest = tmp_path / "project.manifest"
    manifest.write_text(json.dumps(_manifest()), encoding="utf-8")
    server = await GameServer.start(manifest, tmp_path / "players.sqlite3", http_port=0, gate_port=0, connector_port=0)
    writers = []
    try:
        account = _login(server)
        other = _login(server, "bob", "pw")
        other_player = server.store.create(other["uid"], "bob", 1, 1)
        reader, writer = await _open_and_ack(server.connector_port)
        writers.append(writer)
        assert (await _request(reader, writer, 101, "logic.playerHandler.rename", {"name": "Nami"}))["code"] == 500
        auth = {"token": account["token"], "serverId": 1, "oldServerId": 1}
        assert await _request(reader, writer, 102, "connector.entryHandler.entry", auth) == {}
        assert (await _request(reader, writer, 103, "logic.playerHandler.rename", {"name": "Nami"}))["code"] == 500
        created = await _request(reader, writer, 104, "connector.playerHandler.createPlayer", {"name": "alice"})
        player = json.loads(gzip.decompress(base64.b64decode(created["player"])))
        second_reader, second_writer = await _open_and_ack(server.connector_port)
        writers.append(second_writer)
        await _request(second_reader, second_writer, 105, "connector.entryHandler.entry", auth)
        assert (await _request(second_reader, second_writer, 106, "logic.playerHandler.rename", {"name": "Nami"}))["code"] == 500
        for request_id, body in enumerate(({}, {"name": 1}, {"name": ""}, {"name": "Nami", "playerId": other_player["id"]}), 107):
            assert (await _request(reader, writer, request_id, "logic.playerHandler.rename", body))["code"] == 500
        assert (await _request(reader, writer, 111, "connector.playerHandler.entry", {"playerId": other_player["id"], "isReconnect": False}))["code"] == 500
        assert (await _request(reader, writer, 112, "logic.playerHandler.rename", {"name": "Nami"}))["code"] == 500
        assert server.store.get_owned(account["uid"], player["id"]) == player
        await _request(reader, writer, 113, "connector.playerHandler.entry", {"playerId": player["id"], "isReconnect": True})
        assert await _request(reader, writer, 114, "logic.playerHandler.rename", {"name": "Nami"}) == {"name": "Nami"}
        assert (await _request(reader, writer, 115, "logic.playerHandler.rename", {"name": "Robin"}))["code"] == 500
        assert await _request(reader, writer, 116, "connector.entryHandler.entry", auth) == {}
        assert (await _request(reader, writer, 117, "logic.playerHandler.rename", {"name": "Nami"}))["code"] == 500
        assert server.store.get_owned(other["uid"], other_player["id"]) == other_player
    finally:
        for writer in writers:
            writer.close()
        for writer in writers:
            await writer.wait_closed()
        await server.close()


async def _rename_flow(tmp_path):
    manifest = tmp_path / "project.manifest"
    manifest.write_text(json.dumps(_manifest()), encoding="utf-8")
    server = await GameServer.start(manifest, tmp_path / "players.sqlite3", http_port=0, gate_port=0, connector_port=0)
    writer = None
    try:
        account = _login(server, "alice", "secret")
        reader, writer = await _open_and_ack(server.connector_port)
        await _request(reader, writer, 1, "connector.entryHandler.entry", {"token": account["token"], "serverId": 1, "oldServerId": 1})
        created = await _request(reader, writer, 2, "connector.playerHandler.createPlayer", {"name": "alice"})
        player_id = json.loads(gzip.decompress(base64.b64decode(created["player"])).decode())["id"]
        assert await _request(reader, writer, 3, "logic.playerHandler.rename", {"name": "alice-renamed"}) == {"name": "alice-renamed"}
        entered = await _request(reader, writer, 4, "connector.playerHandler.entry", {"playerId": player_id, "isReconnect": False})
        player = json.loads(gzip.decompress(base64.b64decode(entered["player"])).decode())
        assert player["name"] == "alice-renamed"
        assert player["userName"] == "alice"
    finally:
        if writer is not None:
            writer.close()
            await writer.wait_closed()
        await server.close()


async def _auth_order_flow(tmp_path):
    manifest = tmp_path / "project.manifest"
    manifest.write_text(json.dumps(_manifest()), encoding="utf-8")
    server = await GameServer.start(manifest, tmp_path / "players.sqlite3", http_port=0, gate_port=0, connector_port=0)
    try:
        account = _login(server)
        reader, writer = await asyncio.open_connection("127.0.0.1", server.connector_port)
        key = base64.b64encode(b"0123456789abcdef").decode()
        writer.write(("GET / HTTP/1.1\r\nHost: localhost\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Version: 13\r\nSec-WebSocket-Key: " + key + "\r\n\r\n").encode())
        await writer.drain(); await reader.readuntil(b"\r\n\r\n")
        writer.write(_masked_frame(encode_frame(HANDSHAKE_ACK, b"")))
        await writer.drain()
        writer.write(_masked_frame(encode_frame(DATA, encode_data(REQUEST, request_id=1, route="connector.playerHandler.getPlayers", payload={}))))
        await writer.drain()
        assert (await asyncio.wait_for(_read_frame(reader), 1))[0] == 8
        writer.close(); await writer.wait_closed()

        reader, writer = await _open_and_ack(server.connector_port)
        assert (await _request(reader, writer, 12, "connector.entryHandler.entry", {"token": account["token"], "serverId": 1, "oldServerId": 1})) == {}
        assert (await _request(reader, writer, 13, "connector.entryHandler.entry", {"token": "bad", "serverId": 1, "oldServerId": 1}))["code"] == 500
        assert (await _request(reader, writer, 14, "connector.playerHandler.getPlayers", {}))["code"] == 500
        writer.close(); await writer.wait_closed()
    finally:
        await server.close()
