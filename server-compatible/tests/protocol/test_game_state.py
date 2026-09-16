from concurrent.futures import ThreadPoolExecutor
import copy
import gzip
import json
import pathlib
import sqlite3
import sys
import threading

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).parents[2] / "src"))

from game_state import PlayerStore, encode_player  # noqa: E402


def test_rename_owned_player_persists_and_rejects_wrong_owner(tmp_path):
    path = tmp_path / "players.sqlite3"
    store = PlayerStore(path)
    try:
        assert store.register_account("alice", "secret")
        assert store.register_account("bob", "secret")
        alice = store.login_account("alice", "secret")
        bob = store.login_account("bob", "secret")
        assert alice and bob
        player = store.create(alice[0], "alice", 1, 1)
        assert store.rename(alice[0], player["id"], "alice-renamed") == {"name": "alice-renamed"}
        assert store.get_owned(alice[0], player["id"])["name"] == "alice-renamed"
        assert store.rename(bob[0], player["id"], "stolen") is None
        expected = dict(player, name="alice-renamed")
        assert store.get_owned(alice[0], player["id"]) == expected
    finally:
        store.close()
    reopened = PlayerStore(path)
    try:
        assert reopened.get_owned(alice[0], player["id"]) == expected
        assert reopened.create(alice[0], "alice", 1, 1) == expected
    finally:
        reopened.close()


def test_first_rename_is_retry_safe_and_does_not_implement_paid_renames(tmp_path):
    store = PlayerStore(tmp_path / "players.sqlite3")
    try:
        uid, _ = store.login_account("alice", "secret")
        player = store.create(uid, "alice", 1, 1)
        assert store.rename(uid, player["id"], "alice") is None
        assert store.rename(uid, player["id"], "Nami") == {"name": "Nami"}
        assert store.rename(uid, player["id"], "Nami") == {"name": "Nami"}
        assert store.rename(uid, player["id"], "Robin") is None
        assert store.get_owned(uid, player["id"]) == dict(player, name="Nami")
    finally:
        store.close()


@pytest.mark.parametrize("name", [None, True, 12, {}, [], "", "   ", "a" * 65, "bad\nname", "bad\x00name", "bad\ud800"])
def test_first_rename_rejects_invalid_names_without_mutation(tmp_path, name):
    store = PlayerStore(tmp_path / "players.sqlite3")
    try:
        uid, _ = store.login_account("alice", "secret")
        player = store.create(uid, "alice", 1, 1)
        assert store.rename(uid, player["id"], name) is None
        assert store.get_owned(uid, player["id"]) == player
    finally:
        store.close()


def test_first_rename_preserves_unicode_name(tmp_path):
    store = PlayerStore(tmp_path / "players.sqlite3")
    try:
        uid, _ = store.login_account("alice", "secret")
        player = store.create(uid, "alice", 1, 1)
        name = "H\u1ea3i T\u1eb7c"
        assert store.rename(uid, player["id"], name) == {"name": name}
        assert store.get_owned(uid, player["id"]) == dict(player, name=name)
    finally:
        store.close()


def test_first_rename_rolls_back_failed_write(tmp_path):
    store = PlayerStore(tmp_path / "players.sqlite3")
    try:
        uid, _ = store.login_account("alice", "secret")
        player = store.create(uid, "alice", 1, 1)
        store.db.execute("CREATE TRIGGER reject_rename BEFORE UPDATE ON players BEGIN SELECT RAISE(ABORT, 'test failure'); END")
        with pytest.raises(sqlite3.IntegrityError, match="test failure"):
            store.rename(uid, player["id"], "Nami")
        assert not store.db.in_transaction
        assert store.get_owned(uid, player["id"]) == player
        store.db.execute("DROP TRIGGER reject_rename")
        assert store.rename(uid, player["id"], "Nami") == {"name": "Nami"}
    finally:
        store.close()


