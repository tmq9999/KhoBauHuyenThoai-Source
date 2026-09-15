import copy
import asyncio
import base64
from concurrent.futures import ThreadPoolExecutor
import datetime as dt
import gzip
import json
import pathlib
import sqlite3
import sys
import threading

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).parents[2] / "src"))

from game_state import PlayerStore  # noqa: E402
from game_server import GameServer  # noqa: E402
from test_game_server import _login, _manifest, _open_and_ack, _request  # noqa: E402


def _player(store):
    uid, _ = store.login_account("alice", "secret")
    return uid, store.create(uid, "alice", 1, 1)


def _save(store, player):
    store.db.execute("UPDATE players SET payload=? WHERE id=?", (json.dumps(player), player["id"]))
    store.db.commit()


def test_content_reads_literal_apk_rows_without_executing_javascript():
    from game_content import table
    assert table("consumablesData")[21002]["actionPoint"] == 18
    assert table("signInData")[2]["dropListDesc"] == "100701_star_2x1"
    assert table("evolutionItemData")[30102]["requiredIds"] == [40102, 42102, 49902]
    assert table("entityData")[202]["price"] == 5000


def test_literal_reader_rejects_javascript_expressions_and_preserves_strings():
    from game_content import parse_literal
    assert parse_literal('[{hpGrowth: .5, desc: "x: 1, y: .3", n: null}]') == [
        {"hpGrowth": 0.5, "desc": "x: 1, y: .3", "n": None}
    ]
    with pytest.raises(ValueError):
        parse_literal('[{count: process.exit()}]')


def test_new_and_recruited_roles_have_power_and_player_power(tmp_path):
    store = PlayerStore(tmp_path / "state.sqlite3")
    try:
        uid, player = _player(store)
        assert player["power"] == 980.2
        assert player["team"]["roles"]["1"]["attr"]["hpGrowth"] == 233
        result = store.award_recruit(uid, player["id"], "coin")
        assert result["team"]["roles"]["2"]["power"] > 0
        persisted = store.get_owned(uid, player["id"])
        assert persisted["power"] == sum(role["power"] for role in persisted["team"]["roles"].values())
    finally:
        store.close()


def test_battle_win_returns_and_persists_stage_drop_items(tmp_path):
    store = PlayerStore(tmp_path / "state.sqlite3")
    try:
        uid, player = _player(store)
        assert store.begin_smap(uid, player["id"], 10101, ["1"])
        result = store.end_smap(uid, player["id"], 3, ["1"])
        assert result["_temp"]["entityCountMap"] == {"42102": 1, "42202": 1}
        assert result["bag"]["items"]
        persisted = store.get_owned(uid, player["id"])
        assert sum(item["count"] for item in persisted["bag"]["items"].values()) == 2
    finally:
        store.close()


def test_sell_treasure_and_use_ap_item_return_tombstones_without_losing_ap(tmp_path):
    store = PlayerStore(tmp_path / "state.sqlite3")
    try:
        uid, player = _player(store)
        player["bag"]["items"] = {"7": {"kindId": 201, "count": 2}, "8": {"kindId": 21001, "count": 1}}
        player["actionPoint"] = 70
        _save(store, player)
        result = store.sell_items(uid, player["id"], ["7"], [1])
        assert result["coin"] == 2000
        assert result["bag"]["items"]["7"]["count"] == 1
        result = store.use_item(uid, player["id"], "8", 1)
        assert result["actionPoint"] == 76
        assert result["bag"]["items"]["8"] is None
    finally:
        store.close()


def test_sign_in_awards_next_day_role_at_two_stars_and_rejects_same_day_retry(tmp_path):
    store = PlayerStore(tmp_path / "state.sqlite3")
    try:
        uid, player = _player(store)
        first = store.sign_in(uid, player["id"], now_ms=1_700_000_000_000)
        assert first["signInDays"] == 1
        assert first["_temp"]["entityCountMap"] == {"202": 2}
        assert store.sign_in(uid, player["id"], now_ms=1_700_000_000_000) is None
        second = store.sign_in(uid, player["id"], now_ms=1_700_086_400_000)
        assert second["signInDays"] == 2
        rewarded_role = next(role for role in second["team"]["roles"].values() if role["kindId"] == 100701)
        assert rewarded_role["star"] == 2
        assert rewarded_role["initAttr"]["hp"] == 901
        assert all(item["kindId"] != 100701 for item in store.get_owned(uid, player["id"])["bag"]["items"].values())
    finally:
        store.close()


