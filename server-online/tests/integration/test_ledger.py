from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError

from kbht_server.contracts import DomainFailure, GameCommand
from kbht_server.db.schema import command_receipts, content_versions, ledger_postings, outbox_events, players, wallet_ledger, wallets
from purchase_fixture import execute_purchase


def purchase_command(command_id: str) -> GameCommand:
    return GameCommand(
        command_id=UUID(command_id),
        account_id=UUID("00000000-0000-4000-8000-000000000001"),
        player_id=10001,
        server_id=1,
        route="internal.purchase",
        expected_version=0,
        content_version_id=UUID("00000000-0000-4000-8000-000000000010"),
        payload={"cost_gem": 10, "reward_coin": 300},
    )


def test_receipt_replay_cannot_debit_twice(pg_engine, seeded_player):
    command = purchase_command("00000000-0000-4000-8000-000000000101")

    first = execute_purchase(pg_engine, command, cost_gem=10, reward_coin=300)
    replay = execute_purchase(pg_engine, command, cost_gem=10, reward_coin=300)

    assert replay == first
    with pg_engine.connect() as connection:
        balances = dict(
            connection.execute(
                select(wallets.c.currency, wallets.c.balance).where(wallets.c.player_id == 10001)
            ).all()
        )
        gem_deltas = connection.execute(
            select(wallet_ledger.c.delta)
            .where(wallet_ledger.c.player_id == 10001, wallet_ledger.c.currency == "gem")
            .order_by(wallet_ledger.c.created_at)
        ).scalars().all()
        receipt_count = connection.execute(
            select(command_receipts.c.command_id).where(
                command_receipts.c.player_id == 10001,
                command_receipts.c.command_id == command.command_id,
            )
        ).fetchall()

    assert balances == {"gem": 40, "coin": 300}
    assert gem_deltas == [50, -10]
    assert len(receipt_count) == 1


def run_purchase(engine, command):
    return execute_purchase(engine, command, **command.payload)


def assert_opening_state(engine):
    with engine.connect() as connection:
        assert dict(connection.execute(select(wallets.c.currency, wallets.c.balance)).all()) == {"gem": 50, "coin": 0}
        assert connection.execute(select(func.count()).select_from(wallet_ledger)).scalar_one() == 1
        assert connection.execute(select(func.count()).select_from(command_receipts)).scalar_one() == 0
        assert connection.execute(select(func.count()).select_from(outbox_events)).scalar_one() == 0
        assert connection.execute(select(players.c.version)).scalar_one() == 0


@pytest.mark.parametrize("changes,code", [
    ({"account_id": UUID("00000000-0000-4000-8000-000000000099")}, "FORBIDDEN"),
    ({"server_id": 2}, "FORBIDDEN"),
    ({"expected_version": 5}, "CONFLICT"),
    ({"route": "logic.gmHandler.addItem"}, "NOT_IMPLEMENTED"),
])
def test_denied_purchase_has_no_effect(pg_engine, seeded_player, changes, code):
    command = replace(purchase_command(str(uuid4())), **changes)
    with pytest.raises(DomainFailure) as failure:
        run_purchase(pg_engine, command)
    assert failure.value.code == code
    assert_opening_state(pg_engine)


@pytest.mark.parametrize("cost,reward", [(51, 300), (-1, 300), (True, 300), (10, -1), (10, 1.5)])
def test_invalid_or_unfunded_purchase_cannot_mint(pg_engine, seeded_player, cost, reward):
    command = replace(purchase_command(str(uuid4())), payload={"cost_gem": cost, "reward_coin": reward})
    with pytest.raises(DomainFailure) as failure:
        run_purchase(pg_engine, command)
    assert failure.value.code == ("INSUFFICIENT_FUNDS" if cost == 51 else "VALIDATION_ERROR")
    assert_opening_state(pg_engine)


def test_reused_command_with_changed_payload_conflicts(pg_engine, seeded_player):
    command = purchase_command(str(uuid4()))
    run_purchase(pg_engine, command)
    with pytest.raises(DomainFailure) as failure:
        run_purchase(pg_engine, replace(command, payload={"cost_gem": 1, "reward_coin": 900}))
    assert failure.value.code == "CONFLICT"


