"""Literal APK graph expectations; no JavaScript execution or database mocks."""
import hashlib
import sys
from copy import deepcopy
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "server-online/src"))
from kbht_server.content import importer
from kbht_server.content.source import read_table

SOURCE = Path(__file__).resolve().parents[2] / "client-recovered/src/project.js"
SHA = "9776b6e20978d5d911bc0abb85830820bac5a3bfb8db4e65a617c5d18646a818"


def test_sparse_chapters_preserve_missing_fields_explicitly(tmp_path):
    raw = b'"bmapData");\nt.exports = [["kindId","rankId","type"],[401,1],[101,1,1]];\ncc._RF.pop();'
    path = tmp_path / "source.js"
    path.write_bytes(raw)
    with pytest.raises(ValueError, match="row"):
        read_table(path, hashlib.sha256(raw).hexdigest(), "bmapData")
    rows = read_table(path, hashlib.sha256(raw).hexdigest(), "bmapData", allow_missing_trailing=True)
    assert rows[401] == {"kindId": 401, "rankId": 1}
    assert rows[101]["type"] == 1


def test_import_derives_normal_order_and_waves_from_chapter_relationship():
    release = importer.import_release(SOURCE, SHA)
    assert len(release.normal_maps) == 376
    assert len(release.bmap) == 69
    assert sum(len(wave) for row in release.normal_maps.values() for wave in row["waves"]) == 3722
    stage = release.normal_maps[10107]
    assert stage == {
        "chapter_id": 101, "chapter_rank": 1, "rank": 7,
        "predecessor_id": 10106, "action_point": 6, "level_limit": 0,
        "chapter_level_limit": 0, "times": 10, "role_exp": 20, "coin": 1200,
        "waves": [[1010711, 1010712, 1010713],
                  [1010721, 1010722, 1010723, 1010724, 1010725]],
    }
    assert release.normal_maps[10101]["predecessor_id"] is None
    assert release.normal_maps[10201]["predecessor_id"] == 10112
    assert 1 not in release.normal_maps and 20101 not in release.normal_maps
    assert release.smap[10107]["specifyDropValues"] == [125, 125, 125]


def minimal_graph():
    return ({900: {"kindId": 900, "rankId": 1, "type": 1, "levelLimit": 0}},
            {7: {"kindId": 7, "bmapId": 900, "rankId": 1, "actionPoint": 6,
                 "levelLimit": 0, "times": 10, "roleExp": 20, "coin": 1200,
                 "mobZoneCount": 2, "mobZone1": [31], "mobZone2": [32]}})


def validate(bmap, smap):
    return importer.normal_map_graph(bmap, smap)


@pytest.mark.parametrize("row", ['[]', '[401,1,1,99]'])
def test_sparse_mode_still_rejects_empty_and_overlong_rows(tmp_path, row):
    raw = ('"bmapData");\nt.exports = [["kindId","rankId","type"],' + row + '];\ncc._RF.pop();').encode()
    path = tmp_path / "source.js"
    path.write_bytes(raw)
    with pytest.raises(ValueError, match="row"):
        read_table(path, hashlib.sha256(raw).hexdigest(), "bmapData", allow_missing_trailing=True)


def test_map_identity_is_not_a_numeric_range():
    chapters, stages = minimal_graph()
    assert validate(chapters, stages)[7]["chapter_id"] == 900


@pytest.mark.parametrize("field,value", [
    ("bmapId", 999), ("bmapId", True), ("rankId", True), ("rankId", 0),
    ("actionPoint", -1), ("levelLimit", True), ("times", 0),
    ("roleExp", 2**53), ("coin", 1.5), ("mobZoneCount", 3),
    ("mobZone1", []), ("mobZone2", [False]), ("kindId", 8),
])
def test_invalid_normal_stage_is_rejected(field, value):
    chapters, stages = minimal_graph()
    stages[7][field] = value
    with pytest.raises(ValueError):
        validate(chapters, stages)


def test_duplicate_stage_rank_rejected():
    chapters, stages = minimal_graph()
    stages[8] = {**deepcopy(stages[7]), "kindId": 8}
    with pytest.raises(ValueError, match="rank"):
        validate(chapters, stages)


def test_empty_normal_chapter_rejected():
    chapters, stages = minimal_graph()
    chapters[901] = {"kindId": 901, "rankId": 2, "type": 1, "levelLimit": 0}
    with pytest.raises(ValueError, match="empty"):
        validate(chapters, stages)


@pytest.mark.parametrize("target", ["chapter", "stage"])
def test_rank_gap_cannot_silently_skip_content(target):
    chapters, stages = minimal_graph()
    if target == "chapter":
        chapters[901] = {"kindId": 901, "rankId": 3, "type": 1, "levelLimit": 0}
        stages[8] = {**deepcopy(stages[7]), "kindId": 8, "bmapId": 901}
    else:
        stages[8] = {**deepcopy(stages[7]), "kindId": 8, "rankId": 3}
    with pytest.raises(ValueError, match="rank"):
        validate(chapters, stages)


@pytest.mark.parametrize("field,value", [("type", True), ("rankId", True),
                                          ("levelLimit", -1), ("kindId", 901)])
def test_invalid_normal_chapter_rejected(field, value):
    chapters, stages = minimal_graph()
    chapters[900][field] = value
    with pytest.raises(ValueError):
        validate(chapters, stages)
