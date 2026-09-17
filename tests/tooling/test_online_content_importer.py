import hashlib
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "server-online/src"))
from kbht_server.content.importer import import_release

def test_import_release_includes_stage_10107_from_pinned_source():
    root = Path(__file__).resolve().parents[2]
    release = import_release(root / "client-recovered/src/project.js", "9776b6e20978d5d911bc0abb85830820bac5a3bfb8db4e65a617c5d18646a818")
    assert 10107 in release.smap
    assert release.source_sha256 == "9776b6e20978d5d911bc0abb85830820bac5a3bfb8db4e65a617c5d18646a818"

def test_import_release_rejects_wrong_source_hash(tmp_path):
    path = tmp_path / "project.js"
    path.write_text('"smapData");\nt.exports = [["kindId"],[10107]];\ncc._RF.pop();')
    try:
        import_release(path, hashlib.sha256(b"wrong").hexdigest())
    except ValueError as error:
        assert "hash" in str(error)
    else:
        raise AssertionError("wrong source hash was accepted")
