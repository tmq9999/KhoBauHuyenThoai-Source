from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.engine import URL, Engine, make_url


def validate_target(url: URL, environment: str) -> URL:
    if url.drivername != "postgresql+psycopg":
        raise ValueError("PostgreSQL with psycopg is required")
    names = {"test": "kbht_test", "development": "kbht_dev"}
    if environment not in names or url.database != names[environment]:
        raise ValueError("explicit test/development database is required")
    if url.host not in {"127.0.0.1", "::1", "localhost"}:
        raise ValueError("lab database must use loopback")
    if url.query:
        raise ValueError("database URL query overrides are not supported")
    return url


def database_url(environment: str) -> URL:
    variable = {"test": "KBHT_TEST_DATABASE_URL", "development": "KBHT_DATABASE_URL"}.get(environment)
    if variable is None:
        raise ValueError("explicit test/development database is required")
    if os.environ.get(variable):
        try:
            url = make_url(os.environ[variable])
        except Exception:
            raise ValueError("invalid database URL") from None
    else:
        password_file = os.environ.get("KBHT_DB_PASSWORD_FILE")
        if not password_file:
            raise ValueError("database URL or KBHT_DB_PASSWORD_FILE is required")
        url = URL.create(
            "postgresql+psycopg",
            username=os.environ.get("KBHT_DB_USER", "kbht_admin"),
            password=Path(password_file).read_text(encoding="ascii").strip(),
            host="127.0.0.1",
            port=int(os.environ.get("KBHT_DB_PORT", "25432")),
            database="kbht_test" if environment == "test" else "kbht_dev",
        )
    return validate_target(url, environment)


def open_engine(url: URL, *, schema: str | None = None) -> Engine:
    options = "-c timezone=UTC -c statement_timeout=15000 -c lock_timeout=10000"
    if schema is not None:
        import re

        if not re.fullmatch(r"kbht_(?:core|t_[0-9a-f]{32})", schema):
            raise ValueError("invalid database schema")
        options += f" -c search_path={schema}"
    return create_engine(
        url, hide_parameters=True, pool_pre_ping=True, pool_size=5, max_overflow=20,
        connect_args={"connect_timeout": 5, "options": options},
    )
