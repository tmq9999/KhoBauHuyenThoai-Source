"""Test-only setup and projections, backed by actual PostgreSQL commands."""

from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from sqlalchemy import BigInteger, Column, Integer, MetaData, String, Table, func, select, update
from sqlalchemy.dialects.postgresql import insert

from kbht_server.contracts import GameCommand
from kbht_server.db.schema import (
    accounts, command_receipts, content_versions, game_servers, ledger_postings,
    ledger_transactions, outbox_events, players, wallet_ledger, wallets, worker_receipts,
    inventory_items, inventory_ledger, item_definitions, reward_grants,
)
from kbht_server.db.uow import CommandExecutor
from kbht_server.workers.outbox import OutboxConsumer
from purchase_fixture import execute_purchase


CONTENT_ID = UUID("00000000-0000-4000-8000-000000000010")
ACCOUNT_IDS = {
    10001: UUID("00000000-0000-4000-8000-000000000001"),
    10002: UUID("00000000-0000-4000-8000-000000000002"),
}
test_counters = Table(
    "test_counters", MetaData(),
    Column("player_id", BigInteger, primary_key=True),
    Column("requirement", String(120), primary_key=True),
    Column("progress", Integer, nullable=False),
)


def opening_fund(connection, player_id, currency, amount, reason):
    if type(amount) is not int or amount <= 0:
        raise ValueError("positive integer opening balance required")
    wallet = connection.execute(select(wallets).where(
        wallets.c.player_id == player_id, wallets.c.currency == currency,
    ).with_for_update()).mappings().one()
    transaction_id, command_id = uuid4(), uuid4()
    connection.execute(ledger_transactions.insert().values(
        id=transaction_id, player_id=player_id, command_id=command_id, reason=reason,
    ))
    connection.execute(ledger_postings.insert(), [
        {"transaction_id": transaction_id, "line_no": 1, "currency": currency,
         "account_key": f"player:{player_id}", "delta": amount},
        {"transaction_id": transaction_id, "line_no": 2, "currency": currency,
         "account_key": "system:issuance", "delta": -amount},
    ])
    balance = wallet["balance"] + amount
    connection.execute(update(wallets).where(
        wallets.c.player_id == player_id, wallets.c.currency == currency,
    ).values(balance=balance, version=wallet["version"] + 1))
    connection.execute(wallet_ledger.insert().values(
        id=uuid4(), player_id=player_id, currency=currency, delta=amount,
        balance_after=balance, reason=reason, command_id=command_id,
        transaction_id=transaction_id, line_no=1,
    ))


def seed_players(engine, player_ids, *, publish=True):
    with engine.begin() as connection:
        connection.execute(content_versions.insert().values(
            id=CONTENT_ID, source_sha256="0" * 64, rules_sha256="0" * 64,
            status="PUBLISHED" if publish else "DRAFT",
        ))
        connection.execute(game_servers.insert().values(
            id=1, name="M1 Test", status="OPEN", active_content_version_id=CONTENT_ID,
        ))
        for player_id in player_ids:
            connection.execute(accounts.insert().values(
                id=ACCOUNT_IDS[player_id], normalized_login=f"test-{player_id}", password_hash="test-only",
            ))
            connection.execute(players.insert().values(
                id=player_id, account_id=ACCOUNT_IDS[player_id], server_id=1, name=f"Test {player_id}",
            ))
            connection.execute(wallets.insert(), [
                {"player_id": player_id, "currency": currency, "balance": 0, "version": 0}
                for currency in ("gem", "coin")
            ])
            opening_fund(connection, player_id, "gem", 50, "test-opening")


def seed_item_definitions(engine):
    # Synthetic content records for the persistence boundary, not gameplay sources.
    with engine.begin() as connection:
        connection.execute(item_definitions.insert(), [
            {"content_version_id": CONTENT_ID, "kind_id": 49902, "stack_limit": 10},
            {"content_version_id": CONTENT_ID, "kind_id": 49001, "stack_limit": 10},
            {"content_version_id": CONTENT_ID, "kind_id": 90001, "stack_limit": 1},
        ])
        connection.execute(update(content_versions).where(content_versions.c.id == CONTENT_ID).values(status="PUBLISHED"))


def project_counter(connection, event):
    """Exercise a persisted projection; this is not a daily-task implementation."""
    statement = insert(test_counters).values(
        player_id=event.player_id, requirement=event.body["requirement"], progress=event.body["amount"],
    )
    connection.execute(statement.on_conflict_do_update(
        index_elements=[test_counters.c.player_id, test_counters.c.requirement],
        set_={"progress": test_counters.c.progress + statement.excluded.progress},
    ))


