import asyncio
import base64
import gzip
import http.client
import json
import pathlib
import sqlite3
import struct
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).parents[2] / "src"))

from game_server import GameServer  # noqa: E402
from game_state import PlayerStore  # noqa: E402
from pomelo_codec import (  # noqa: E402
    DATA,
    HANDSHAKE,
    HANDSHAKE_ACK,
    REQUEST,
    decode_data,
    decode_frame,
    encode_data,
    encode_frame,
)


def _battle_player(store, name="alice", password="secret"):
    account = store.login_account(name, password)
    assert account is not None
    uid, token = account
    player = store.create(uid, name, 1, 1)
    assert store.award_recruit(uid, player["id"], "coin") is not None
    assert store.award_recruit(uid, player["id"], "gem") is not None
    return uid, token, store.get_owned(uid, player["id"])


def test_begin_smap_debits_ap_once_and_pending_survives_store_reopen(tmp_path):
    state = tmp_path / "players.sqlite3"
    store = PlayerStore(state)
    uid, _, player = _battle_player(store)
    expected = {"code": 200, "actionPoint": 54, "_temp": {"showEntityIdsMap": {}}}
    assert store.begin_smap(uid, player["id"], 10101, ["1", "2", "3"]) == expected
    assert store.begin_smap(uid, player["id"], 10101, ["1", "2", "3"]) == expected
    assert store.get_owned(uid, player["id"])["actionPoint"] == 54
    store.close()

    reopened = PlayerStore(state)
    try:
        assert reopened.begin_smap(uid, player["id"], 10101, ["1", "2", "3"]) == expected
        assert reopened.get_owned(uid, player["id"])["actionPoint"] == 54
    finally:
        reopened.close()


def test_first_win_awards_literal_values_complete_roles_and_preserves_map_subtrees(tmp_path):
    store = PlayerStore(tmp_path / "players.sqlite3")
    try:
        uid, _, player = _battle_player(store)
        player["smapStarMap"] = {
            "1": {"101": {"10101": 0, "10106": 0, "sibling": 3}, "102": {"kept": 2}},
            "2": {"kept": True},
        }
        player["smapTimesMap"] = {
            "1": {"101": {"10101": 0, "10106": 0, "sibling": 4}, "102": {"kept": 5}},
            "2": {"kept": True},
        }
        store.db.execute("UPDATE players SET payload=? WHERE id=?", (json.dumps(player), player["id"]))
        store.db.commit()

        assert store.begin_smap(uid, player["id"], 10101, ["1", "2", "3"])["actionPoint"] == 54
        result = store.end_smap(uid, player["id"], 3, ["1", "2", "3"])

        assert result["code"] == 200
        assert (result["coin"], result["experience"], result["actionPoint"]) == (1200, 6, 54)
        assert result["_temp"] == {"entityCountMap": {}}
        assert result["smapStarMap"] == {
            "1": {"101": {"10101": 3, "10106": 0, "sibling": 3}, "102": {"kept": 2}}
        }
        assert result["smapTimesMap"] == {
            "1": {"101": {"10101": 1, "10106": 0, "sibling": 4}, "102": {"kept": 5}}
        }
        assert set(result["team"]["roles"]) == {"1", "2", "3"}
        assert [result["team"]["roles"][key]["kindId"] for key in ("1", "2", "3")] == [100101, 100201, 100301]
        for role in result["team"]["roles"].values():
            assert role["level"] == 1
            assert role["experience"] == 20
            assert role["nextLevelExp"] == 25
            assert set(role["attr"]) == {"hp", "atk", "def", "mdef", "hit", "dodge", "crit"}
            assert len(role["equipments"]) == 6

        persisted = store.get_owned(uid, player["id"])
        assert persisted["coin"] == 1200 and persisted["experience"] == 6
        assert persisted["smapStarMap"]["2"] == {"kept": True}
        assert persisted["smapTimesMap"]["2"] == {"kept": True}
        assert store.end_smap(uid, player["id"], 3, ["1", "2", "3"]) is None
        assert store.begin_smap(uid, player["id"], 10101, ["1", "2", "3"]) is None
        assert store.get_owned(uid, player["id"])["coin"] == 1200
    finally:
        store.close()