def test_evolve_role_changes_kind_and_returns_updated_team(tmp_path):
    store = PlayerStore(tmp_path / "state.sqlite3")
    try:
        uid, player = _player(store)
        for item in player["team"]["roles"]["1"]["equipments"].values():
            item["kindId"] += 1
        _save(store, player)
        result = store.evolve_role(uid, player["id"], "1")
        assert result["team"]["roles"]["1"]["kindId"] == 100102
        assert result["_temp"]["preRole"]["kindId"] == 100101
        assert result["team"]["roles"]["1"]["skills"] == {
            "100101": {"kindId": 100101, "level": 1}, "100102": {"kindId": 100102, "level": 1}
        }
        assert result["coin"] == 0
        assert result["team"]["roles"]["1"]["power"] > 0
    finally:
        store.close()


def test_use_role_experience_item_levels_teammate_and_consumes_item(tmp_path):
    store = PlayerStore(tmp_path / "state.sqlite3")
    try:
        uid, player = _player(store)
        player["bag"]["items"] = {"9": {"kindId": 20002, "count": 1}}
        _save(store, player)
        result = store.use_exp_item(uid, player["id"], "1", "9", 1)
        role = result["team"]["roles"]["1"]
        assert (role["level"], role["experience"], role["power"]) == (6, 65, 1501.7)
        assert result["bag"]["items"]["9"] is None
    finally:
        store.close()


def test_evolve_equipment_consumes_exact_materials_before_role_evolution(tmp_path):
    store = PlayerStore(tmp_path / "state.sqlite3")
    try:
        uid, player = _player(store)
        player["coin"] = 600
        player["bag"]["items"] = {str(i): {"kindId": entity, "count": count} for i, (entity, count) in enumerate(
            [(40102, 1), (42102, 1), (49902, 6), (40202, 1), (42202, 1), (40302, 1), (42302, 1),
             (40402, 1), (42402, 1), (40502, 1), (42502, 1), (40602, 1), (42602, 1)], 1)}
        _save(store, player)
        assert store.evolve_role(uid, player["id"], "1") is None
        for slot in range(1, 7):
            result = store.evolve_equipment(uid, player["id"], "1", f"evlItem_{slot}")
            assert result["team"]["roles"]["1"]["equipments"][f"evlItem_{slot}"]["kindId"] == 30002 + slot * 100
        assert result["coin"] == 0
        assert store.get_owned(uid, player["id"])["bag"]["items"] == {}
        evolved = store.evolve_role(uid, player["id"], "1")
        assert evolved["team"]["roles"]["1"]["kindId"] == 100102
        assert store.evolve_role(uid, player["id"], "1") is None
        assert store.begin_smap(uid, player["id"], 10101, ["1"])["code"] == 200
    finally:
        store.close()


def test_box_reward_delta_contains_new_stacks_and_consumed_slot(tmp_path):
    store = PlayerStore(tmp_path / "state.sqlite3")
    try:
        uid, player = _player(store)
        player["bag"]["items"] = {"9": {"kindId": 321, "count": 1}}
        _save(store, player)
        result = store.use_item(uid, player["id"], "9", 1)
        client_items = copy.deepcopy(player["bag"]["items"])
        for key, value in result["bag"]["items"].items():
            if value is None:
                client_items.pop(key, None)
            else:
                client_items[key] = value
        assert client_items == store.get_owned(uid, player["id"])["bag"]["items"]
        assert sum(item["count"] for item in client_items.values()) == 18
    finally:
        store.close()


@pytest.mark.parametrize("method,args", [
    ("use_item", ("1", -1)), ("use_item", (True, 1)), ("use_item", ("1", True)),
    ("use_item", ("1", 3)), ("sell_items", (["1", "1"], [1, 1])),
    ("sell_items", ([{}], [1])), ("sell_items", (["1"], [True])),
    ("use_exp_item", ("1", "1", -1)), ("use_exp_item", ("1", True, 1)),
    ("evolve_role", (True,)), ("evolve_equipment", ("1", "invalid")),
])
def test_invalid_requests_never_change_persisted_player(tmp_path, method, args):
    store = PlayerStore(tmp_path / "state.sqlite3")
    try:
        uid, player = _player(store)
        player["bag"]["items"] = {"1": {"kindId": 201, "count": 2}}
        _save(store, player)
        assert getattr(store, method)(uid, player["id"], *args) is None
        assert store.get_owned(uid, player["id"]) == player
    finally:
        store.close()


