from __future__ import annotations

from dataclasses import replace
from concurrent.futures import ThreadPoolExecutor
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select, text, update
from sqlalchemy.exc import DBAPIError

from kbht_server.contracts import DomainFailure
from kbht_server.db.schema import (
    inventory_items, inventory_ledger, item_definitions, reward_grants, reward_items,
    content_versions, game_servers, command_receipts, outbox_events, players,
    reward_currencies,
)
from kbht_server.db.migrations import check_invariants
from kbht_server.db.uow import CommandExecutor


def test_reward_grant_persists_item_and_currency_atomically(pg_lab):
    command = pg_lab.purchase_command(player_id=10001, cost_gem=0, reward_coin=0, key="reward-1")
    command = replace(command, route="internal.reward", payload={"source_id": "00000000-0000-4000-8000-000000000101"})

    def reward(work, payload):
        return work.rewards.grant(
            source_type="battle", source_id=UUID(payload["source_id"]),
            items={49902: 2}, currencies={"coin": 100},
        )

    result = CommandExecutor(pg_lab.engine, {"internal.reward": reward}).execute(command)
    assert result.result["items"] == [{"kind_id": 49902, "quantity": 2}]
    assert result.result["currencies"] == {"coin": 100}
    assert pg_lab.wallet(10001, "coin") == 100
    with pg_lab.engine.connect() as connection:
        assert connection.execute(select(inventory_items.c.quantity).where(
            inventory_items.c.player_id == 10001, inventory_items.c.kind_id == 49902,
        )).scalar_one() == 2
        assert connection.execute(select(func.count()).select_from(reward_items)).scalar_one() == 1


def test_same_reward_source_cannot_mint_twice(pg_lab):
    source_id = UUID("00000000-0000-4000-8000-000000000102")

    def reward(work, payload):
        return work.rewards.grant(source_type="chapter", source_id=source_id, items={49902: 3})

    first = pg_lab.execute_handler("internal.reward", {"source_id": str(source_id)}, reward, key="grant-1")
    replay = pg_lab.execute_handler("internal.reward", {"source_id": str(source_id)}, reward, key="grant-2")
    assert replay.result == first.result
    assert pg_lab.item_quantity(10001, 49902) == 3
    assert pg_lab.reward_count(10001, "chapter", source_id) == 1


def test_inventory_consumption_is_atomic_and_uses_authoritative_quantity(pg_lab):
    pg_lab.add_item(10001, 49902, 5, reason="test-opening-item")
    command = pg_lab.inventory_command(10001, {"kind_id": 49902, "quantity": 2}, key="consume-1")

    def consume(work, payload):
        return work.inventory.consume(payload["kind_id"], payload["quantity"], reason="test-consume")

    result = CommandExecutor(pg_lab.engine, {"internal.inventory": consume}).execute(command)
    assert result.result == {"kind_id": 49902, "quantity": 2, "remaining": 3}
    assert pg_lab.item_quantity(10001, 49902) == 3
    assert pg_lab.inventory_deltas(10001, 49902)[-1] == -2


@pytest.mark.parametrize("quantity", [0, -1, True, 1.5])
def test_invalid_inventory_quantity_does_not_mutate(pg_lab, quantity):
    pg_lab.add_item(10001, 49902, 5, reason="test-opening-item")
    command = pg_lab.inventory_command(10001, {"kind_id": 49902, "quantity": quantity}, key=f"invalid-{quantity}")

    def consume(work, payload):
        return work.inventory.consume(payload["kind_id"], payload["quantity"], reason="test-consume")

    with pytest.raises(DomainFailure) as failure:
        CommandExecutor(pg_lab.engine, {"internal.inventory": consume}).execute(command)
    assert failure.value.code == "VALIDATION_ERROR"
    assert pg_lab.item_quantity(10001, 49902) == 5


def test_inventory_overdraw_rolls_back_all_rows(pg_lab):
    pg_lab.add_item(10001, 49902, 2, reason="test-opening-item")
    command = pg_lab.inventory_command(10001, {"kind_id": 49902, "quantity": 3}, key="overdraw-1")

    def consume(work, payload):
        return work.inventory.consume(payload["kind_id"], payload["quantity"], reason="test-consume")

    with pytest.raises(DomainFailure) as failure:
        CommandExecutor(pg_lab.engine, {"internal.inventory": consume}).execute(command)
    assert failure.value.code == "INSUFFICIENT_FUNDS"
    assert pg_lab.item_quantity(10001, 49902) == 2
    assert pg_lab.receipt_count(command.command_id) == 0