def test_loss_closes_pending_counts_attempt_without_rewards_and_allows_retry(tmp_path):
    store = PlayerStore(tmp_path / "players.sqlite3")
    try:
        uid, _, player = _battle_player(store)
        store.begin_smap(uid, player["id"], 10101, ["1", "2", "3"])
        result = store.end_smap(uid, player["id"], 0, ["1", "2", "3"])
        assert result == {
            "code": 200,
            "actionPoint": 54,
            "smapTimesMap": {"1": {"101": {"10101": 1, "10106": 0}}},
            "_temp": {"entityCountMap": {}},
        }
        persisted = store.get_owned(uid, player["id"])
        assert persisted["coin"] == 0 and persisted["experience"] == 0
        assert persisted["smapStarMap"]["1"]["101"]["10101"] == 0
        assert all(role["experience"] == 0 for role in persisted["team"]["roles"].values())
        assert store.end_smap(uid, player["id"], 0, ["1", "2", "3"]) is None
        assert store.begin_smap(uid, player["id"], 10101, ["1", "2", "3"])["actionPoint"] == 48
    finally:
        store.close()


def test_pending_rejects_different_begin_cross_owner_and_mismatched_end(tmp_path):
    store = PlayerStore(tmp_path / "players.sqlite3")
    try:
        alice_uid, _, alice = _battle_player(store, "alice", "secret")
        bob_uid, _, _ = _battle_player(store, "bob", "pw")
        before = store.get_owned(alice_uid, alice["id"])
        assert store.begin_smap(alice_uid, alice["id"], 10101, ["1", "2", "3"])["actionPoint"] == 54
        assert store.begin_smap(alice_uid, alice["id"], 10101, ["1", "2"]) is None
        assert store.end_smap(bob_uid, alice["id"], 3, ["1", "2", "3"]) is None
        assert store.end_smap(alice_uid, alice["id"], 3, ["1", "2"]) is None
        after_rejections = store.get_owned(alice_uid, alice["id"])
        assert after_rejections["actionPoint"] == before["actionPoint"] - 6
        assert after_rejections["coin"] == before["coin"]
        assert store.end_smap(alice_uid, alice["id"], 2, ["3", "2", "1"])["coin"] == 1200
    finally:
        store.close()


def test_expired_pending_cannot_settle_but_does_not_permanently_block_player(tmp_path):
    store = PlayerStore(tmp_path / "players.sqlite3")
    try:
        uid, _, player = _battle_player(store)
        store.begin_smap(uid, player["id"], 10101, ["1", "2", "3"])
        store.db.execute("UPDATE smap_pending SET expires_at=0 WHERE player_id=?", (player["id"],))
        store.db.commit()
        assert store.end_smap(uid, player["id"], 3, ["1", "2", "3"]) is None
        expired = store.get_owned(uid, player["id"])
        assert (expired["actionPoint"], expired["coin"], expired["experience"]) == (54, 0, 0)
        assert expired["smapTimesMap"]["1"]["101"]["10101"] == 0
        assert store.begin_smap(uid, player["id"], 10101, ["1", "2", "3"])["actionPoint"] == 48
    finally:
        store.close()


@pytest.mark.parametrize(
    "smap_id,indices",
    [
        (10102, ["1", "2", "3"]),
        (True, ["1", "2", "3"]),
        (10101, []),
        (10101, ["1", "1"]),
        (10101, ["1", "2", "3", "4", "5", "6"]),
        (10101, ["1", "2", 3]),
        (10101, ["1", "2", "99"]),
    ],
)
def test_begin_rejects_unsupported_or_invalid_selection_without_mutation(tmp_path, smap_id, indices):
    store = PlayerStore(tmp_path / "players.sqlite3")
    try:
        uid, _, player = _battle_player(store)
        before = store.get_owned(uid, player["id"])
        assert store.begin_smap(uid, player["id"], smap_id, indices) is None
        assert store.get_owned(uid, player["id"]) == before
    finally:
        store.close()