def test_result_mutation_cannot_change_persisted_replay(pg_engine, seeded_player):
    command = purchase_command(str(uuid4()))
    result = run_purchase(pg_engine, command)
    result.result["coin"] = -1
    pg_engine.dispose()
    replay = run_purchase(pg_engine, command)
    assert replay.result["coin"] == 300
    assert replay.aggregate_version == 1
    assert len(replay.event_ids) == 1


def test_outbox_failure_rolls_back_wallet_ledger_and_receipt(pg_engine, seeded_player):
    with pg_engine.begin() as connection:
        connection.exec_driver_sql("ALTER TABLE outbox_events ADD CONSTRAINT fail_probe CHECK (false)")
    with pytest.raises(IntegrityError):
        run_purchase(pg_engine, purchase_command(str(uuid4())))
    assert_opening_state(pg_engine)


def test_twenty_simultaneous_retries_commit_once(pg_engine, seeded_player):
    command = purchase_command(str(uuid4()))
    with ThreadPoolExecutor(max_workers=20) as pool:
        results = list(pool.map(lambda _: run_purchase(pg_engine, command), range(20)))
    assert all(result == results[0] for result in results)
    with pg_engine.connect() as connection:
        assert connection.execute(select(func.count()).select_from(command_receipts)).scalar_one() == 1
        assert connection.execute(select(func.count()).select_from(outbox_events)).scalar_one() == 1
        assert connection.execute(select(wallets.c.balance).where(wallets.c.currency == "gem")).scalar_one() == 40


def test_twenty_competing_spends_never_overdraw(pg_engine, seeded_player):
    def spend(_):
        command = purchase_command(str(uuid4()))
        for attempt in range(30):
            with pg_engine.connect() as connection:
                version = connection.execute(select(players.c.version)).scalar_one()
            try:
                run_purchase(pg_engine, replace(command, expected_version=version))
                return "COMMITTED"
            except DomainFailure as failure:
                if failure.code != "CONFLICT":
                    return failure.code
        pytest.fail("contention failed to converge")

    with ThreadPoolExecutor(max_workers=20) as pool:
        outcomes = list(pool.map(spend, range(20)))
    assert outcomes.count("COMMITTED") == 5
    assert outcomes.count("INSUFFICIENT_FUNDS") == 15
    with pg_engine.connect() as connection:
        assert dict(connection.execute(select(wallets.c.currency, wallets.c.balance)).all()) == {"gem": 0, "coin": 1500}
        assert connection.execute(select(func.sum(wallet_ledger.c.delta)).where(wallet_ledger.c.currency == "gem")).scalar_one() == 0


def test_purchase_postings_balance_each_currency(pg_engine, seeded_player):
    run_purchase(pg_engine, purchase_command(str(uuid4())))
    with pg_engine.connect() as connection:
        totals = connection.execute(select(
            ledger_postings.c.transaction_id, ledger_postings.c.currency, func.sum(ledger_postings.c.delta),
        ).group_by(ledger_postings.c.transaction_id, ledger_postings.c.currency)).all()
        assert len(totals) == 3
        assert all(total == 0 for _, _, total in totals)
        assert connection.execute(select(func.count()).select_from(ledger_postings)).scalar_one() == 6


def test_unknown_content_cannot_run_handler(pg_engine, seeded_player):
    command = replace(purchase_command(str(uuid4())), content_version_id=uuid4())
    with pytest.raises(DomainFailure) as failure:
        run_purchase(pg_engine, command)
    assert failure.value.code == "CONTENT_UNAVAILABLE"
    assert_opening_state(pg_engine)


@pytest.mark.parametrize("changes", [
    {"player_id": True}, {"player_id": 9007199254740992}, {"server_id": False},
    {"expected_version": False}, {"expected_version": -1}, {"command_id": "not-a-uuid"},
])
def test_bad_envelope_is_rejected_before_database_mutation(pg_engine, seeded_player, changes):
    with pytest.raises(DomainFailure) as failure:
        run_purchase(pg_engine, replace(purchase_command(str(uuid4())), **changes))
    assert failure.value.code == "VALIDATION_ERROR"
    assert_opening_state(pg_engine)