def test_sign_in_uses_vietnam_midnight_vip_multiplier_and_actual_later_days(tmp_path):
    store = PlayerStore(tmp_path / "state.sqlite3")
    try:
        uid, player = _player(store)
        zone = dt.timezone(dt.timedelta(hours=7))
        before_midnight = int(dt.datetime(2026, 9, 15, 23, 59, tzinfo=zone).timestamp() * 1000)
        player["signInDays"] = 3
        player["signInTime"] = before_midnight
        player["vip"]["level"] = 4
        _save(store, player)
        assert store.sign_in(uid, player["id"], now_ms=before_midnight - 86_400_000) is None
        result = store.sign_in(uid, player["id"], now_ms=before_midnight + 60_000)
        assert result["signInDays"] == 4
        assert result["gem"] == 110
        assert result["_temp"]["entityCountMap"] == {"102": 60}
        assert store.sign_in(uid, player["id"], now_ms=before_midnight + 120_000) is None
        fifth = store.sign_in(uid, player["id"], now_ms=before_midnight + 2 * 86_400_000)
        assert fifth["signInDays"] == 5
        assert fifth["_temp"]["entityCountMap"] == {"21002": 5}
    finally:
        store.close()


def test_capped_role_cannot_spend_more_exp_items_but_can_still_battle(tmp_path):
    store = PlayerStore(tmp_path / "state.sqlite3")
    try:
        uid, player = _player(store)
        player["bag"]["items"] = {"1": {"kindId": 20004, "count": 2}}
        _save(store, player)
        first = store.use_exp_item(uid, player["id"], "1", "1", 1)
        assert (first["team"]["roles"]["1"]["level"], first["team"]["roles"]["1"]["experience"]) == (6, 100)
        before = store.get_owned(uid, player["id"])
        assert store.use_exp_item(uid, player["id"], "1", "1", 1) is None
        assert store.get_owned(uid, player["id"]) == before
        assert store.begin_smap(uid, player["id"], 10101, ["1"])["code"] == 200
        assert store.end_smap(uid, player["id"], 3, ["1"])["code"] == 200
    finally:
        store.close()


def test_failed_reward_write_rolls_back_signin_marker_and_inventory(tmp_path):
    store = PlayerStore(tmp_path / "state.sqlite3")
    try:
        uid, player = _player(store)
        store.db.execute("CREATE TRIGGER reject_award BEFORE UPDATE ON players BEGIN SELECT RAISE(ABORT, 'test failure'); END")
        with pytest.raises(sqlite3.IntegrityError):
            store.sign_in(uid, player["id"])
        assert not store.db.in_transaction
        assert store.get_owned(uid, player["id"]) == player
    finally:
        store.close()


def test_battle_result_refreshes_power_before_reply_and_database_commit(tmp_path):
    store = PlayerStore(tmp_path / "state.sqlite3")
    try:
        uid, player = _player(store)
        for stage in (10101, 10102):
            assert store.begin_smap(uid, player["id"], stage, ["1"])
            result = store.end_smap(uid, player["id"], 3, ["1"])
        assert result["team"]["roles"]["1"]["power"] == 1084.5
        assert result["power"] == 1084.5
        stored = json.loads(store.db.execute("SELECT payload FROM players WHERE id=?", (player["id"],)).fetchone()[0])
        assert stored["power"] == result["power"]
    finally:
        store.close()


def test_legacy_growth_and_power_repair_persists_without_changing_progress(tmp_path):
    state = tmp_path / "state.sqlite3"
    store = PlayerStore(state)
    uid, player = _player(store)
    legacy = copy.deepcopy(player)
    role = legacy["team"]["roles"]["1"]
    legacy["power"] = role["power"] = 0
    for field in ("hpGrowth", "atkGrowth", "defGrowth", "mdefGrowth"):
        role["attr"].pop(field)
    for item in role["equipments"].values():
        item.pop("attrs")
    legacy["coin"] = 9182
    legacy["bag"]["items"] = {"71": {"kindId": 202, "count": 4}}
    _save(store, legacy)
    store.close()
    reopened = PlayerStore(state)
    try:
        repaired = reopened.get_owned(uid, player["id"])
        expected = copy.deepcopy(player)
        expected["coin"], expected["bag"] = legacy["coin"], legacy["bag"]
        assert repaired == expected
        assert json.loads(reopened.db.execute("SELECT payload FROM players").fetchone()[0]) == repaired
    finally:
        reopened.close()