def test_reward_rejects_unknown_item_without_wallet_debit(pg_lab):
    command = pg_lab.inventory_command(10001, {"kind_id": 999999, "quantity": 1}, key="unknown-item")

    def reward(work, payload):
        return work.rewards.grant(source_type="battle", source_id=uuid4(), items={payload["kind_id"]: payload["quantity"]}, currencies={"coin": 100})

    with pytest.raises(DomainFailure) as failure:
        CommandExecutor(pg_lab.engine, {"internal.inventory": reward}).execute(command)
    assert failure.value.code == "NOT_FOUND"
    assert pg_lab.wallet(10001, "coin") == 0


def test_reward_result_is_persisted_and_not_mutable_by_caller(pg_lab):
    source_id = UUID("00000000-0000-4000-8000-000000000103")

    def reward(work, payload):
        return work.rewards.grant(source_type="battle", source_id=source_id, items={49902: 1})

    first = pg_lab.execute_handler("internal.reward", {}, reward, key="mutable-result")
    first.result["items"][0]["quantity"] = 999
    replay = pg_lab.execute_handler("internal.reward", {}, reward, key="mutable-result-replay")
    assert replay.result["items"] == [{"kind_id": 49902, "quantity": 1}]


def test_reward_lineage_is_queryable(pg_lab):
    source_id = UUID("00000000-0000-4000-8000-000000000104")

    def reward(work, payload):
        return work.rewards.grant(source_type="map", source_id=source_id, items={49902: 4})

    pg_lab.execute_handler("internal.reward", {}, reward, key="lineage")
    with pg_lab.engine.connect() as connection:
        row = connection.execute(select(reward_grants.c.source_type, reward_grants.c.source_id).where(
            reward_grants.c.player_id == 10001,
        )).mappings().one()
        item = connection.execute(select(inventory_ledger.c.source_type, inventory_ledger.c.source_id).where(
            inventory_ledger.c.player_id == 10001,
        )).mappings().one()
    assert row["source_type"] == "map"
    assert row["source_id"] == source_id
    assert item["source_type"] == "reward"
    assert item["source_id"] == source_id


def execute_inventory(pg_lab, payload, handler, key=None, player_id=10001):
    return pg_lab.execute_handler("internal.inventory", payload, handler,
                                 key=key or str(uuid4()), player_id=player_id)


def test_add_splits_and_refills_stacks_without_losing_quantity(pg_lab):
    pg_lab.add_item(10001, 49902, 23, reason="opening")
    rows = pg_lab.items(10001)
    assert [row["quantity"] for row in rows] == [10, 10, 3]
    first_id = rows[0]["id"]
    consumed = execute_inventory(pg_lab, {}, lambda work, _: work.inventory.consume(49902, 12, reason="spend"))
    assert consumed.result["remaining"] == 11
    pg_lab.add_item(10001, 49902, 9, reason="refill")
    assert [row["quantity"] for row in pg_lab.items(10001)] == [9, 8, 3]
    assert pg_lab.items(10001)[0]["id"] == first_id
    assert sum(pg_lab.inventory_deltas(10001, 49902)) == 20


def test_single_unit_definition_allocates_separate_owned_records(pg_lab):
    pg_lab.add_item(10001, 90001, 3, reason="opening")
    rows = pg_lab.items(10001)
    assert len({row["id"] for row in rows}) == 3
    assert [row["quantity"] for row in rows] == [1, 1, 1]
    execute_inventory(pg_lab, {}, lambda work, _: work.inventory.consume(
        90001, 1, reason="selected", inventory_id=rows[1]["id"],
    ))
    assert [row["quantity"] for row in pg_lab.items(10001)] == [1, 0, 1]


def test_selected_record_cannot_borrow_from_other_stacks(pg_lab):
    pg_lab.add_item(10001, 49902, 12, reason="opening")
    selected = pg_lab.items(10001)[1]["id"]
    with pytest.raises(DomainFailure) as failure:
        execute_inventory(pg_lab, {}, lambda work, _: work.inventory.consume(49902, 3, reason="selected", inventory_id=selected))
    assert failure.value.code == "INSUFFICIENT_FUNDS"
    assert pg_lab.item_quantity(10001, 49902) == 12


def test_foreign_inventory_id_cannot_be_consumed(pg_lab):
    pg_lab.add_item(10002, 49902, 5, reason="other-player")
    foreign_id = pg_lab.items(10002)[0]["id"]
    with pytest.raises(DomainFailure) as failure:
        execute_inventory(pg_lab, {}, lambda work, _: work.inventory.consume(49902, 1, reason="steal", inventory_id=foreign_id))
    assert failure.value.code == "NOT_FOUND"
    assert pg_lab.item_quantity(10002, 49902) == 5
    assert pg_lab.items(10001) == []


