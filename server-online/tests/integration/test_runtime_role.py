from uuid import uuid4

import pytest
from sqlalchemy import event, text
from sqlalchemy.exc import DBAPIError

from kbht_server.db.permissions import grant_runtime_access
from kbht_server.db.session import open_engine
from kbht_server.db.migrations import check_invariants
from kbht_server.db.uow import CommandExecutor
from kbht_server.workers.outbox import OutboxConsumer
from kbht_server.workers.poller import OutboxPoller


@pytest.fixture()
def runtime_lab(pg_lab):
    engine = pg_lab.engine
    role = "kbht_test_runtime_" + uuid4().hex
    with engine.begin() as connection:
        schema = connection.execute(text("SELECT current_schema()")).scalar_one()
        connection.execute(text(f'CREATE ROLE "{role}" NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS'))
        grant_runtime_access(connection, role)
    runtime = open_engine(engine.url, schema=schema)

    @event.listens_for(runtime, "connect")
    def assume_runtime(dbapi_connection, _):
        dbapi_connection.autocommit = True
        with dbapi_connection.cursor() as cursor:
            cursor.execute(f'SET ROLE "{role}"')
        dbapi_connection.autocommit = False

    try:
        yield pg_lab, runtime, role
    finally:
        runtime.dispose()
        # Role is generated here and owns no data; revoke only its test-schema grants.
        with engine.begin() as connection:
            connection.execute(text(f'REVOKE ALL ON ALL TABLES IN SCHEMA "{schema}" FROM "{role}"'))
            connection.execute(text(f'REVOKE UPDATE (version, updated_at) ON players FROM "{role}"'))
            connection.execute(text(f'REVOKE UPDATE (balance, version, updated_at) ON wallets FROM "{role}"'))
            connection.execute(text(f'REVOKE UPDATE (quantity, version, updated_at) ON inventory_items FROM "{role}"'))
            connection.execute(text(f'REVOKE UPDATE (status, attempts, lease_token, lease_expires_at, next_attempt_at, last_error_code, updated_at) ON outbox_deliveries FROM "{role}"'))
            for table, column in (("game_servers", "id"), ("content_versions", "id"),
                                  ("item_definitions", "content_version_id"), ("outbox_events", "id")):
                connection.execute(text(f'REVOKE UPDATE ({column}) ON {table} FROM "{role}"'))
            connection.execute(text(f'REVOKE ALL ON ALL SEQUENCES IN SCHEMA "{schema}" FROM "{role}"'))
            connection.execute(text(f'REVOKE ALL ON SCHEMA "{schema}" FROM "{role}"'))
            connection.execute(text(f'DROP ROLE "{role}"'))


def test_runtime_can_settle_inventory_wallet_receipt_and_consume_event(runtime_lab):
    lab, runtime, role = runtime_lab
    source = uuid4()
    command = lab.inventory_command(10001, {}, key="runtime-grant")
    def handler(work, _):
        work.adjust_wallet("gem", -10, reason="runtime-test")
        return work.rewards.grant(source_type="test-runtime", source_id=source, items={49902: 2}, currencies={"coin": 100})
    executor = CommandExecutor(runtime, {command.route: handler})
    result = executor.execute(command)
    assert executor.execute(command) == result
    event_id = result.event_ids[0]
    def read_projection(connection, evt):
        assert evt.player_id == 10001
        assert connection.execute(text("SELECT current_user")).scalar_one() == role
    consumer = OutboxConsumer(runtime, "runtime-verification", {"reward.granted": read_projection})
    assert consumer.consume(event_id) is True
    assert consumer.consume(event_id) is False
    assert lab.item_quantity(10001, 49902) == 2
    assert lab.wallet(10001, "gem") == 40
    assert lab.wallet(10001, "coin") == 100
    assert not any(check_invariants(runtime).values())


def test_runtime_can_poll_lease_and_finish_delivery(runtime_lab):
    lab, runtime, role = runtime_lab
    event_id = lab.emit_progress_event(10001, "drawTimes", 1)
    def handler(connection, event):
        assert connection.execute(text("SELECT current_user")).scalar_one() == role
    worker = OutboxPoller(OutboxConsumer(runtime, "runtime-poller", {"test.progress": handler}))
    assert worker.poll_once() == "DONE"
    assert worker.poll_once() == "IDLE"
    assert lab.worker_receipt_count(event_id) == 1