def test_duplicate_signin_across_two_stores_awards_only_once(tmp_path):
    state = tmp_path / "state.sqlite3"
    first, second = PlayerStore(state), PlayerStore(state)
    try:
        uid, player = _player(first)
        barrier = threading.Barrier(2, timeout=5)
        def claim(store):
            barrier.wait()
            return store.sign_in(uid, player["id"], now_ms=1_700_000_000_000)
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(claim, store) for store in (first, second)]
            results = [future.result(timeout=5) for future in futures]
        assert sum(result is not None for result in results) == 1
        stored = first.get_owned(uid, player["id"])
        assert stored["signInDays"] == 1
        assert list(stored["bag"]["items"].values()) == [{"kindId": 202, "count": 2}]
    finally:
        first.close()
        second.close()


def test_existing_owned_player_still_required_for_all_new_mutations(tmp_path):
    store = PlayerStore(tmp_path / "state.sqlite3")
    try:
        uid, player = _player(store)
        other, _ = store.login_account("bob", "pw")
        for owner, player_id, server_id in ((other, player["id"], 1), (uid, 0, 1), (uid, player["id"], 2)):
            for method, args in (("sign_in", ()), ("use_item", ("1", 1)), ("sell_items", (["1"], [1])),
                                 ("use_exp_item", ("1", "1", 1)), ("evolve_role", ("1",)),
                                 ("evolve_equipment", ("1", "evlItem_1"))):
                assert getattr(store, method)(owner, player_id, *args, server_id=server_id) is None
        assert store.get_owned(uid, player["id"]) == player
    finally:
        store.close()


def test_use_exp_at_level_ten_uses_next_apk_row_instead_of_artificial_cap(tmp_path):
    store = PlayerStore(tmp_path / "state.sqlite3")
    try:
        uid, player = _player(store)
        player.update(level=10, nextLevelExp=130)
        player["team"]["roles"]["1"].update(level=10, nextLevelExp=180)
        player["bag"]["items"] = {"1": {"kindId": 20002, "count": 1}}
        _save(store, player)
        result = store.use_exp_item(uid, player["id"], "1", "1", 1)
        role = result["team"]["roles"]["1"]
        assert (role["level"], role["experience"], role["nextLevelExp"]) == (11, 120, 210)
    finally:
        store.close()


def test_retry_recruit_after_evolution_does_not_award_duplicate_class(tmp_path):
    store = PlayerStore(tmp_path / "state.sqlite3")
    try:
        uid, player = _player(store)
        store.award_recruit(uid, player["id"], "coin")
        player = store.get_owned(uid, player["id"])
        player["team"]["roles"]["2"]["kindId"] = 100202
        player["point"]["nextCoinFreeTime"] = 0
        _save(store, player)
        result = store.award_recruit(uid, player["id"], "coin")
        assert result["team"]["roles"]["2"]["kindId"] == 100202
        assert len(store.get_owned(uid, player["id"])["team"]["roles"]) == 2
    finally:
        store.close()


def test_retry_recruit_repairs_zero_power_in_database_not_just_response(tmp_path):
    store = PlayerStore(tmp_path / "state.sqlite3")
    try:
        uid, player = _player(store)
        store.award_recruit(uid, player["id"], "coin")
        player = store.get_owned(uid, player["id"])
        player["power"] = 0
        player["team"]["roles"]["2"]["power"] = 0
        _save(store, player)
        result = store.award_recruit(uid, player["id"], "coin")
        stored = json.loads(store.db.execute("SELECT payload FROM players").fetchone()[0])
        assert stored["power"] == result["power"] == 1960.4
    finally:
        store.close()


def test_player_level_eleven_to_twelve_grants_ap_from_recovered_rule(tmp_path):
    store = PlayerStore(tmp_path / "state.sqlite3")
    try:
        uid, player = _player(store)
        player.update(level=11, experience=129, nextLevelExp=130, actionPoint=50)
        _save(store, player)
        assert store.begin_smap(uid, player["id"], 10101, ["1"])
        result = store.end_smap(uid, player["id"], 3, ["1"])
        assert (result["level"], result["experience"], result["actionPoint"]) == (12, 5, 84)
        assert result["timesMaxMap"]["actionPoint"] == 72
    finally:
        store.close()


