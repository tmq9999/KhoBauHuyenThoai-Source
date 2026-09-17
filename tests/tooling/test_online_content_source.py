import hashlib
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "server-online/src"))
from kbht_server.content.source import read_table


def read_fixture(tmp_path, rows):
    raw = ('"smapData");\nt.exports = ' + rows + ';\ncc._RF.pop();').encode()
    path = tmp_path / "project.js"
    path.write_bytes(raw)
    return read_table(path, hashlib.sha256(raw).hexdigest(), "smapData")


def test_literal_strings_and_json_values_are_preserved(tmp_path):
    rows = read_fixture(tmp_path, '[["kindId","value"],[10107,{name:"function(): new",enabled:true,missing:null,rate:.5}]]')
    assert rows[10107]["value"] == {"name": "function(): new", "enabled": True, "missing": None, "rate": 0.5}


@pytest.mark.parametrize("rows", [
    '[["kindId"],[10107],[10107]]',
    '[["kindId","name"],[10107]]',
    '[["kindId","kindId"],[10107,10108]]',
    '[["kindId"],[true]]',
    '[["kindId"],[9007199254740992]]',
    '[["kindId","value"],[10107,NaN]]',
    '[["kindId","value"],[10107,1e999]]',
    '[["kindId","value"],[10107,(function(){return 1})()]]',
])
def test_invalid_content_is_rejected(tmp_path, rows):
    with pytest.raises(ValueError):
        read_fixture(tmp_path, rows)


def test_wrong_hash_rejected(tmp_path):
    path = tmp_path / "project.js"
    path.write_text("not trusted")
    with pytest.raises(ValueError, match="hash"):
        read_table(path, "0" * 64, "smapData")


def test_reads_real_pinned_stage_seven():
    root = Path(__file__).resolve().parents[2]
    rows = read_table(root / "client-recovered/src/project.js", "9776b6e20978d5d911bc0abb85830820bac5a3bfb8db4e65a617c5d18646a818", "smapData")
    assert rows[10107]["kindId"] == 10107
    assert len(rows) > 6
