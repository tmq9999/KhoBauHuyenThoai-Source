from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from kbht_server.content import importer

SOURCE=Path(__file__).resolve().parents[3]/'client-recovered/src/project.js'
SHA='9776b6e20978d5d911bc0abb85830820bac5a3bfb8db4e65a617c5d18646a818'


def store(engine):
    assert hasattr(importer,'store_acquisition'),'acquisition persistence missing'
    return importer.store_acquisition(engine,SOURCE,SHA)


def test_persists_material_evidence_without_publication_and_replays(pg_engine):
    result=store(pg_engine)
    assert result['publishable'] is False
    assert result['zero_count_rows']==177
    material=next(row for row in result['materials'] if row['entity_id']==49902)
    assert material['fixed_boxes']==[321] and material['repeatable_normal_maps']==[]
    assert not material['gameplay_verified']
    pg_engine.dispose()
    assert store(pg_engine)==result
    with pg_engine.connect() as connection:
        bundle=connection.execute(text('SELECT bundle FROM content_dependency_archives')).scalar_one()
        assert bundle['sources']['stages']['10107']['specifyDropValues']==[125,125,125]
        for table in ('content_versions','game_servers','inventory_items','wallets'):
            assert connection.execute(text(f'SELECT count(*) FROM {table}')).scalar_one()==0


def test_parallel_acquisition_archive_and_dependency_archive_coexist(pg_engine):
    barrier=Barrier(2)
    def run(_):
        barrier.wait(timeout=10)
        return store(pg_engine)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(run,range(2)))
    assert results[0]==results[1]
    assert importer.store_dependencies(pg_engine,SOURCE,SHA)['reference_status']=='BLOCKED'
    with pg_engine.connect() as connection:
        assert connection.execute(text('SELECT count(*) FROM content_dependency_archives')).scalar_one()==2


def test_suppressed_write_rolls_back_instead_of_reporting_success(pg_engine):
    with pg_engine.begin() as connection:
        connection.execute(text('CREATE FUNCTION suppress_acquisition() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RETURN NULL; END $$'))
        connection.execute(text('CREATE TRIGGER suppress_acquisition BEFORE INSERT ON content_dependency_archives FOR EACH ROW EXECUTE FUNCTION suppress_acquisition()'))
    with pytest.raises(ValueError,match='mismatch'): store(pg_engine)
    with pg_engine.connect() as connection:
        assert connection.execute(text('SELECT count(*) FROM content_dependency_archives')).scalar_one()==0


def test_acquisition_snapshot_is_immutable(pg_engine):
    store(pg_engine)
    with pytest.raises(DBAPIError),pg_engine.begin() as connection:
        connection.execute(text("UPDATE content_dependency_archives SET bundle='{}'::jsonb"))


def test_acquisition_cli_includes_nonplayable_status(pg_engine,monkeypatch,capsys):
    import json
    from kbht_server import cli
    monkeypatch.setattr(cli,'open_engine',lambda *args,**kwargs:pg_engine)
    assert cli.main(['audit-acquisition','--environment','test','--source',str(SOURCE),'--source-sha256',SHA])==0
    result=json.loads(capsys.readouterr().out)
    assert result['publishable'] is False and result['zero_count_rows']==177
