from __future__ import annotations

import sys
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy.schema import CreateSchema, DropSchema

SRC = Path(__file__).parents[1] / "src"
sys.path.insert(0, str(SRC))
sys.path.insert(0, str(Path(__file__).parent))


def _test_engine(create_schema: bool):
    from kbht_server.db.migrations import apply_migrations
    from kbht_server.db.session import database_url, open_engine

    url = database_url("test")
    schema = "kbht_t_" + uuid4().hex
    admin = open_engine(url)
    with admin.begin() as connection:
        assert connection.exec_driver_sql("SELECT current_database()").scalar_one() == "kbht_test"
        connection.execute(CreateSchema(schema))
    engine = open_engine(url, schema=schema)
    try:
        if create_schema:
            apply_migrations(engine)
        yield engine
    finally:
        engine.dispose()
        with admin.begin() as connection:
            connection.execute(DropSchema(schema, cascade=True))
        admin.dispose()


@pytest.fixture()
def pg_engine():
    yield from _test_engine(True)


@pytest.fixture()
def empty_pg_engine():
    yield from _test_engine(False)


@pytest.fixture()
def seeded_player(pg_engine):
    from pg_lab import seed_players

    seed_players(pg_engine, (10001,))
    return 10001


@pytest.fixture()
def pg_lab(pg_engine):
    from pg_lab import PGLab, seed_item_definitions, seed_players, test_counters

    seed_players(pg_engine, (10001, 10002), publish=False)
    seed_item_definitions(pg_engine)
    test_counters.create(pg_engine)
    return PGLab(pg_engine)
