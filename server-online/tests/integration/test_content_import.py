from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

import pytest
from sqlalchemy import event, text
from sqlalchemy.exc import DBAPIError

from kbht_server.content import importer

SOURCE = Path(__file__).resolve().parents[3] / "client-recovered/src/project.js"
SHA = "9776b6e20978d5d911bc0abb85830820bac5a3bfb8db4e65a617c5d18646a818"


def test_import_roundtrip_replay_and_concurrency(pg_engine):
    assert hasattr(importer, "store_source"), "PostgreSQL content import not implemented"
    barrier = Barrier(2)
    def synchronize(connection, cursor, statement, parameters, context, executemany):
        if statement.startswith("INSERT INTO content_source_imports"):
            barrier.wait(timeout=10)
    event.listen(pg_engine, "before_cursor_execute", synchronize)
    try:
        with ThreadPoolExecutor(max_workers=2) as workers:
            results = list(workers.map(lambda _: importer.store_source(pg_engine, SOURCE, SHA), range(2)))
    finally:
        event.remove(pg_engine, "before_cursor_execute", synchronize)
    assert results[0] == results[1]
    assert results[0]["status"] == "STAGED"
    assert results[0]["rows"] > 6
    row = importer.load_source_row(pg_engine, results[0]["id"], 10107)
    assert row["kindId"] == 10107
    assert importer.load_source_row(pg_engine, results[0]["id"], 1)["kindId"] == 1
    with pg_engine.connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM content_source_imports")).scalar_one() == 1
        assert connection.execute(text("SELECT count(*) FROM content_source_rows")).scalar_one() == results[0]["rows"]


def test_failure_rolls_back_whole_import(pg_engine):
    assert hasattr(importer, "store_source"), "PostgreSQL content import not implemented"
    with pg_engine.begin() as connection:
        connection.execute(text("ALTER TABLE content_source_rows ADD CONSTRAINT fail_import CHECK (kind_id != 10107)"))
    with pytest.raises(DBAPIError):
        importer.store_source(pg_engine, SOURCE, SHA)
    with pg_engine.connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM content_source_imports")).scalar_one() == 0
        assert connection.execute(text("SELECT count(*) FROM content_source_rows")).scalar_one() == 0


def test_staged_source_cannot_be_rewritten(pg_engine):
    assert hasattr(importer, "store_source"), "PostgreSQL content import not implemented"
    result = importer.store_source(pg_engine, SOURCE, SHA)
    for statement in ("DELETE FROM content_source_rows", "UPDATE content_source_rows SET payload = '{}'", "TRUNCATE content_source_rows", "DELETE FROM content_source_imports"):
        with pytest.raises(DBAPIError), pg_engine.begin() as connection:
            connection.execute(text(statement))
    assert importer.load_source_row(pg_engine, result["id"], 10107)["kindId"] == 10107


def test_content_cli_roundtrip(pg_engine, monkeypatch, capsys):
    import json
    from kbht_server import cli

    monkeypatch.setattr(cli, "open_engine", lambda *args, **kwargs: pg_engine)
    assert cli.main(["import-content", "--environment", "test", "--source", str(SOURCE), "--source-sha256", SHA]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "STAGED"
    assert cli.main(["read-content", "--environment", "test", "--import-id", result["id"], "--kind-id", "10107"]) == 0
    assert json.loads(capsys.readouterr().out)["kindId"] == 10107
    assert cli.main(["prepare-content", "--environment", "test", "--import-id", result["id"]]) == 0
    draft = json.loads(capsys.readouterr().out)
    assert draft["status"] == "DRAFT"
    assert draft["source_import_id"] == result["id"]

def test_unvalidated_source_cannot_publish_or_open_server(pg_engine):
    from pg_lab import seed_players, CONTENT_ID
    seed_players(pg_engine, ())
    with pg_engine.begin() as connection:
        connection.execute(text("UPDATE game_servers SET status='MAINTENANCE' WHERE id=1"))
    result = importer.store_source(pg_engine, SOURCE, SHA)
    with pytest.raises(ValueError, match="validation"):
        importer.publish_source(pg_engine, result["id"], server_id=1)
    with pg_engine.connect() as connection:
        server = connection.execute(text("SELECT status, active_content_version_id FROM game_servers WHERE id=1")).one()
        assert tuple(server) == ("MAINTENANCE", CONTENT_ID)
        assert connection.execute(text("SELECT count(*) FROM content_versions")).scalar_one() == 1


def test_prepare_draft_preserves_server_and_replays(pg_engine):
    assert hasattr(importer, "prepare_draft"), "Draft preparation not implemented"
    result = importer.store_source(pg_engine, SOURCE, SHA)
    draft = importer.prepare_draft(pg_engine, result["id"])
    assert draft == importer.prepare_draft(pg_engine, result["id"])
    assert draft["status"] == "DRAFT"
    assert draft["source_import_id"] == result["id"]
    with pg_engine.connect() as connection:
        stored = connection.execute(text("SELECT status,source_sha256,rules_sha256 FROM content_versions WHERE id=:id"), {"id": draft["id"]}).one()
        assert tuple(stored) == ("DRAFT", SHA, draft["rules_sha256"])
        assert connection.execute(text("SELECT count(*) FROM game_servers")).scalar_one() == 0


def test_draft_replay_detects_changed_version(pg_engine):
    assert hasattr(importer, "prepare_draft")
    result = importer.store_source(pg_engine, SOURCE, SHA)
    draft = importer.prepare_draft(pg_engine, result["id"])
    with pg_engine.begin() as connection:
        connection.execute(text("UPDATE content_versions SET rules_sha256=:hash WHERE id=:id"), {"hash": "0" * 64, "id": draft["id"]})
    with pytest.raises(ValueError, match="mismatch"):
        importer.prepare_draft(pg_engine, result["id"])
