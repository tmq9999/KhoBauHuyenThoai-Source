import hashlib
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'server-online/src'))
from kbht_server.content import source


def fixture(tmp_path, rows):
    raw = ('"mobData");\nt.exports = ' + rows + ';\ncc._RF.pop();').encode()
    path = tmp_path / 'source.js'
    path.write_bytes(raw)
    return path, hashlib.sha256(raw).hexdigest()


def test_boolean_literals_are_converted_without_touching_strings(tmp_path):
    path, sha = fixture(tmp_path, '[["kindId","extra"],[1,{flag:!0,no:!1,text:"!0 !1",rate:-.5}]]')
    assert source.read_table(path, sha, 'mobData')[1]['extra'] == {
        'flag': True, 'no': False, 'text': '!0 !1', 'rate': -0.5}


def test_audit_rows_preserve_sentinel_duplicates_and_missing_cells(tmp_path):
    path, sha = fixture(tmp_path, '[["kindId","name"],[0,"ship"],[1,"first"],[1]]')
    assert hasattr(source, 'read_table_archive'), 'ordered literal archive missing'
    archive = source.read_table_archive(path, sha, 'mobData')
    assert archive == {'columns': ['kindId', 'name'], 'rows': [[0, 'ship'], [1, 'first'], [1]]}
    with pytest.raises(ValueError):
        source.read_table(path, sha, 'mobData', allow_missing_trailing=True)


@pytest.mark.parametrize('value', ['!2', '!0+1', '!!0', '(function(){return 1})()', 'NaN', '1e999'])
def test_archive_rejects_executable_or_nonfinite_values(tmp_path, value):
    path, sha = fixture(tmp_path, '[["kindId","value"],[1,' + value + ']]')
    assert hasattr(source, 'read_table_archive'), 'ordered literal archive missing'
    with pytest.raises(ValueError):
        source.read_table_archive(path, sha, 'mobData')


def test_archive_rejects_wrong_hash(tmp_path):
    path, _ = fixture(tmp_path, '[["kindId"],[0]]')
    assert hasattr(source, 'read_table_archive'), 'ordered literal archive missing'
    with pytest.raises(ValueError, match='hash'):
        source.read_table_archive(path, '0' * 64, 'mobData')