def test_concurrent_first_renames_cannot_both_replace_the_initial_name(tmp_path):
    path = tmp_path / "players.sqlite3"
    first, second = PlayerStore(path), PlayerStore(path)
    try:
        uid, _ = first.login_account("alice", "secret")
        player = first.create(uid, "alice", 1, 1)
        barrier = threading.Barrier(2, timeout=5)

        def choose(store, name):
            barrier.wait()
            return store.rename(uid, player["id"], name)

        with ThreadPoolExecutor(max_workers=2) as pool:
            calls = [pool.submit(choose, first, "Nami"), pool.submit(choose, second, "Robin")]
            results = [call.result(timeout=10) for call in calls]
        assert sum(result is not None for result in results) == 1
        chosen = next(result["name"] for result in results if result is not None)
        assert first.get_owned(uid, player["id"]) == dict(player, name=chosen)
        assert second.get_owned(uid, player["id"]) == dict(player, name=chosen)
    finally:
        first.close()
        second.close()


PROJECT_SOURCE = pathlib.Path(__file__).parents[3] / "client-recovered" / "src" / "project.js"
STARTER_VALUES = pathlib.Path(__file__).parent / "fixtures" / "starter-values.json"


def _pinned_table(name: str):
    source = PROJECT_SOURCE.read_text(encoding="utf-8")
    start = source.index(f'"{name}");\nt.exports = [') + len(f'"{name}");\nt.exports = ')
    end = source.index("];\ncc._RF.pop();", start) + 1
    return json.loads(source[start:end])


def _starter_role(kind_id: int):
    values = json.loads(STARTER_VALUES.read_text(encoding="utf-8"))
    role = values["completeLevel1RoleFixture"][str(kind_id)]
    # Keep the original zero-power evidence immutable; expected response now
    # includes the fields read by roleScene and eqptScene.
    role["power"] = 980.2 if kind_id == 100201 else 978.2
    role["attr"].update({"hpGrowth": 233, "atkGrowth": 9, "defGrowth": 21, "mdefGrowth": 21}
                        if kind_id == 100201 else {"hpGrowth": 159, "atkGrowth": 19, "defGrowth": 19, "mdefGrowth": 19})
    for slot, item in role["equipments"].items():
        attrs = {"hp": 0, "atk": 0, "def": 0, "mdef": 0, "hit": 0, "dodge": 0, "crit": 0}
        attrs.update({"hp": 551, "def": 51} if slot == "evlItem_1" else
                     {"mdef": 51, "dodge": 28} if slot == "evlItem_2" else {"atk": 20, "crit": 10})
        item["attrs"] = attrs
    return role


def test_create_is_idempotent_persists_and_encodes_home_candidate(tmp_path):
    state_path = tmp_path / "players.sqlite3"
    store = PlayerStore(state_path)
    try:
        uid, _ = store.login_account("alice", "secret")
        created = store.create(uid, "alice", 1, 1)
        repeated = store.create(uid, "alice", 1, 1)
        assert created["id"] == repeated["id"]
        assert created["userName"] == created["name"] == "alice"
        assert (created["gem"], created["coin"], created["level"]) == (50, 0, 1)
        role = created["team"]["roles"]["1"]
        expected_role = _starter_role(100201)
        expected_role.update(kindId=100101, skills={"100101": {"kindId": 100101, "level": 1}})
        assert role == expected_role
        goods = created["shop"]["goodsMap"]["1"]
        assert set(goods) == {"10001", "10002"}
        assert all(set(goods[str(index)]) == {"entityId", "moneyId", "price", "count", "isSaleOut", "requireVip", "shopType"}
                   for index in (10001, 10002))
        assert created["shop"]["refreshTimesMap"] == {"1": 0}
        assert created["shop"]["hideRoleClassIds"] == [63]
        assert all(goods[str(index)]["isSaleOut"] is False for index in (10001, 10002))
        cards = created["extra"]["goodsList"]
        assert [(card["isMonthCard"], card["isBigMonthCard"], card["isYearCard"], card["isWeekCard"])
                for card in cards] == [(1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 1, 0), (0, 0, 0, 1)]
        assert all(card["show"] == "Chưa hỗ trợ" for card in cards)
        assert created["timesMaxMap"] == {"actionPoint": 60, "skillPoint": 10}
        assert created["nextRecoverTimeMap"] == {"actionPoint": 0, "skillPoint": 0}
        assert (created["actionPoint"], created["skillPoint"]) == (60, 10)
        assert created["task"]["daily"] == {}
        assert created["task"]["receivedPointMap"] == {"daily": {}, "weekly": {}}
        assert (created["task"]["dailyActivePoint"], created["task"]["weeklyActivePoint"]) == (0, 0)
        assert created["extra"]["chat"] == {"worldList": [], "guildList": [], "allServerList": []}
        encoded = encode_player(created)
        assert json.loads(gzip.decompress(__import__("base64").b64decode(encoded)).decode("utf-8")) == created
    finally:
        store.close()

    reopened = PlayerStore(state_path)
    try:
        assert reopened.list_players(uid) == [{"id": created["id"]}]
        assert reopened.get_owned(uid, created["id"]) == created
        assert reopened.get_owned("uid-other", created["id"]) is None
    finally:
        reopened.close()