@pytest.mark.parametrize("sql", [
    "UPDATE wallet_ledger SET delta = 99", "DELETE FROM reward_grants", "TRUNCATE inventory_ledger",
    "UPDATE outbox_events SET body = '{}'::jsonb", "DELETE FROM worker_receipts",
    "ALTER TABLE inventory_items DISABLE TRIGGER ALL", "CREATE TABLE runtime_forbidden (id integer)",
    "SELECT password_hash FROM accounts", "UPDATE players SET account_id = gen_random_uuid()",
    "UPDATE inventory_items SET player_id = 10002", "UPDATE content_versions SET status = 'DRAFT'",
    "UPDATE game_servers SET status = 'CLOSED'",
])
def test_runtime_cannot_edit_history_content_ownership_or_ddl(runtime_lab, sql):
    _, engine, _ = runtime_lab
    with pytest.raises(DBAPIError) as failure:
        with engine.begin() as connection:
            connection.execute(text(sql))
    assert failure.value.orig.sqlstate == "42501"


def test_permission_provision_rejects_superuser(pg_engine):
    with pg_engine.begin() as connection:
        role = connection.execute(text("SELECT current_user")).scalar_one()
        with pytest.raises(ValueError, match="dedicated"):
            grant_runtime_access(connection, role)


def test_runtime_cannot_change_server_identity(runtime_lab):
    lab, engine, _ = runtime_lab
    with lab.engine.begin() as connection:
        connection.execute(text("INSERT INTO game_servers (id, name) VALUES (2, 'empty-test-server')"))
    with pytest.raises(DBAPIError, match="server identity"):
        with engine.begin() as connection:
            connection.execute(text("UPDATE game_servers SET id = 3 WHERE id = 2"))


def test_runtime_grants_are_repeatable_without_expanding_permissions(runtime_lab):
    lab, engine, role = runtime_lab
    with lab.engine.begin() as connection:
        grant_runtime_access(connection, role)
    with engine.connect() as connection:
        assert connection.execute(text("SELECT current_user")).scalar_one() == role
        assert connection.execute(text("SELECT count(*) FROM players")).scalar_one() == 2


@pytest.mark.parametrize("grant", [
    "GRANT UPDATE ON wallet_ledger TO {role}",
    "GRANT SELECT ON accounts TO {role}",
    "GRANT UPDATE (account_id) ON players TO {role}",
    "GRANT CREATE ON SCHEMA {schema} TO {role}",
])
def test_provisioning_rejects_preexisting_excess_privileges(runtime_lab, grant):
    lab, _, role = runtime_lab
    with lab.engine.begin() as connection:
        schema = connection.execute(text("SELECT current_schema()")).scalar_one()
        try:
            with connection.begin_nested():
                connection.execute(text(grant.format(role=f'"{role}"', schema=f'"{schema}"')))
                with pytest.raises(ValueError, match="privilege"):
                    grant_runtime_access(connection, role)
                raise RuntimeError("rollback test-only excess grant")
        except RuntimeError as error:
            assert str(error) == "rollback test-only excess grant"


def test_provisioning_rejects_table_owner_even_when_schema_has_another_owner(runtime_lab):
    lab, _, role = runtime_lab
    with lab.engine.begin() as connection:
        try:
            with connection.begin_nested():
                connection.execute(text(f'ALTER TABLE test_counters OWNER TO "{role}"'))
                with pytest.raises(ValueError, match="non-owner"):
                    grant_runtime_access(connection, role)
                raise RuntimeError("rollback test-only owner")
        except RuntimeError as error:
            assert str(error) == "rollback test-only owner"


def test_provisioning_rejects_inheriting_role(runtime_lab):
    lab, _, role = runtime_lab
    with lab.engine.begin() as connection:
        try:
            with connection.begin_nested():
                connection.execute(text(f'ALTER ROLE "{role}" INHERIT'))
                with pytest.raises(ValueError, match="unprivileged"):
                    grant_runtime_access(connection, role)
                raise RuntimeError("rollback test-only inherit")
        except RuntimeError as error:
            assert str(error) == "rollback test-only inherit"