def test_last_item_row_is_retained_for_ledger_and_wire_tombstone(pg_lab):
    pg_lab.add_item(10001, 49902, 2, reason="opening")
    row_id = pg_lab.items(10001)[0]["id"]
    result = execute_inventory(pg_lab, {}, lambda work, _: work.inventory.consume(49902, 2, reason="all"))
    assert result.result["remaining"] == 0
    assert pg_lab.items(10001)[0]["id"] == row_id
    assert pg_lab.items(10001)[0]["quantity"] == 0
    assert pg_lab.inventory_deltas(10001, 49902) == [2, -2]


def test_consumption_command_replay_does_not_spend_twice(pg_lab):
    pg_lab.add_item(10001, 49902, 5, reason="opening")
    def consume(work, _):
        return work.inventory.consume(49902, 2, reason="use")
    first = execute_inventory(pg_lab, {}, consume, key="item-retry")
    pg_lab.engine.dispose()
    assert execute_inventory(pg_lab, {}, consume, key="item-retry") == first
    assert pg_lab.item_quantity(10001, 49902) == 3


@pytest.mark.parametrize("field,value", [("items", {49902: 4}), ("currencies", {"coin": 200})])
def test_changed_reward_source_conflicts_without_minting(pg_lab, field, value):
    source = uuid4()
    def grant(work, _):
        return work.rewards.grant(source_type="mail", source_id=source, items={49902: 3}, currencies={"coin": 100})
    execute_inventory(pg_lab, {}, grant)
    args = {"source_type": "mail", "source_id": source, "items": {49902: 3}, "currencies": {"coin": 100}, field: value}
    with pytest.raises(DomainFailure) as failure:
        execute_inventory(pg_lab, {}, lambda work, _: work.rewards.grant(**args))
    assert failure.value.code == "CONFLICT"
    assert pg_lab.item_quantity(10001, 49902) == 3
    assert pg_lab.wallet(10001, "coin") == 100


def test_reward_source_scope_includes_recipient_and_source_type(pg_lab):
    source = uuid4()
    for player_id, source_type in [(10001, "mail"), (10002, "mail"), (10001, "chapter")]:
        execute_inventory(pg_lab, {}, lambda work, _: work.rewards.grant(
            source_type=source_type, source_id=source, items={49902: 1},
        ), player_id=player_id)
    assert pg_lab.item_quantity(10001, 49902) == 2
    assert pg_lab.item_quantity(10002, 49902) == 1


@pytest.mark.parametrize("stage", ["inventory_ledger", "reward_items", "outbox_events", "command_receipts"])
def test_failure_rolls_back_currency_inventory_grant_and_receipt(pg_lab, stage):
    with pg_lab.engine.begin() as connection:
        connection.execute(text(f"ALTER TABLE {stage} ADD CONSTRAINT fail_probe CHECK (false)"))
    def reward(work, _):
        work.adjust_wallet("gem", -10, reason="test-buy")
        return work.rewards.grant(source_type="purchase", source_id=uuid4(), items={49902: 2}, currencies={"coin": 100})
    with pytest.raises(DBAPIError):
        execute_inventory(pg_lab, {}, reward)
    assert pg_lab.items(10001) == []
    assert pg_lab.wallet(10001, "gem") == 50
    assert pg_lab.wallet(10001, "coin") == 0
    with pg_lab.engine.connect() as connection:
        for table in (inventory_ledger, reward_grants, reward_items, command_receipts, outbox_events):
            assert connection.execute(select(func.count()).select_from(table)).scalar_one() == 0


def test_unknown_currency_rolls_back_previously_added_items(pg_lab):
    with pytest.raises(DomainFailure) as failure:
        execute_inventory(pg_lab, {}, lambda work, _: work.rewards.grant(
            source_type="mail", source_id=uuid4(), items={49902: 2}, currencies={"unavailable": 1},
        ))
    assert failure.value.code == "NOT_FOUND"
    assert pg_lab.items(10001) == []


def test_multiple_grants_in_same_command_share_wallet_ledger_transaction(pg_lab):
    sources = (uuid4(), uuid4())
    def grants(work, _):
        one = work.rewards.grant(source_type="mail", source_id=sources[0], currencies={"coin": 10})
        two = work.rewards.grant(source_type="mail", source_id=sources[1], currencies={"coin": 20})
        return {"one": one, "two": two}
    execute_inventory(pg_lab, {}, grants)
    assert pg_lab.wallet(10001, "coin") == 30
    assert pg_lab.ledger_deltas(10001, "coin") == [10, 20]