def test_hide_role_class_ids_cover_only_the_pinned_missing_friendship_class(tmp_path):
    role_rows = _pinned_table("roleData")
    friendship_rows = _pinned_table("friendshipData")
    role_classes = {row[1] for row in role_rows[1:]}
    required_classes = {class_id for row in friendship_rows[1:] for class_id in row[2]}
    missing_classes = required_classes - role_classes
    assert missing_classes == {63}

    store = PlayerStore(tmp_path / "players.sqlite3")
    try:
        uid, _ = store.login_account("alice", "secret")
        player = store.create(uid, "alice", 1, 1)
        hidden = set(player["shop"]["hideRoleClassIds"])
        assert required_classes - hidden <= role_classes
    finally:
        store.close()


def test_get_owned_migrates_and_persists_legacy_player_without_hidden_role_classes(tmp_path):
    state_path = tmp_path / "players.sqlite3"
    store = PlayerStore(state_path)
    try:
        uid, _ = store.login_account("alice", "secret")
        created = store.create(uid, "alice", 1, 1)
        legacy = json.loads(json.dumps(created))
        legacy["shop"].pop("hideRoleClassIds", None)
        legacy["task"].pop("daily", None)
        legacy["task"].pop("receivedPointMap", None)
        legacy["task"].pop("dailyActivePoint", None)
        legacy["task"].pop("weeklyActivePoint", None)
        store.db.execute("UPDATE players SET payload=? WHERE id=?", (json.dumps(legacy), created["id"]))
        store.db.commit()
    finally:
        store.close()

    reopened = PlayerStore(state_path)
    try:
        migrated = reopened.get_owned(uid, created["id"])
        assert migrated["shop"]["hideRoleClassIds"] == [63]
        assert migrated["task"]["daily"] == {}
        assert migrated["task"]["receivedPointMap"] == {"daily": {}, "weekly": {}}
        assert migrated["task"]["dailyActivePoint"] == migrated["task"]["weeklyActivePoint"] == 0
        stored = json.loads(reopened.db.execute("SELECT payload FROM players WHERE id=?", (created["id"],)).fetchone()[0])
        assert stored["shop"]["hideRoleClassIds"] == [63]
    finally:
        reopened.close()


def test_legacy_chat_normalization_merges_missing_lists_without_overwriting_existing_chat(tmp_path):
    state_path = tmp_path / "players.sqlite3"
    store = PlayerStore(state_path)
    try:
        uid, _ = store.login_account("alice", "secret")
        created = store.create(uid, "alice", 1, 1)
        legacy = json.loads(json.dumps(created))
        legacy["extra"]["chat"] = {"worldList": [{"message": "kept"}]}
        store.db.execute("UPDATE players SET payload=? WHERE id=?", (json.dumps(legacy), created["id"]))
        store.db.commit()
    finally:
        store.close()
    reopened = PlayerStore(state_path)
    try:
        migrated = reopened.get_owned(uid, created["id"])
        assert migrated["extra"]["chat"] == {"worldList": [{"message": "kept"}], "guildList": [], "allServerList": []}
    finally:
        reopened.close()


def test_create_rolls_back_when_candidate_serialization_fails(tmp_path, monkeypatch):
    store = PlayerStore(tmp_path / "players.sqlite3")
    try:
        uid, _ = store.login_account("alice", "secret")
        monkeypatch.setattr(store, "_candidate", lambda *_args: {"bad": {1, 2}})
        with pytest.raises(TypeError):
            store.create(uid, "alice", 1, 1)
        assert store.list_players(uid) == []
    finally:
        store.close()


