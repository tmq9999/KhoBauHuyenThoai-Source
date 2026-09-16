import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select, text
from sqlalchemy.schema import DropSchema

from kbht_server.db.migrations import check_invariants
from kbht_server.db.schema import (
    accounts, command_receipts, content_versions, game_servers, inventory_items,
    inventory_ledger, item_definitions, ledger_postings, ledger_transactions,
    outbox_events, players, reward_currencies, reward_grants, reward_items, wallets, wallet_ledger,
    worker_receipts, outbox_deliveries,
)
from kbht_server.db.uow import CommandExecutor
from kbht_server.workers.poller import OutboxPoller


def checked_test_schema(engine):
    with engine.connect() as connection:
        assert connection.execute(text("SELECT current_database()")).scalar_one() == "kbht_test"
        schema = connection.execute(text("SELECT current_schema()")).scalar_one()
    if not re.fullmatch(r"kbht_t_[0-9a-f]{32}", schema):
        raise RuntimeError("durability tests require a disposable test schema")
    return schema


def reward_handler(work, payload):
    work.adjust_wallet("gem", -10, reason="crash-probe")
    return work.rewards.grant(source_type="test-crash", source_id=UUID(payload["source"]),
                              items={49902: 2}, currencies={"coin": 100})


@pytest.mark.parametrize("phase,exit_code", [("before-commit", 71), ("after-commit", 72)])
def test_process_loss_cannot_lose_or_duplicate_a_command(pg_lab, phase, exit_code):
    schema = checked_test_schema(pg_lab.engine)
    command = pg_lab.inventory_command(10001, {"source": str(uuid4())}, key=str(uuid4()), route="internal.crash-probe")
    script = Path(__file__).parents[1] / "crash_command.py"
    result = subprocess.run(
        [sys.executable, "-I", str(script), schema, phase, str(command.command_id), command.payload["source"]],
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == exit_code, result.stderr
    if phase == "before-commit":
        assert pg_lab.wallet(10001, "gem") == 50
        assert pg_lab.items(10001) == []
        assert pg_lab.receipt_count(command.command_id) == 0
        assert pg_lab.events(command.command_id) == []
    else:
        assert pg_lab.wallet(10001, "gem") == 40
        assert pg_lab.item_quantity(10001, 49902) == 2
        assert pg_lab.receipt_count(command.command_id) == 1
    executor = CommandExecutor(pg_lab.engine, {command.route: reward_handler})
    first = executor.execute(command)
    pg_lab.engine.dispose()
    assert executor.execute(command) == first
    assert pg_lab.wallet(10001, "gem") == 40
    assert pg_lab.wallet(10001, "coin") == 100
    assert pg_lab.item_quantity(10001, 49902) == 2
    assert not any(check_invariants(pg_lab.engine).values())


def pg_tool(name):
    configured = os.environ.get("KBHT_PG_BIN")
    if configured:
        candidate = Path(configured) / (name + (".exe" if os.name == "nt" else ""))
    else:
        candidate = Path(__file__).parents[3] / "work/m1-env/postgresql-18.6/pgsql/bin" / f"{name}.exe"
    if candidate.is_file():
        return str(candidate.resolve())
    found = shutil.which(name)
    if not found:
        pytest.fail("Set KBHT_PG_BIN to PostgreSQL client tools for restore tests")
    return found


def test_dump_restore_retains_reward_receipts_items_and_worker_dedup(pg_lab, tmp_path):
    schema = checked_test_schema(pg_lab.engine)
    command = pg_lab.inventory_command(10001, {"source": str(uuid4())}, key="restore-reward", route="internal.crash-probe")
    executor = CommandExecutor(pg_lab.engine, {command.route: reward_handler})
    saved = executor.execute(command)
    event_id = pg_lab.emit_progress_event(10002, "drawTimes", 1)
    assert OutboxPoller(pg_lab.consumer()).poll_once() == "DONE"
    tables = (accounts, players, content_versions, game_servers, item_definitions, wallets,
              ledger_transactions, ledger_postings, wallet_ledger, command_receipts, outbox_events,
              inventory_items, inventory_ledger, reward_grants, reward_items, reward_currencies,
              worker_receipts, outbox_deliveries)

    def snapshot():
        with pg_lab.engine.connect() as connection:
            return {table.name: connection.execute(select(table).order_by(*table.primary_key.columns)).mappings().all()
                    for table in tables}

    before = snapshot()
    target = pg_lab.engine.url
    env = {key: value for key, value in os.environ.items() if not key.startswith("PG")}
    env.update(PGHOST=target.host, PGPORT=str(target.port or 5432), PGUSER=target.username,
               PGPASSWORD=target.password, PGDATABASE="kbht_test", PGCONNECT_TIMEOUT="5")
    backup = tmp_path / "synthetic-test-schema.dump"
    dumped = subprocess.run([pg_tool("pg_dump"), "--no-password", "--format=custom", f"--schema={schema}",
                             f"--file={backup}"], env=env, capture_output=True, text=True, timeout=30)
    assert dumped.returncode == 0, dumped.stderr
    assert backup.stat().st_size > 0
    pg_lab.engine.dispose()
    # Only this test's generated schema is removed; no pre-existing data is a restore target.
    assert checked_test_schema(pg_lab.engine) == schema
    with pg_lab.engine.begin() as connection:
        connection.execute(DropSchema(schema, cascade=True))
    pg_lab.engine.dispose()
    restored = subprocess.run([pg_tool("pg_restore"), "--no-password", "--no-owner", "--no-privileges",
                               "--single-transaction", "--exit-on-error", "--dbname=kbht_test", str(backup)],
                              env=env, capture_output=True, text=True, timeout=30)
    assert restored.returncode == 0, restored.stderr
    assert snapshot() == before
    assert executor.execute(command) == saved
    assert pg_lab.consume_progress_event(event_id) is False
    assert pg_lab.progress(10002, "drawTimes") == 1
    assert not any(check_invariants(pg_lab.engine).values())


@pytest.mark.parametrize("phase,exit_code", [("after-claim", 80), ("in-handler", 81), ("after-commit", 82)])
def test_worker_process_loss_reclaims_lease_without_duplicate_projection(pg_lab, phase, exit_code):
    schema = checked_test_schema(pg_lab.engine)
    event_id = pg_lab.emit_progress_event(10001, "drawTimes", 1)
    child = subprocess.run([sys.executable, "-I", str(Path(__file__).parents[1] / "crash_poller.py"), schema, phase],
                           capture_output=True, text=True, timeout=20)
    assert child.returncode == exit_code, child.stderr
    assert pg_lab.progress(10001, "drawTimes") == (1 if phase == "after-commit" else 0)
    clock = lambda: datetime(2026, 9, 16, tzinfo=timezone.utc) + timedelta(seconds=3)
    result = OutboxPoller(pg_lab.consumer(), clock=clock).poll_once()
    assert result == ("IDLE" if phase == "after-commit" else "DONE")
    assert pg_lab.worker_receipt_count(event_id) == 1
    assert pg_lab.progress(10001, "drawTimes") == 1
