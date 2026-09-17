from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier
from uuid import NAMESPACE_URL, uuid5

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import DBAPIError

from kbht_server.content import importer

SOURCE = Path(__file__).resolve().parents[3] / 'client-recovered/src/project.js'
SHA = '9776b6e20978d5d911bc0abb85830820bac5a3bfb8db4e65a617c5d18646a818'


def store(engine):
    assert hasattr(importer,'store_dependencies'), 'durable dependency archive missing'
    return importer.store_dependencies(engine,SOURCE,SHA)


def test_archive_keeps_conflicts_and_replays_after_reconnect(pg_engine):
    result = store(pg_engine)
    assert result['reference_status'] == 'BLOCKED' and result['publishable'] is False
    pg_engine.dispose()
    assert store(pg_engine) == result
    with pg_engine.connect() as connection:
        bundle = connection.execute(text('SELECT bundle FROM content_dependency_archives')).scalar_one()
        rows = [row for row in bundle['tables']['fightSkillData']['rows'] if row[0]==1105010]
        assert len(rows)==2 and rows[0][14]==300 and rows[1][14]==600
        assert bundle['tables']['mobData']['rows'][0][0]==0
        assert connection.execute(text('SELECT count(*) FROM content_versions')).scalar_one()==0
        assert connection.execute(text('SELECT count(*) FROM game_servers')).scalar_one()==0


def test_concurrent_archive_deduplicates(pg_engine):
    barrier=Barrier(2)
    def run(_):
        barrier.wait(timeout=10)
        return store(pg_engine)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(run,range(2)))
    assert results[0]==results[1]
    with pg_engine.connect() as connection:
        assert connection.execute(text('SELECT count(*) FROM content_dependency_archives')).scalar_one()==1


@pytest.mark.parametrize('sql', [
    'DELETE FROM content_dependency_archives',
    "UPDATE content_dependency_archives SET bundle='{}'::jsonb",
    'TRUNCATE content_dependency_archives',
])
def test_archive_is_immutable(pg_engine,sql):
    store(pg_engine)
    with pytest.raises(DBAPIError),pg_engine.begin() as connection:
        connection.execute(text(sql))


def test_archive_insert_failure_leaves_no_rows(pg_engine):
    assert 'content_dependency_archives' in inspect(pg_engine).get_table_names()
    with pg_engine.begin() as connection:
        connection.execute(text('ALTER TABLE content_dependency_archives ADD CHECK (false)'))
    with pytest.raises(DBAPIError):
        store(pg_engine)
    with pg_engine.connect() as connection:
        assert connection.execute(text('SELECT count(*) FROM content_dependency_archives')).scalar_one()==0


def test_archive_cli_reports_blockers_not_gameplay_success(pg_engine,monkeypatch,capsys):
    import json
    from kbht_server import cli
    monkeypatch.setattr(cli,'open_engine',lambda *args,**kwargs:pg_engine)
    assert cli.main(['import-dependencies','--environment','test','--source',str(SOURCE),'--source-sha256',SHA])==0
    summary=json.loads(capsys.readouterr().out)
    assert summary['reference_status']=='BLOCKED' and summary['publishable'] is False
    assert summary['counts']['mobData']==16245
    assert any(issue['kind_id']==1105010 for issue in summary['issues'])


def test_mismatching_preexisting_archive_is_not_overwritten(pg_engine):
    from kbht_server.content.dependencies import FORMAT
    archive_id=uuid5(NAMESPACE_URL,f'kbht:dependency:{SHA}:{FORMAT}')
    with pg_engine.begin() as connection:
        connection.execute(text("INSERT INTO content_dependency_archives(id,source_sha256,format,bundle_sha256,bundle) VALUES (:id,:sha,:format,:digest,'{}'::jsonb)"),
                           {'id':archive_id,'sha':SHA,'format':FORMAT,'digest':'0'*64})
    with pytest.raises(ValueError,match='archive mismatch'):
        store(pg_engine)
    with pg_engine.connect() as connection:
        assert connection.execute(text('SELECT bundle FROM content_dependency_archives')).scalar_one()=={}


def test_suppressed_archive_write_cannot_report_success(pg_engine):
    with pg_engine.begin() as connection:
        connection.execute(text('CREATE FUNCTION suppress_archive() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RETURN NULL; END $$'))
        connection.execute(text('CREATE TRIGGER suppress_archive BEFORE INSERT ON content_dependency_archives FOR EACH ROW EXECUTE FUNCTION suppress_archive()'))
    with pytest.raises(ValueError,match='archive mismatch'):
        store(pg_engine)
    with pg_engine.connect() as connection:
        assert connection.execute(text('SELECT count(*) FROM content_dependency_archives')).scalar_one()==0