def test_award_first_recruits_merges_luffy_and_persists_idempotently(tmp_path):
    store = PlayerStore(tmp_path / "players.sqlite3")
    try:
        uid, _ = store.login_account("alice", "secret")
        player = store.create(uid, "alice", 1, 1)
        first = store.award_recruit(uid, player["id"], "coin")
        assert first["code"] == 200
        assert first["team"]["roles"]["2"] == _starter_role(100201)
        assert first["_temp"]["dropList"] == [{"entityId": 100201, "count": 1, "extra": {"star": 1}}]
        assert store.get_owned(uid, player["id"])["team"]["roles"].keys() == {"1", "2"}
        assert store.get_owned(uid, player["id"])["point"]["freeCoinTimes"] == 1
        replay = store.award_recruit(uid, player["id"], "coin")
        assert replay == first
        second = store.award_recruit(uid, player["id"], "gem")
        assert second["team"]["roles"]["3"] == _starter_role(100301)
        assert store.get_owned(uid, player["id"])["team"]["roles"].keys() == {"1", "2", "3"}
        assert store.get_owned(uid, player["id"])["gem"] == 50
        assert store.award_recruit(uid, player["id"], "gem") == second
    finally:
        store.close()


def test_award_recruit_rejects_invalid_route_or_owner_without_mutation(tmp_path):
    store = PlayerStore(tmp_path / "players.sqlite3")
    try:
        uid, _ = store.login_account("alice", "secret")
        player = store.create(uid, "alice", 1, 1)
        before = store.get_owned(uid, player["id"])
        assert store.award_recruit(uid, player["id"], "paid") is None
        assert store.award_recruit("missing", player["id"], "coin") is None
        assert store.get_owned(uid, player["id"]) == before
    finally:
        store.close()


def test_award_recruit_rejects_active_free_draw_state_without_mutation(tmp_path):
    store = PlayerStore(tmp_path / "players.sqlite3")
    try:
        uid, _ = store.login_account("alice", "secret")
        player = store.create(uid, "alice", 1, 1)
        player["point"]["freeCoinTimes"] = 5
        player["point"]["nextGemFreeTime"] = 9_999_999_999_999
        store.db.execute("UPDATE players SET payload=? WHERE id=?", (json.dumps(player), player["id"]))
        store.db.commit()
        assert store.award_recruit(uid, player["id"], "coin") is None
        assert store.award_recruit(uid, player["id"], "gem") is None
        assert store.get_owned(uid, player["id"])["team"]["roles"] == {"1": player["team"]["roles"]["1"]}
    finally:
        store.close()


def test_candidate_and_legacy_normalization_have_first_smap_maps(tmp_path):
    state_path = tmp_path / "players.sqlite3"
    store = PlayerStore(state_path)
    try:
        uid, _ = store.login_account("alice", "secret")
        created = store.create(uid, "alice", 1, 1)
        assert created["actionPoint"] == 60
        assert created["smapStarMap"] == {"1": {"101": {"10101": 0, "10106": 0}}}
        assert created["smapTimesMap"] == {"1": {"101": {"10101": 0, "10106": 0}}}
        legacy = json.loads(json.dumps(created))
        legacy.pop("smapStarMap"); legacy.pop("smapTimesMap")
        store.db.execute("UPDATE players SET payload=? WHERE id=?", (json.dumps(legacy), created["id"]))
        store.db.commit()
    finally:
        store.close()
    reopened = PlayerStore(state_path)
    try:
        migrated = reopened.get_owned(uid, created["id"])
        assert migrated["smapStarMap"] == {"1": {"101": {"10101": 0, "10106": 0}}}
        assert migrated["smapTimesMap"] == {"1": {"101": {"10101": 0, "10106": 0}}}
    finally:
        reopened.close()


def test_recruit_awards_survive_store_reopen(tmp_path):
    state_path = tmp_path / "players.sqlite3"
    store = PlayerStore(state_path)
    uid, _ = store.login_account("alice", "secret")
    player = store.create(uid, "alice", 1, 1)
    store.award_recruit(uid, player["id"], "coin")
    store.award_recruit(uid, player["id"], "gem")
    store.close()
    reopened = PlayerStore(state_path)
    try:
        persisted = reopened.get_owned(uid, player["id"])
        assert set(persisted["team"]["roles"]) == {"1", "2", "3"}
        assert persisted["point"]["freeCoinTimes"] == 1
        assert persisted["point"]["isPayGemFirst"] is True
    finally:
        reopened.close()


