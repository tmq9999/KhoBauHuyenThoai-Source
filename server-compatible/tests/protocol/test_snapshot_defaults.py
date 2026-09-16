import copy
import json
from pathlib import Path
import sys

import pytest


sys.path.insert(0, str(Path(__file__).parents[2] / "src"))
from game_state import PlayerStore

FIXTURE = Path(__file__).parent / "fixtures/core-snapshot-defaults.json"


def assert_ui_defaults(player):
    expected = json.loads(FIXTURE.read_text(encoding="utf-8"))
    for group in ("vip", "point", "friend"):
        for key, value in expected[group].items():
            assert player[group][key] == value


def test_fresh_player_snapshot_has_zero_counters_instead_of_undefined(tmp_path):
    store = PlayerStore(tmp_path / "test.sqlite3")
    try:
        uid, _ = store.login_account("defaults-lab", "pw")
        player = store.create(uid, "defaults-lab", 1, 1)
        assert_ui_defaults(player)
        assert store.get_owned(uid, player["id"]) == player
    finally:
        store.close()


@pytest.mark.parametrize("method", ["entry", "create"])
def test_legacy_counters_added_without_resetting_existing_progress(tmp_path, method):
    path = tmp_path / "test.sqlite3"
    store = PlayerStore(path)
    uid, _ = store.login_account("defaults-lab", "pw")
    player = store.create(uid, "defaults-lab", 1, 1)
    expected = json.loads(FIXTURE.read_text(encoding="utf-8"))
    for group in ("vip", "point", "friend"):
        for key in expected[group]:
            player[group].pop(key, None)
    player["vip"].update(buyCoinTimes=3, resetSmapTimesTimesMap={"1": {"101": {"10102": 1}}})
    player["point"]["gemTimes"] = 7
    original = copy.deepcopy(player)
    store.db.execute("UPDATE players SET payload=? WHERE id=?", (json.dumps(player), player["id"]))
    store.db.commit()
    store.close()
    store = PlayerStore(path)
    try:
        repaired = store.get_owned(uid, player["id"]) if method == "entry" else store.create(uid, "defaults-lab", 1, 1)
        assert repaired["vip"]["buyCoinTimes"] == 3
        assert repaired["point"]["gemTimes"] == 7
        assert repaired["vip"]["resetSmapTimesTimesMap"] == {"1": {"101": {"10102": 1}}}
        assert repaired["vip"]["buyActionPointTimes"] == 0
        assert repaired["vip"]["buySkillPointTimes"] == 0
        assert repaired["friend"]["actionPointReceiveTimes"] == 0
        assert repaired["bag"] == original["bag"] and repaired["team"] == original["team"]
        assert repaired["coin"] == original["coin"] and repaired["gem"] == original["gem"]
        assert json.loads(store.db.execute("SELECT payload FROM players").fetchone()[0]) == repaired
    finally:
        store.close()
