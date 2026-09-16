from __future__ import annotations

from dataclasses import replace

import pytest

from kbht_server.contracts import DomainFailure
from kbht_server.db.migrations import check_invariants


def test_pg_lab_exposes_two_players_and_real_transaction_helpers(pg_lab):
    assert pg_lab.players == (10001, 10002)
    command = pg_lab.purchase_command(player_id=10001, cost_gem=10, reward_coin=300, key="pg-lab-1")
    result = pg_lab.execute(command)

    assert pg_lab.wallet(10001, "gem") == 40
    assert pg_lab.wallet(10001, "coin") == 300
    assert pg_lab.ledger_deltas(10001, "gem") == [50, -10]
    assert pg_lab.receipt_count(command.command_id) == 1
    assert len(pg_lab.events(command.command_id)) == 1
    assert pg_lab.execute(command) == result
    assert pg_lab.wallet(10002, "gem") == 50
    assert pg_lab.wallet(10002, "coin") == 0


def test_pg_lab_funding_is_an_opening_ledger_transaction(pg_lab):
    pg_lab.fund(10002, "gem", 25, reason="test-opening-2")

    assert pg_lab.wallet(10002, "gem") == 75
    assert pg_lab.ledger_deltas(10002, "gem") == [50, 25]
    assert not any(check_invariants(pg_lab.engine).values())


def test_progress_event_worker_deduplicates_real_counter_update(pg_lab):
    event_id = pg_lab.emit_progress_event(10001, "upgradeEquipmentTimes", 1)

    assert pg_lab.consume_progress_event(event_id) is True
    assert pg_lab.consume_progress_event(event_id) is False
    assert pg_lab.progress(10001, "upgradeEquipmentTimes") == 1
    assert pg_lab.worker_receipt_count(event_id) == 1


def test_lab_key_rebuild_replays_after_connection_reopen(pg_lab):
    inputs = {"player_id": 10001, "cost_gem": 10, "reward_coin": 300, "key": "stable-key"}
    command = pg_lab.purchase_command(**inputs)
    first = pg_lab.execute(command)
    pg_lab.engine.dispose()
    assert pg_lab.purchase_command(**inputs) == command
    assert pg_lab.execute(pg_lab.purchase_command(**inputs)) == first


def test_two_accounts_cannot_spend_each_others_wallet(pg_lab):
    first = pg_lab.purchase_command(player_id=10001, cost_gem=10, reward_coin=300, key="owner-a")
    with pytest.raises(DomainFailure) as failure:
        pg_lab.execute(replace(first, player_id=10002))
    assert failure.value.code == "FORBIDDEN"
    assert pg_lab.wallet(10001, "gem") == pg_lab.wallet(10002, "gem") == 50