def test_new_feature_routes_use_selected_owner_and_survive_reconnect(tmp_path):
    asyncio.run(asyncio.wait_for(_feature_socket_flow(tmp_path), 15))


async def _feature_socket_flow(tmp_path):
    manifest = tmp_path / "project.manifest"
    manifest.write_text(json.dumps(_manifest()), encoding="utf-8")
    state = tmp_path / "players.sqlite3"
    server = await GameServer.start(manifest, state, http_port=0, gate_port=0, connector_port=0)
    writers = []
    try:
        account = _login(server)
        reader, writer = await _open_and_ack(server.connector_port)
        writers.append(writer)
        auth = {"token": account["token"], "serverId": 1, "oldServerId": 1}
        routes = [
            ("logic.playerHandler.signIn", {}),
            ("logic.playerHandler.useItem", {"bagIndex": "7", "itemCount": 1}),
            ("logic.bagHandler.sell", {"bagIndexs": ["7"], "itemCounts": [1]}),
            ("logic.teamHandler.useExpItem", {"teamIndex": "1", "bagIndex": "8", "itemCount": 1}),
            ("logic.teamHandler.evolveEquipment", {"teamIndex": "1", "equipmentType": "evlItem_1"}),
            ("logic.teamHandler.evolveRole", {"teamIndex": "1"}),
        ]
        seq = 0
        async def request(route, body):
            nonlocal seq
            seq += 1
            return await _request(reader, writer, seq, route, body)

        for route, body in routes:
            assert (await request(route, body))["code"] == 500
        assert await request("connector.entryHandler.entry", auth) == {}
        for route, body in routes:
            assert (await request(route, body))["code"] == 500
        created = await request("connector.playerHandler.createPlayer", {"name": "alice"})
        player = json.loads(gzip.decompress(base64.b64decode(created["player"])))
        assert player["power"] == 980.2
        first_sign = await request(*routes[0])
        assert first_sign["signInDays"] == 1
        assert first_sign["_temp"]["entityCountMap"] == {"202": 2}
        bag_key = next(iter(first_sign["bag"]["items"]))
        sold = await request("logic.bagHandler.sell", {"bagIndexs": [bag_key], "itemCounts": [2]})
        assert sold["coin"] == 10000
        assert sold["bag"]["items"][bag_key] is None
        assert (await request(*routes[0]))["code"] == 500
        # No live state is edited: seed the independent test DB for the routes
        # whose item sources are outside the currently mapped gameplay slice.
        seeded = server.store.get_owned(account["uid"], player["id"])
        seeded["bag"]["items"] = {"7": {"kindId": 321, "count": 1}, "8": {"kindId": 20002, "count": 1},
                                   "9": {"kindId": 21002, "count": 1}}
        _save(server.store, seeded)
        box = await request("logic.playerHandler.useItem", {"bagIndex": "7", "itemCount": 1})
        assert len(box["_temp"]["entityCountMap"]) == 13
        exp = await request(*routes[3])
        assert exp["team"]["roles"]["1"]["level"] == 6
        assert exp["power"] == 1501.7
        ap = await request("logic.playerHandler.useItem", {"bagIndex": "9", "itemCount": 1})
        assert ap["actionPoint"] == 78
        for index in range(1, 7):
            assert (await request("logic.teamHandler.evolveEquipment", {"teamIndex": "1", "equipmentType": f"evlItem_{index}"}))["code"] == 200
        evolve = await request(*routes[5])
        assert evolve["team"]["roles"]["1"]["kindId"] == 100102
        assert evolve["_temp"]["preRole"]["level"] == 6
        current = server.store.get_owned(account["uid"], player["id"])
        for route, body in routes:
            assert (await request(route, {**body, "playerId": 999}))["code"] == 500
        assert server.store.get_owned(account["uid"], player["id"]) == current
        assert (await request("connector.playerHandler.entry", {"playerId": 999, "isReconnect": False}))["code"] == 500
        for route, body in routes:
            assert (await request(route, body))["code"] == 500
        entered = await request("connector.playerHandler.entry", {"playerId": player["id"], "isReconnect": True})
        assert json.loads(gzip.decompress(base64.b64decode(entered["player"]))) == current
    finally:
        for writer in writers:
            writer.close()
            await writer.wait_closed()
        await server.close()
    reopened = PlayerStore(state)
    try:
        assert reopened.get_owned(account["uid"], player["id"]) == current
    finally:
        reopened.close()