@pytest.mark.parametrize("reader_name,mutation", [("get_owned", "rename"), ("create", "recruit")])
def test_normalization_serializes_with_other_store_mutations(tmp_path, monkeypatch, reader_name, mutation):
    path = tmp_path / "players.sqlite3"
    normalizer, writer = PlayerStore(path), PlayerStore(path)
    try:
        uid, _ = normalizer.login_account("alice", "secret")
        player = normalizer.create(uid, "alice", 1, 1)
        legacy = json.loads(json.dumps(player))
        legacy["extra"].pop("chat")
        normalizer.db.execute("UPDATE players SET payload=? WHERE id=?", (json.dumps(legacy), player["id"]))
        normalizer.db.commit()
        selected = threading.Event()
        mutation_done = threading.Event()
        original_normalize = normalizer._normalize_existing

        def pause_after_select(player_id, payload):
            selected.set()
            mutation_done.wait(0.5)
            return original_normalize(player_id, payload)

        monkeypatch.setattr(normalizer, "_normalize_existing", pause_after_select)

        def mutate():
            try:
                if mutation == "rename":
                    return writer.rename(uid, player["id"], "Nami")
                return writer.award_recruit(uid, player["id"], "coin")
            finally:
                mutation_done.set()

        with ThreadPoolExecutor(max_workers=2) as pool:
            if reader_name == "get_owned":
                read = pool.submit(normalizer.get_owned, uid, player["id"])
            else:
                read = pool.submit(normalizer.create, uid, "alice", 1, 1)
            assert selected.wait(2)
            write = pool.submit(mutate)
            read.result(timeout=5)
            assert write.result(timeout=5) is not None
        current = normalizer.get_owned(uid, player["id"])
        assert current["extra"]["chat"] == {"worldList": [], "guildList": [], "allServerList": []}
        if mutation == "rename":
            assert current["name"] == "Nami"
        else:
            assert current["team"]["roles"]["2"]["kindId"] == 100201
    finally:
        normalizer.close()
        writer.close()


def test_partial_smap_maps_are_recursively_completed_without_losing_progress(tmp_path):
    store = PlayerStore(tmp_path / "players.sqlite3")
    try:
        uid, _ = store.login_account("alice", "secret")
        player = store.create(uid, "alice", 1, 1)
        player["smapStarMap"] = {"1": {"101": {"10101": 3, "extra": 7}}, "2": {"kept": True}}
        player["smapTimesMap"] = {"1": {"other": {"kept": 9}}}
        store.db.execute("UPDATE players SET payload=? WHERE id=?", (json.dumps(player), player["id"]))
        store.db.commit()
        migrated = store.get_owned(uid, player["id"])
        assert migrated["smapStarMap"] == {
            "1": {"101": {"10101": 3, "10106": 0, "extra": 7}}, "2": {"kept": True}
        }
        assert migrated["smapTimesMap"] == {
            "1": {"other": {"kept": 9}, "101": {"10101": 0, "10106": 0}}
        }
    finally:
        store.close()


@pytest.mark.parametrize("reader_name", ["get_owned", "create"])
def test_failed_normalization_rolls_back_transaction_for_next_operation(tmp_path, reader_name):
    store = PlayerStore(tmp_path / "players.sqlite3")
    try:
        uid, _ = store.login_account("alice", "secret")
        player = store.create(uid, "alice", 1, 1)
        legacy = json.loads(json.dumps(player))
        legacy["extra"].pop("chat")
        store.db.execute("UPDATE players SET payload=? WHERE id=?", (json.dumps(legacy), player["id"]))
        store.db.execute("CREATE TRIGGER reject_normalize BEFORE UPDATE ON players BEGIN SELECT RAISE(ABORT, 'test failure'); END")
        store.db.commit()
        with pytest.raises(sqlite3.IntegrityError, match="test failure"):
            if reader_name == "get_owned":
                store.get_owned(uid, player["id"])
            else:
                store.create(uid, "alice", 1, 1)
        assert not store.db.in_transaction
        store.db.execute("DROP TRIGGER reject_normalize")
        assert store.get_owned(uid, player["id"])["extra"]["chat"] == {
            "worldList": [], "guildList": [], "allServerList": []
        }
    finally:
        store.close()