def test_begin_rejects_attempt_cap_low_ap_completed_and_unsupported_role_state(tmp_path):
    for field, value in (("attempts", 10), ("ap", 5), ("completed", 1), ("role_xp", 5)):
        store = PlayerStore(tmp_path / f"{field}.sqlite3")
        try:
            uid, _, player = _battle_player(store)
            if field == "attempts":
                player["smapTimesMap"]["1"]["101"]["10101"] = value
            elif field == "ap":
                player["actionPoint"] = value
            elif field == "completed":
                player["smapStarMap"]["1"]["101"]["10101"] = value
            else:
                player["team"]["roles"]["1"]["experience"] = value
            store.db.execute("UPDATE players SET payload=? WHERE id=?", (json.dumps(player), player["id"]))
            store.db.commit()
            before = store.get_owned(uid, player["id"])
            assert store.begin_smap(uid, player["id"], 10101, ["1", "2", "3"]) is None
            assert store.get_owned(uid, player["id"]) == before
        finally:
            store.close()


@pytest.mark.parametrize("star", [-1, 4, True, 1.0, "3"])
def test_end_rejects_invalid_star_without_consuming_pending(tmp_path, star):
    store = PlayerStore(tmp_path / "players.sqlite3")
    try:
        uid, _, player = _battle_player(store)
        store.begin_smap(uid, player["id"], 10101, ["1", "2", "3"])
        assert store.end_smap(uid, player["id"], star, ["1", "2", "3"]) is None
        assert store.end_smap(uid, player["id"], 1, ["1", "2", "3"])["coin"] == 1200
    finally:
        store.close()


def test_begin_and_end_roll_back_all_battle_state_when_sqlite_write_fails(tmp_path):
    store = PlayerStore(tmp_path / "players.sqlite3")
    try:
        uid, _, player = _battle_player(store)
        store.db.execute("CREATE TRIGGER reject_begin BEFORE UPDATE ON players BEGIN SELECT RAISE(ABORT, 'battle write failed'); END")
        store.db.commit()
        with pytest.raises(sqlite3.IntegrityError, match="battle write failed"):
            store.begin_smap(uid, player["id"], 10101, ["1", "2", "3"])
        assert not store.db.in_transaction
        assert store.db.execute("SELECT COUNT(*) FROM smap_pending").fetchone()[0] == 0
        store.db.execute("DROP TRIGGER reject_begin")
        assert store.get_owned(uid, player["id"])["actionPoint"] == 60

        store.begin_smap(uid, player["id"], 10101, ["1", "2", "3"])
        store.db.execute("CREATE TRIGGER reject_end BEFORE UPDATE ON players BEGIN SELECT RAISE(ABORT, 'settle write failed'); END")
        store.db.commit()
        with pytest.raises(sqlite3.IntegrityError, match="settle write failed"):
            store.end_smap(uid, player["id"], 3, ["1", "2", "3"])
        assert not store.db.in_transaction
        assert store.db.execute("SELECT COUNT(*) FROM smap_pending").fetchone()[0] == 1
        stored = json.loads(store.db.execute("SELECT payload FROM players WHERE id=?", (player["id"],)).fetchone()[0])
        assert (stored["actionPoint"], stored["coin"], stored.get("experience", 0)) == (54, 0, 0)
        store.db.execute("DROP TRIGGER reject_end")
        assert store.end_smap(uid, player["id"], 3, ["1", "2", "3"])["coin"] == 1200
    finally:
        store.close()


def _manifest():
    return {
        "version": "1.0.0.02",
        "host": "127.0.0.1:20001",
        "remoteVersionUrl": "http://127.0.0.1:20001/update/version.manifest",
        "remoteManifestUrl": "http://127.0.0.1:20001/update/project.manifest",
        "packageUrl": "http://127.0.0.1:20001/update/1.0.0.02",
        "assets": {},
    }


def _login(server, name="alice", password="secret"):
    connection = http.client.HTTPConnection(server.host, server.http_port, timeout=2)
    try:
        connection.request(
            "POST",
            "/user/login",
            f"name={name}&password={password}",
            {"Content-Type": "application/x-www-form-urlencoded"},
        )
        response = connection.getresponse()
        assert response.status == 200
        return json.loads(response.read())
    finally:
        connection.close()


def _masked_frame(payload):
    mask = b"\x01\x02\x03\x04"
    masked = bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))
    length = bytes((0x80 | len(masked),)) if len(masked) < 126 else bytes((0x80 | 126,)) + struct.pack(">H", len(masked))
    return b"\x82" + length + mask + masked


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
    assert opcode == 2 and decode_frame(reply)[0] == HANDSHAKE
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


