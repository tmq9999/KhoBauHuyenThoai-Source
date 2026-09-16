from __future__ import annotations

import pytest
from sqlalchemy.engine import URL

from kbht_server.db.session import validate_target


@pytest.mark.parametrize("database", ["kbht_test_prod", "postgres", "kbht_dev", None])
def test_test_target_requires_exact_database_name(database):
    target = URL.create("postgresql+psycopg", host="127.0.0.1", database=database)
    with pytest.raises(ValueError, match="database"):
        validate_target(target, "test")


@pytest.mark.parametrize("host", ["example.com", "0.0.0.0", None])
def test_lab_target_refuses_non_loopback(host):
    with pytest.raises(ValueError, match="loopback"):
        validate_target(URL.create("postgresql+psycopg", host=host, database="kbht_test"), "test")


def test_target_refuses_sqlite():
    with pytest.raises(ValueError, match="PostgreSQL"):
        validate_target(URL.create("sqlite", database="kbht_test"), "test")


def test_supported_target_preserves_encoded_credentials():
    target = URL.create("postgresql+psycopg", host="127.0.0.1", database="kbht_test", password="test+/@:")
    assert validate_target(target, "test") == target