def test_large_split_request_is_bounded_before_mutation(pg_lab):
    with pytest.raises(DomainFailure) as failure:
        pg_lab.add_item(10001, 90001, 1001, reason="large-split")
    assert failure.value.code == "LIMIT_REACHED"
    assert pg_lab.items(10001) == []


def test_content_switch_cannot_mix_incompatible_stacks(pg_lab):
    pg_lab.add_item(10001, 49902, 2, reason="opening")
    content_id = uuid4()
    with pg_lab.engine.begin() as connection:
        connection.execute(content_versions.insert().values(id=content_id, source_sha256="1"*64, rules_sha256="1"*64, status="DRAFT"))
        connection.execute(item_definitions.insert().values(content_version_id=content_id, kind_id=49902, stack_limit=5))
        connection.execute(update(content_versions).where(content_versions.c.id == content_id).values(status="PUBLISHED"))
        connection.execute(update(game_servers).where(game_servers.c.id == 1).values(active_content_version_id=content_id))
    command = replace(pg_lab.inventory_command(10001, {}, key="new-content"), content_version_id=content_id)
    with pytest.raises(DomainFailure) as failure:
        CommandExecutor(pg_lab.engine, {command.route: lambda work, _: work.inventory.add(49902, 1, reason="new")}).execute(command)
    assert failure.value.code == "CONTENT_UNAVAILABLE"
    assert pg_lab.item_quantity(10001, 49902) == 2


def run_with_conflict_retry(lab, command, handler):
    for _ in range(30):
        with lab.engine.connect() as connection:
            version = connection.execute(select(players.c.version).where(players.c.id == command.player_id)).scalar_one()
        try:
            return CommandExecutor(lab.engine, {command.route: handler}).execute(replace(command, expected_version=version))
        except DomainFailure as failure:
            if failure.code != "CONFLICT":
                raise
    raise AssertionError("concurrent command retry did not converge")


def test_twenty_grant_commands_for_same_source_mint_once(pg_lab):
    source = uuid4()
    def grant(work, _):
        return work.rewards.grant(source_type="mail", source_id=source, items={49902: 3}, currencies={"coin": 100})
    commands = [pg_lab.inventory_command(10001, {}, key=str(uuid4())) for _ in range(20)]
    with ThreadPoolExecutor(max_workers=20) as pool:
        results = list(pool.map(lambda cmd: run_with_conflict_retry(pg_lab, cmd, grant), commands))
    assert all(result.result == results[0].result for result in results)
    assert pg_lab.item_quantity(10001, 49902) == 3
    assert pg_lab.wallet(10001, "coin") == 100
    assert pg_lab.reward_count(10001, "mail", source) == 1
    with pg_lab.engine.connect() as connection:
        assert connection.execute(select(func.count()).select_from(outbox_events)).scalar_one() == 1


def test_twenty_simultaneous_spends_cannot_exceed_owned_items(pg_lab):
    pg_lab.add_item(10001, 49902, 5, reason="opening")
    def spend(work, _):
        return work.inventory.consume(49902, 1, reason="spend")
    commands = [pg_lab.inventory_command(10001, {}, key=str(uuid4())) for _ in range(20)]
    def attempt(command):
        try:
            run_with_conflict_retry(pg_lab, command, spend)
            return "spent"
        except DomainFailure as failure:
            return failure.code
    with ThreadPoolExecutor(max_workers=20) as pool:
        outcomes = list(pool.map(attempt, commands))
    assert outcomes.count("spent") == 5
    assert outcomes.count("INSUFFICIENT_FUNDS") == 15
    assert pg_lab.item_quantity(10001, 49902) == 0
    assert sum(pg_lab.inventory_deltas(10001, 49902)) == 0


@pytest.mark.parametrize("table", ["inventory_ledger", "reward_grants", "reward_items", "reward_currencies"])
@pytest.mark.parametrize("action", ["DELETE FROM", "TRUNCATE"])
def test_reward_and_item_history_is_append_only(pg_lab, table, action):
    execute_inventory(pg_lab, {}, lambda work, _: work.rewards.grant(
        source_type="mail", source_id=uuid4(), items={49902: 2}, currencies={"coin": 100},
    ))
    with pytest.raises(DBAPIError, match="append-only"):
        with pg_lab.engine.begin() as connection:
            connection.execute(text(f"{action} {table}{' CASCADE' if action == 'TRUNCATE' else ''}"))


