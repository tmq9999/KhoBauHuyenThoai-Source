from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
from alembic import command as alembic_command
from alembic.config import Config
from sqlalchemy import inspect, select, text, update
from sqlalchemy.exc import DBAPIError

from kbht_server.db.migrations import apply_migrations, check_invariants
from kbht_server.db import migrations
from kbht_server.db.schema import command_receipts, ledger_postings, outbox_events, wallet_ledger, wallets
from pg_lab import PGLab, seed_players, test_counters


def test_worker_receipts_upgrade_preserves_committed_commands(empty_pg_engine):
    cfg = Config()
    cfg.set_main_option("script_location", str(Path(migrations.__file__).with_name("alembic")))
    with empty_pg_engine.begin() as connection:
        cfg.attributes["connection"] = connection
        alembic_command.upgrade(cfg, "0001_core")
    seed_players(empty_pg_engine, (10001, 10002))
    lab = PGLab(empty_pg_engine)
    purchase = lab.purchase_command(player_id=10001, cost_gem=10, reward_coin=300, key="pre-upgrade")
    saved_result = lab.execute(purchase)
    event_id = lab.emit_progress_event(10001, "drawTimes", 1)
    with empty_pg_engine.connect() as connection:
        before = [connection.execute(select(table)).mappings().all()
                  for table in (wallets, wallet_ledger, ledger_postings, command_receipts, outbox_events)]

    assert apply_migrations(empty_pg_engine) == "0005_runtime_guards"
    assert apply_migrations(empty_pg_engine) == "0005_runtime_guards"
    with empty_pg_engine.connect() as connection:
        after = [connection.execute(select(table)).mappings().all()
                 for table in (wallets, wallet_ledger, ledger_postings, command_receipts, outbox_events)]
    assert before == after
    assert lab.execute(purchase) == saved_result
    test_counters.create(empty_pg_engine)
    assert lab.consume_progress_event(event_id) is True
    assert lab.consume_progress_event(event_id) is False
    assert lab.progress(10001, "drawTimes") == 1
    assert not any(check_invariants(empty_pg_engine).values())


def test_migration_creates_authoritative_core_tables(empty_pg_engine):
    apply_migrations(empty_pg_engine)
    names = set(inspect(empty_pg_engine).get_table_names())
    assert {"accounts", "players", "wallets", "ledger_transactions", "ledger_postings",
            "wallet_ledger", "command_receipts", "outbox_events", "alembic_version"} <= names
    with empty_pg_engine.connect() as connection:
        assert connection.execute(text("SELECT version_num FROM alembic_version")).scalars().all() == ["0005_runtime_guards"]


def test_migration_is_idempotent_and_invariants_are_read_only(empty_pg_engine):
    apply_migrations(empty_pg_engine)
    apply_migrations(empty_pg_engine)
    assert check_invariants(empty_pg_engine) == {
        "wallet_mismatches": 0, "unbalanced_transactions": 0,
        "posting_mismatches": 0, "orphan_receipts": 0,
        "inventory_mismatches": 0, "inventory_history_mismatches": 0,
        "reward_item_mismatches": 0, "reward_currency_mismatches": 0,
    }


def test_migration_refuses_partial_unversioned_schema(empty_pg_engine):
    with empty_pg_engine.begin() as connection:
        connection.execute(text("CREATE TABLE wallets (player_id bigint PRIMARY KEY)"))
    with pytest.raises(RuntimeError, match="unversioned"):
        apply_migrations(empty_pg_engine)
    assert inspect(empty_pg_engine).get_table_names() == ["wallets"]


@pytest.mark.parametrize("table", ["wallet_ledger", "ledger_postings", "ledger_transactions"])
@pytest.mark.parametrize("operation", ["DELETE", "TRUNCATE"])
def test_ledger_history_cannot_be_erased(pg_engine, seeded_player, table, operation):
    with pytest.raises(DBAPIError, match="append-only"):
        with pg_engine.begin() as connection:
            connection.execute(text(f"{operation} {'FROM ' if operation == 'DELETE' else ''}{table}{' CASCADE' if operation == 'TRUNCATE' else ''}"))


def test_ledger_history_cannot_be_rewritten(pg_engine, seeded_player):
    with pytest.raises(DBAPIError, match="append-only"):
        with pg_engine.begin() as connection:
            connection.execute(update(wallet_ledger).values(delta=51))


def test_invariants_detect_wallet_without_matching_ledger(pg_engine, seeded_player):
    with pg_engine.begin() as connection:
        connection.execute(update(wallets).where(wallets.c.currency == "gem").values(balance=51))
    with pytest.raises(RuntimeError, match="wallet_mismatches"):
        check_invariants(pg_engine)


def test_cli_module_executes_parser_and_help():
    result = subprocess.run([sys.executable, "-I", "-m", "kbht_server.cli", "--help"],
                            capture_output=True, text=True, timeout=15)
    assert result.returncode == 0
    assert "migrate" in result.stdout
    assert "check-invariants" in result.stdout