class PGLab:
    players = (10001, 10002)

    def __init__(self, engine):
        self.engine = engine
        self.command_versions = {}

    def purchase_command(self, *, player_id, cost_gem, reward_coin, key=None, command_id=None):
        if (key is None) == (command_id is None):
            raise ValueError("specify either key or command_id")
        identifier = UUID(str(command_id)) if command_id is not None else uuid5(NAMESPACE_URL, f"kbht-test:{key}")
        label = (player_id, identifier)
        if label not in self.command_versions:
            self.command_versions[label] = self._version(player_id)
        return GameCommand(
            command_id=identifier, account_id=ACCOUNT_IDS[player_id], player_id=player_id, server_id=1,
            route="internal.purchase", expected_version=self.command_versions[label],
            content_version_id=CONTENT_ID, payload={"cost_gem": cost_gem, "reward_coin": reward_coin},
        )

    def execute(self, command):
        return execute_purchase(self.engine, command, **command.payload)

    def wallet(self, player_id, currency):
        with self.engine.connect() as connection:
            return connection.execute(select(wallets.c.balance).where(
                wallets.c.player_id == player_id, wallets.c.currency == currency,
            )).scalar_one()

    def ledger_deltas(self, player_id, currency):
        with self.engine.connect() as connection:
            return connection.execute(select(wallet_ledger.c.delta).where(
                wallet_ledger.c.player_id == player_id, wallet_ledger.c.currency == currency,
            ).order_by(wallet_ledger.c.created_at, wallet_ledger.c.transaction_id,
                       wallet_ledger.c.line_no)).scalars().all()

    def receipt_count(self, command_id):
        with self.engine.connect() as connection:
            return connection.execute(select(func.count()).select_from(command_receipts).where(
                command_receipts.c.command_id == command_id,
            )).scalar_one()

    def events(self, command_id):
        with self.engine.connect() as connection:
            return connection.execute(select(outbox_events).where(
                outbox_events.c.command_id == command_id,
            )).mappings().all()

    def fund(self, player_id, currency, amount, *, reason):
        with self.engine.begin() as connection:
            opening_fund(connection, player_id, currency, amount, reason)

    def emit_progress_event(self, player_id, requirement, amount):
        command = GameCommand(
            command_id=uuid4(), account_id=ACCOUNT_IDS[player_id], player_id=player_id, server_id=1,
            route="internal.progress", expected_version=self._version(player_id), content_version_id=CONTENT_ID,
            payload={"requirement": requirement, "amount": amount},
        )

        def emit(work, payload):
            work.emit("test.progress", payload)
            return {"accepted": True}

        result = CommandExecutor(self.engine, {command.route: emit}).execute(command)
        return result.event_ids[0]

    def consumer(self, *, name="test-progress-v1", handler=project_counter):
        return OutboxConsumer(self.engine, name, {"test.progress": handler})

    def consume_progress_event(self, event_id):
        return self.consumer().consume(event_id)

    def progress(self, player_id, requirement):
        with self.engine.connect() as connection:
            return connection.execute(select(test_counters.c.progress).where(
                test_counters.c.player_id == player_id, test_counters.c.requirement == requirement,
            )).scalar_one_or_none() or 0

    def worker_receipt_count(self, event_id):
        with self.engine.connect() as connection:
            return connection.execute(select(func.count()).select_from(worker_receipts).where(
                worker_receipts.c.event_id == event_id,
            )).scalar_one()

    def _version(self, player_id):
        with self.engine.connect() as connection:
            return connection.execute(select(players.c.version).where(players.c.id == player_id)).scalar_one()

    def inventory_command(self, player_id, payload, *, key, route="internal.inventory"):
        identifier = uuid5(NAMESPACE_URL, f"kbht-test:{key}")
        label = (player_id, identifier)
        if label not in self.command_versions:
            self.command_versions[label] = self._version(player_id)
        return GameCommand(
            command_id=identifier, account_id=ACCOUNT_IDS[player_id], player_id=player_id,
            server_id=1, route=route, expected_version=self.command_versions[label],
            content_version_id=CONTENT_ID, payload=payload,
        )

    def execute_handler(self, route, payload, handler, *, key, player_id=10001):
        command = self.inventory_command(player_id, payload, key=key, route=route)
        return CommandExecutor(self.engine, {route: handler}).execute(command)

    def add_item(self, player_id, kind_id, quantity, *, reason):
        def opening(work, payload):
            return work.inventory.add(payload["kind_id"], payload["quantity"], reason=reason)

        return self.execute_handler("internal.opening-item", {"kind_id": kind_id, "quantity": quantity},
                                    opening, key=str(uuid4()), player_id=player_id)

    def items(self, player_id):
        with self.engine.connect() as connection:
            return connection.execute(select(inventory_items).where(
                inventory_items.c.player_id == player_id,
            ).order_by(inventory_items.c.id)).mappings().all()

    def item_quantity(self, player_id, kind_id):
        return sum(row["quantity"] for row in self.items(player_id) if row["kind_id"] == kind_id)

    def inventory_deltas(self, player_id, kind_id):
        with self.engine.connect() as connection:
            return connection.execute(select(inventory_ledger.c.delta).where(
                inventory_ledger.c.player_id == player_id, inventory_ledger.c.kind_id == kind_id,
            ).order_by(inventory_ledger.c.created_at, inventory_ledger.c.inventory_id,
                       inventory_ledger.c.inventory_version)).scalars().all()

    def reward_count(self, player_id, source_type, source_id):
        with self.engine.connect() as connection:
            return connection.execute(select(func.count()).select_from(reward_grants).where(
                reward_grants.c.player_id == player_id, reward_grants.c.source_type == source_type,
                reward_grants.c.source_id == source_id,
            )).scalar_one()