def test_begin_and_end_smap_routes_over_real_loopback_websocket(tmp_path):
    asyncio.run(asyncio.wait_for(_battle_socket_flow(tmp_path), 10))


async def _battle_socket_flow(tmp_path):
    manifest = tmp_path / "project.manifest"
    manifest.write_text(json.dumps(_manifest()), encoding="utf-8")
    server = await GameServer.start(manifest, tmp_path / "players.sqlite3", http_port=0, gate_port=0, connector_port=0)
    writer = None
    try:
        account = _login(server)
        reader, writer = await _open_and_ack(server.connector_port)
        auth = {"token": account["token"], "serverId": 1, "oldServerId": 1}
        assert await _request(reader, writer, 1, "connector.entryHandler.entry", auth) == {}
        created = await _request(reader, writer, 2, "connector.playerHandler.createPlayer", {"name": "alice"})
        player = json.loads(gzip.decompress(base64.b64decode(created["player"])))
        await _request(reader, writer, 3, "logic.pointHandler.coin", {})
        await _request(reader, writer, 4, "logic.pointHandler.gem", {})

        begin = await _request(
            reader, writer, 5, "logic.smapHandler.beginSmap", {"smapId": 10101, "teamIndexs": ["1", "2", "3"]}
        )
        assert begin == {"code": 200, "actionPoint": 54, "_temp": {"showEntityIdsMap": {}}}
        end = await _request(
            reader, writer, 6, "logic.smapHandler.endSmap", {"star": 3, "teamIndexs": ["1", "2", "3"]}
        )
        assert (end["code"], end["coin"], end["experience"], end["actionPoint"]) == (200, 1200, 6, 54)
        assert end["_temp"] == {"entityCountMap": {}}
        stored = server.store.get_owned(account["uid"], player["id"])
        assert stored["smapStarMap"]["1"]["101"]["10101"] == 3
    finally:
        if writer is not None:
            writer.close()
            await writer.wait_closed()
        await server.close()


def test_smap_routes_require_exact_payload_selected_owner_and_pending(tmp_path):
    asyncio.run(asyncio.wait_for(_battle_socket_rejections(tmp_path), 10))


async def _battle_socket_rejections(tmp_path):
    manifest = tmp_path / "project.manifest"
    manifest.write_text(json.dumps(_manifest()), encoding="utf-8")
    server = await GameServer.start(manifest, tmp_path / "players.sqlite3", http_port=0, gate_port=0, connector_port=0)
    writers = []
    try:
        account = _login(server)
        reader, writer = await _open_and_ack(server.connector_port)
        writers.append(writer)
        await _request(reader, writer, 1, "connector.entryHandler.entry", {"token": account["token"], "serverId": 1, "oldServerId": 1})
        assert (await _request(reader, writer, 2, "logic.smapHandler.beginSmap", {"smapId": 10101, "teamIndexs": ["1"]}))["code"] == 500
        created = await _request(reader, writer, 3, "connector.playerHandler.createPlayer", {"name": "alice"})
        player = json.loads(gzip.decompress(base64.b64decode(created["player"])))
        await _request(reader, writer, 4, "logic.pointHandler.coin", {})
        await _request(reader, writer, 5, "logic.pointHandler.gem", {})
        for request_id, body in enumerate(
            (
                {"smapId": 10101, "teamIndexs": ["1", "2", "3"], "extra": True},
                {"smapId": 10102, "teamIndexs": ["1", "2", "3"]},
                {"smapId": 10101, "teamIndexs": ["1", "1"]},
            ),
            6,
        ):
            assert (await _request(reader, writer, request_id, "logic.smapHandler.beginSmap", body))["code"] == 500
        assert (await _request(reader, writer, 9, "logic.smapHandler.endSmap", {"star": 3, "teamIndexs": ["1", "2", "3"]}))["code"] == 500
        assert server.store.get_owned(account["uid"], player["id"])["actionPoint"] == 60
    finally:
        for writer in writers:
            writer.close()
        for writer in writers:
            await writer.wait_closed()
        await server.close()