def test_inventory_invariants_detect_quantity_without_ledger(pg_lab):
    pg_lab.add_item(10001, 49902, 3, reason="opening")
    assert not any(check_invariants(pg_lab.engine).values())
    with pg_lab.engine.begin() as connection:
        connection.execute(update(inventory_items).where(inventory_items.c.player_id == 10001).values(quantity=4))
    with pytest.raises(RuntimeError, match="inventory_mismatches"):
        check_invariants(pg_lab.engine)


def test_item_definition_used_by_grant_is_immutable(pg_lab):
    execute_inventory(pg_lab, {}, lambda work, _: work.rewards.grant(source_type="mail", source_id=uuid4(), items={49902: 1}))
    with pytest.raises(DBAPIError, match="published item definition"):
        with pg_lab.engine.begin() as connection:
            connection.execute(update(item_definitions).where(item_definitions.c.kind_id == 49902).values(stack_limit=1))


def test_content_cannot_be_unpublished_to_rewrite_item_rules(pg_lab):
    with pytest.raises(DBAPIError, match="published content"):
        with pg_lab.engine.begin() as connection:
            connection.execute(update(content_versions).where(
                content_versions.c.id == pg_lab.inventory_command(10001, {}, key="content-version").content_version_id,
            ).values(status="DRAFT"))


def test_published_content_provenance_cannot_change(pg_lab):
    with pytest.raises(DBAPIError, match="published content"):
        with pg_lab.engine.begin() as connection:
            connection.execute(update(content_versions).values(source_sha256="f" * 64))


@pytest.mark.parametrize("args", [
    {"items": {}}, {"items": {49902: 0}}, {"items": {49902: True}},
    {"items": {True: 1}}, {"items": {49902: 1.5}}, {"items": {49902: -1}},
    {"items": {49902: 9007199254740992}}, {"items": []},
    {"currencies": {"coin": -1}}, {"currencies": {"coin": True}},
    {"currencies": {"": 1}}, {"currencies": {"x" * 33: 1}},
])
def test_invalid_reward_amounts_leave_no_grant_or_items(pg_lab, args):
    with pytest.raises(DomainFailure) as failure:
        execute_inventory(pg_lab, {}, lambda work, _: work.rewards.grant(
            source_type="mail", source_id=uuid4(), **args,
        ))
    assert failure.value.code == "VALIDATION_ERROR"
    assert pg_lab.items(10001) == []
    with pg_lab.engine.connect() as connection:
        assert connection.execute(select(func.count()).select_from(reward_grants)).scalar_one() == 0


def test_real_item_exchange_rolls_back_consumption_when_reward_fails(pg_lab):
    pg_lab.add_item(10001, 49902, 3, reason="opening")
    def exchange(work, _):
        work.inventory.consume(49902, 2, reason="exchange-cost")
        return work.rewards.grant(source_type="exchange", source_id=uuid4(), items={999999: 1})
    with pytest.raises(DomainFailure):
        execute_inventory(pg_lab, {}, exchange)
    assert pg_lab.item_quantity(10001, 49902) == 3
    assert pg_lab.inventory_deltas(10001, 49902) == [3]


def test_inventory_and_reward_invariants_reconcile_valid_exchange(pg_lab):
    pg_lab.add_item(10001, 49902, 13, reason="opening")
    source = uuid4()
    def exchange(work, _):
        work.inventory.consume(49902, 12, reason="exchange-cost")
        return work.rewards.grant(source_type="exchange", source_id=source, items={49001: 15}, currencies={"coin": 77})
    execute_inventory(pg_lab, {}, exchange)
    assert pg_lab.item_quantity(10001, 49902) == 1
    assert pg_lab.item_quantity(10001, 49001) == 15
    assert all(value == 0 for value in check_invariants(pg_lab.engine).values())


@pytest.mark.parametrize("table,column,expected", [
    (inventory_ledger, "quantity_after", "inventory_history_mismatches"),
    (reward_items, "quantity", "reward_item_mismatches"),
    (reward_currencies, "quantity", "reward_currency_mismatches"),
])
def test_invariant_checker_detects_corrupted_reward_history(pg_lab, table, column, expected):
    execute_inventory(pg_lab, {}, lambda work, _: work.rewards.grant(
        source_type="mail", source_id=uuid4(), items={49902: 2}, currencies={"coin": 100},
    ))
    # Deliberately corrupt only the throwaway schema to exercise restore diagnostics.
    with pg_lab.engine.begin() as connection:
        connection.execute(text(f"ALTER TABLE {table.name} DISABLE TRIGGER USER"))
        connection.execute(update(table).values({column: table.c[column] + 1}))
        connection.execute(text(f"ALTER TABLE {table.name} ENABLE TRIGGER USER"))
    with pytest.raises(RuntimeError, match=expected):
        check_invariants(pg_lab.engine)
