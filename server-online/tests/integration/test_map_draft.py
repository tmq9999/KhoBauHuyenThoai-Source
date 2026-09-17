from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import DBAPIError

from kbht_server.content import importer

SOURCE = Path(__file__).resolve().parents[3] / "client-recovered/src/project.js"
SHA = "9776b6e20978d5d911bc0abb85830820bac5a3bfb8db4e65a617c5d18646a818"


def require_tables(engine):
    assert {"content_chapter_sources", "normal_map_definitions", "normal_map_waves"} <= set(inspect(engine).get_table_names())


def prepare(engine):
    require_tables(engine)
    source = importer.store_source(engine, SOURCE, SHA)
    return source, importer.prepare_draft(engine, source["id"])


def test_materializes_literal_graph_waves_and_replays(pg_engine):
    source, draft = prepare(pg_engine)
    assert importer.prepare_draft(pg_engine, source["id"]) == draft
    with pg_engine.connect() as connection:
        params = {"id": draft["id"]}
        assert connection.execute(text("SELECT count(*) FROM normal_map_definitions WHERE content_version_id=:id"), params).scalar_one() == 376
        assert connection.execute(text("SELECT count(*) FROM normal_map_waves WHERE content_version_id=:id"), params).scalar_one() == 3722
        stage = connection.execute(text("SELECT chapter_id,predecessor_id,action_point,coin,role_exp FROM normal_map_definitions WHERE content_version_id=:id AND kind_id=10107"), params).one()
        assert tuple(stage) == (101, 10106, 6, 1200, 20)
        assert connection.execute(text("SELECT predecessor_id FROM normal_map_definitions WHERE content_version_id=:id AND kind_id=10201"), params).scalar_one() == 10112
        assert connection.execute(text("SELECT mob_id FROM normal_map_waves WHERE content_version_id=:id AND map_id=10107 ORDER BY zone,position"), params).scalars().all() == [1010711,1010712,1010713,1010721,1010722,1010723,1010724,1010725]
        assert connection.execute(text("SELECT count(*) FROM game_servers")).scalar_one() == 0
        chapters = connection.execute(text("SELECT payload FROM content_chapter_sources WHERE import_id=:id"), {"id": source["id"]}).scalar_one()
        assert len(chapters) == 69
        assert "type" not in chapters["401"]


def test_concurrent_preparation_is_one_draft(pg_engine):
    require_tables(pg_engine)
    source = importer.store_source(pg_engine, SOURCE, SHA)
    barrier = Barrier(2)
    def run(_):
        barrier.wait(timeout=10)
        return importer.prepare_draft(pg_engine, source["id"])
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(run, range(2)))
    assert results[0] == results[1]
    with pg_engine.connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM content_versions")).scalar_one() == 1


def test_failure_rolls_back_version_maps_and_waves(pg_engine):
    require_tables(pg_engine)
    source = importer.store_source(pg_engine, SOURCE, SHA)
    with pg_engine.begin() as connection:
        connection.execute(text("ALTER TABLE normal_map_waves ADD CHECK (mob_id != 1010711)"))
    with pytest.raises(DBAPIError):
        importer.prepare_draft(pg_engine, source["id"])
    with pg_engine.connect() as connection:
        for table in ("content_versions", "normal_map_definitions", "normal_map_waves"):
            assert connection.execute(text(f"SELECT count(*) FROM {table}")).scalar_one() == 0


@pytest.mark.parametrize("sql", [
    "UPDATE normal_map_definitions SET coin=999 WHERE kind_id=10107",
    "DELETE FROM normal_map_waves WHERE map_id=10107 AND zone=1 AND position=1",
    "INSERT INTO normal_map_waves SELECT content_version_id,map_id,zone,99,mob_id FROM normal_map_waves WHERE map_id=10107 AND zone=1 AND position=1",
])
def test_replay_rejects_changed_missing_or_extra_projection(pg_engine, sql):
    source, _ = prepare(pg_engine)
    with pg_engine.begin() as connection:
        connection.execute(text(sql))
    with pytest.raises(ValueError, match="mismatch"):
        importer.prepare_draft(pg_engine, source["id"])


@pytest.mark.parametrize("sql", [
    "UPDATE normal_map_definitions SET coin=999 WHERE kind_id=10107",
    "DELETE FROM normal_map_waves WHERE map_id=10107",
    "INSERT INTO normal_map_waves SELECT content_version_id,map_id,zone,99,mob_id FROM normal_map_waves WHERE map_id=10107 AND zone=1 AND position=1",
    "TRUNCATE normal_map_waves",
])
def test_published_map_projection_immutable(pg_engine, sql):
    _, draft = prepare(pg_engine)
    # Owner-only fixture publication tests guards; importer never publishes.
    with pg_engine.begin() as connection:
        connection.execute(text("UPDATE content_versions SET status='PUBLISHED' WHERE id=:id"), {"id": draft["id"]})
    with pytest.raises(DBAPIError), pg_engine.begin() as connection:
        connection.execute(text(sql))


def test_legacy_smap_only_import_requires_verified_chapter_backfill(pg_engine):
    require_tables(pg_engine)
    # Seed the old persisted shape, without bypassing current importer behavior.
    from kbht_server.content.source import read_table
    rows = read_table(SOURCE, SHA, "smapData")
    source = {"id": uuid4(), "status": "STAGED", "rows": len(rows)}
    with pg_engine.begin() as connection:
        connection.execute(text("INSERT INTO content_source_imports(id,source_sha256,table_name,status,row_count) VALUES (:id,:sha,'smapData','STAGED',:count)"), {"id": source["id"], "sha": SHA, "count": len(rows)})
        connection.execute(text("INSERT INTO content_source_rows(import_id,kind_id,payload) VALUES (:id,:kind,CAST(:payload AS jsonb))"),
                           [{"id": source["id"], "kind": key, "payload": json.dumps(row)} for key, row in rows.items()])
    with pytest.raises(ValueError, match="chapter"):
        importer.prepare_draft(pg_engine, source["id"])
    assert importer.store_source(pg_engine, SOURCE, SHA) == source
    assert importer.prepare_draft(pg_engine, source["id"])["status"] == "DRAFT"


def test_suppressed_chapter_write_cannot_report_success(pg_engine):
    require_tables(pg_engine)
    with pg_engine.begin() as connection:
        connection.execute(text("CREATE FUNCTION suppress_chapter() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RETURN NULL; END $$"))
        connection.execute(text("CREATE TRIGGER suppress_chapter BEFORE INSERT ON content_chapter_sources FOR EACH ROW EXECUTE FUNCTION suppress_chapter()"))
    with pytest.raises(ValueError, match="chapter source mismatch"):
        importer.store_source(pg_engine, SOURCE, SHA)
    with pg_engine.connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM content_source_imports")).scalar_one() == 0
