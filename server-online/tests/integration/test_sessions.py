from uuid import UUID
from kbht_server.auth import SessionService
from sqlalchemy import text
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from sqlalchemy import event
import pytest

def test_session_issue_resolve_revoke(pg_engine, seeded_player):
    service = SessionService(pg_engine)
    token = service.issue(UUID("00000000-0000-4000-8000-000000000001"))
    assert service.resolve(token) == UUID("00000000-0000-4000-8000-000000000001")
    service.revoke(token)
    assert service.resolve(token) is None
    with pg_engine.connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM sessions WHERE token_hash=:hash"), {"hash": service._hash(token)}).scalar_one() == 1

def test_concurrent_issue_keeps_one_active_session(pg_engine, seeded_player):
    barrier = Barrier(2)
    def synchronize(connection, cursor, statement, parameters, context, executemany):
        if statement.startswith("SELECT id FROM accounts"):
            barrier.wait(timeout=5)
    event.listen(pg_engine, "before_cursor_execute", synchronize)
    try:
        with ThreadPoolExecutor(max_workers=2) as workers:
            tokens = list(workers.map(lambda _: SessionService(pg_engine).issue(UUID("00000000-0000-4000-8000-000000000001")), range(2)))
    finally:
        event.remove(pg_engine, "before_cursor_execute", synchronize)
    assert sum(SessionService(pg_engine).resolve(token) is not None for token in tokens) == 1

@pytest.mark.parametrize("ttl", [0, -1, True, 1000000])
def test_invalid_ttl_rejected(pg_engine, ttl):
    with pytest.raises(ValueError):
        SessionService(pg_engine, ttl_minutes=ttl)

def test_restart_and_expiration(pg_engine, seeded_player):
    token = SessionService(pg_engine).issue(UUID("00000000-0000-4000-8000-000000000001"))
    assert SessionService(pg_engine).resolve(token) is not None
    with pg_engine.begin() as connection:
        connection.execute(text("UPDATE sessions SET expires_at=now()-interval '1 second'"))
    assert SessionService(pg_engine).resolve(token) is None
