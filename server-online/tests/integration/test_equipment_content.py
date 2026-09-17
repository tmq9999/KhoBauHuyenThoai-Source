from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

import pytest
from sqlalchemy import inspect,text
from sqlalchemy.exc import DBAPIError
from kbht_server.content import importer

SOURCE=Path(__file__).resolve().parents[3]/'client-recovered/src/project.js'
SHA='9776b6e20978d5d911bc0abb85830820bac5a3bfb8db4e65a617c5d18646a818'


def prepare(engine):
    assert hasattr(importer,'prepare_equipment_draft'),'equipment persistence missing'
    return importer.prepare_equipment_draft(engine,SOURCE,SHA)


def test_equipment_draft_stores_target_cost_and_replays(pg_engine):
    result=prepare(pg_engine)
    assert result['status']=='DRAFT' and result['publishable'] is False
    assert result['equipment_count']==120 and result['requirement_count']==342
    pg_engine.dispose()
    assert prepare(pg_engine)==result
    with pg_engine.connect() as connection:
        rows=connection.execute(text('SELECT material_id,quantity FROM equipment_requirements WHERE kind_id=30102 ORDER BY position')).all()
        assert [tuple(row) for row in rows]==[(40102,1),(42102,1),(49902,1)]
        assert connection.execute(text('SELECT next_kind_id FROM equipment_definitions WHERE kind_id=30120')).scalar_one() is None
        assert connection.execute(text('SELECT count(*) FROM game_servers')).scalar_one()==0
        assert connection.execute(text('SELECT count(*) FROM item_definitions')).scalar_one()==0


def test_equipment_preparation_concurrent(pg_engine):
    barrier=Barrier(2)
    def run(_):
        barrier.wait(timeout=10)
        return prepare(pg_engine)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(run,range(2)))
    assert results[0]==results[1]
    with pg_engine.connect() as connection:
        assert connection.execute(text('SELECT count(*) FROM equipment_definitions')).scalar_one()==120


def test_recipe_failure_rolls_back_version_and_definitions(pg_engine):
    assert 'equipment_requirements' in inspect(pg_engine).get_table_names()
    with pg_engine.begin() as connection:
        connection.execute(text('ALTER TABLE equipment_requirements ADD CHECK (material_id != 49902)'))
    with pytest.raises(DBAPIError): prepare(pg_engine)
    with pg_engine.connect() as connection:
        for table in ('content_versions','equipment_source_snapshots','equipment_definitions','equipment_requirements'):
            assert connection.execute(text(f'SELECT count(*) FROM {table}')).scalar_one()==0


@pytest.mark.parametrize('sql',[
    'UPDATE equipment_requirements SET quantity=99 WHERE kind_id=30102',
    'DELETE FROM equipment_requirements WHERE kind_id=30102',
    "UPDATE equipment_definitions SET effect='{}'::jsonb WHERE kind_id=30102",
])
def test_replay_rejects_changed_projection(pg_engine,sql):
    prepare(pg_engine)
    with pg_engine.begin() as connection: connection.execute(text(sql))
    with pytest.raises(ValueError,match='mismatch'): prepare(pg_engine)


@pytest.mark.parametrize('sql',[
    'UPDATE equipment_requirements SET quantity=99 WHERE kind_id=30102',
    'DELETE FROM equipment_definitions WHERE kind_id=30101',
    'TRUNCATE equipment_requirements',
])
def test_published_equipment_cannot_mutate(pg_engine,sql):
    result=prepare(pg_engine)
    with pg_engine.begin() as connection:
        connection.execute(text("UPDATE content_versions SET status='PUBLISHED' WHERE id=:id"),{'id':result['id']})
    with pytest.raises(DBAPIError),pg_engine.begin() as connection: connection.execute(text(sql))


def test_equipment_cli_roundtrip(pg_engine,monkeypatch,capsys):
    import json
    from kbht_server import cli
    monkeypatch.setattr(cli,'open_engine',lambda *args,**kwargs:pg_engine)
    assert cli.main(['prepare-equipment','--environment','test','--source',str(SOURCE),'--source-sha256',SHA])==0
    result=json.loads(capsys.readouterr().out)
    assert result['equipment_count']==120 and result['publishable'] is False