def test_existing_recruits_reconcile_absent_completion_markers_without_renewing_progress(tmp_path):
    store = PlayerStore(tmp_path / "players.sqlite3")
    try:
        uid, _ = store.login_account("alice", "secret")
        player = store.create(uid, "alice", 1, 1)
        player["team"]["roles"]["2"] = _starter_role(100201)
        player["team"]["roles"]["3"] = _starter_role(100301)
        player["point"] = {"nextCoinFreeTime": 123, "nextGemFreeTime": 456, "other": 9}
        store.db.execute("UPDATE players SET payload=? WHERE id=?", (json.dumps(player), player["id"]))
        store.db.commit()
        coin = store.award_recruit(uid, player["id"], "coin")
        gem = store.award_recruit(uid, player["id"], "gem")
        assert coin["point"] == {"freeCoinTimes": 1, "nextCoinFreeTime": 123}
        assert gem["point"] == {"isPayGemFirst": True, "nextGemFreeTime": 456}
        assert store.get_owned(uid, player["id"])["point"] == {
            "freeCoinTimes": 1, "isPayGemFirst": True,
            "gemTimes": 0,
            "nextCoinFreeTime": 123, "nextGemFreeTime": 456, "other": 9,
        }
    finally:
        store.close()


def test_existing_recruits_reconcile_false_and_zero_completion_markers(tmp_path):
    store = PlayerStore(tmp_path / "players.sqlite3")
    try:
        uid, _ = store.login_account("alice", "secret")
        player = store.create(uid, "alice", 1, 1)
        player["team"]["roles"]["2"] = _starter_role(100201)
        player["team"]["roles"]["3"] = _starter_role(100301)
        player["point"].update({"freeCoinTimes": 0, "isPayGemFirst": False})
        store.db.execute("UPDATE players SET payload=? WHERE id=?", (json.dumps(player), player["id"]))
        store.db.commit()
        assert store.award_recruit(uid, player["id"], "coin")["point"]["freeCoinTimes"] == 1
        assert store.award_recruit(uid, player["id"], "gem")["point"]["isPayGemFirst"] is True
        point = store.get_owned(uid, player["id"])["point"]
        assert point["freeCoinTimes"] == 1
        assert point["isPayGemFirst"] is True
        assert point["nextCoinFreeTime"] == player["point"]["nextCoinFreeTime"]
        assert point["nextGemFreeTime"] == player["point"]["nextGemFreeTime"]
    finally:
        store.close()


def test_existing_coin_recruit_retains_higher_free_counter(tmp_path):
    store = PlayerStore(tmp_path / "players.sqlite3")
    try:
        uid, _ = store.login_account("alice", "secret")
        player = store.create(uid, "alice", 1, 1)
        player["team"]["roles"]["2"] = _starter_role(100201)
        player["point"]["freeCoinTimes"] = 4
        store.db.execute("UPDATE players SET payload=? WHERE id=?", (json.dumps(player), player["id"]))
        store.db.commit()
        assert store.award_recruit(uid, player["id"], "coin")["point"]["freeCoinTimes"] == 4
        assert store.get_owned(uid, player["id"])["point"]["freeCoinTimes"] == 4
    finally:
        store.close()


def test_recruit_uses_unbounded_free_numeric_slot_without_overwriting_roles(tmp_path):
    store = PlayerStore(tmp_path / "players.sqlite3")
    try:
        uid, _ = store.login_account("alice", "secret")
        player = store.create(uid, "alice", 1, 1)
        sentinel = {"kindId": 999999}
        player["team"]["roles"] = {str(index): copy.deepcopy(sentinel) for index in range(1, 100)}
        store.db.execute("UPDATE players SET payload=? WHERE id=?", (json.dumps(player), player["id"]))
        store.db.commit()
        result = store.award_recruit(uid, player["id"], "coin")
        assert result["team"]["roles"]["100"]["kindId"] == 100201
        persisted = store.get_owned(uid, player["id"])["team"]["roles"]
        assert all(persisted[str(index)] == sentinel for index in range(1, 100))
        assert persisted["100"]["kindId"] == 100201
    finally:
        store.close()
