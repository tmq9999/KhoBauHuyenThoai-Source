from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, replace
from typing import Callable
from uuid import UUID, uuid4

from sqlalchemy import select, update, func
from sqlalchemy.engine import Connection, Engine

from kbht_server.contracts import CommandResult, DomainFailure, GameCommand
from kbht_server.db.repositories import InventoryRepository
from kbht_server.economy.rewards import RewardService
from kbht_server.db.schema import (
    command_receipts, content_versions, game_servers, ledger_postings,
    ledger_transactions, outbox_events, players, wallet_ledger, wallets,
)


MAX_BALANCE = 9_007_199_254_740_991


class UnitOfWork:
    """One locked player transaction. Only the executor commits it."""

    def __init__(self, connection: Connection, command: GameCommand):
        self.connection = connection
        self.command = command
        self.event_ids: list[UUID] = []
        self.transaction_id: UUID | None = None
        self.posting_no = 0
        self.inventory = InventoryRepository(self)
        self.rewards = RewardService(self)

    def adjust_wallet(self, currency: str, delta: int, *, reason: str) -> int:
        if type(delta) is not int or not -MAX_BALANCE <= delta <= MAX_BALANCE:
            raise DomainFailure("VALIDATION_ERROR", "Invalid wallet amount")
        wallet = self.connection.execute(
            select(wallets).where(wallets.c.player_id == self.command.player_id,
                                  wallets.c.currency == currency).with_for_update()
        ).mappings().one_or_none()
        if wallet is None:
            raise DomainFailure("NOT_FOUND", "Wallet not found")
        balance = wallet["balance"] + delta
        if balance < 0:
            raise DomainFailure("INSUFFICIENT_FUNDS", "Insufficient currency")
        if balance > MAX_BALANCE:
            raise DomainFailure("LIMIT_REACHED", "Wallet capacity exceeded")
        if self.transaction_id is None:
            self.transaction_id = uuid4()
            self.connection.execute(ledger_transactions.insert().values(
                id=self.transaction_id, player_id=self.command.player_id,
                command_id=self.command.command_id, reason=self.command.route,
            ))
        self.posting_no += 2
        line_no = self.posting_no - 1
        self.connection.execute(ledger_postings.insert(), [
            {"transaction_id": self.transaction_id, "line_no": line_no,
             "currency": currency, "account_key": f"player:{self.command.player_id}", "delta": delta},
            {"transaction_id": self.transaction_id, "line_no": self.posting_no,
             "currency": currency, "account_key": "system:issuance" if delta >= 0 else "system:sink", "delta": -delta},
        ])
        self.connection.execute(update(wallets).where(
            wallets.c.player_id == self.command.player_id, wallets.c.currency == currency,
        ).values(balance=balance, version=wallet["version"] + 1, updated_at=func.now()))
        self.connection.execute(wallet_ledger.insert().values(
            id=uuid4(), player_id=self.command.player_id, currency=currency, delta=delta,
            balance_after=balance, reason=reason, command_id=self.command.command_id,
            transaction_id=self.transaction_id, line_no=line_no,
        ))
        return balance

    def emit(self, event_type: str, body: dict) -> UUID:
        event_id = uuid4()
        self.connection.execute(outbox_events.insert().values(
            id=event_id, player_id=self.command.player_id, command_id=self.command.command_id,
            event_type=event_type, body=body,
        ))
        self.event_ids.append(event_id)
        return event_id


Handler = Callable[[UnitOfWork, dict], dict]


class CommandExecutor:
    def __init__(self, engine: Engine, handlers: dict[str, Handler]):
        self.engine = engine
        self.handlers = dict(handlers)

    def execute(self, command: GameCommand) -> CommandResult:
        if any(type(value) is not UUID for value in (
            command.command_id, command.account_id, command.content_version_id,
        )) or any(type(value) is not int or not 0 < value <= MAX_BALANCE for value in (
            command.player_id, command.server_id,
        )) or type(command.expected_version) is not int or not 0 <= command.expected_version < 2_147_483_647:
            raise DomainFailure("VALIDATION_ERROR", "Invalid command identity or version")
        if type(command.route) is not str or not command.route or len(command.route) > 160 or type(command.payload) is not dict:
            raise DomainFailure("VALIDATION_ERROR", "Invalid route or payload")
        handler = self.handlers.get(command.route)
        if handler is None:
            raise DomainFailure("NOT_IMPLEMENTED", "Route is not registered")
        # Capture the payload once: the hash and handler must see identical data.
        try:
            payload = json.loads(json.dumps(command.payload, allow_nan=False))
            command = replace(command, payload=payload)
            fingerprint = json.dumps(asdict(command), sort_keys=True, separators=(",", ":"), default=str, allow_nan=False)
        except (TypeError, ValueError, RecursionError):
            raise DomainFailure("VALIDATION_ERROR", "Invalid command") from None
        digest = hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()
        with self.engine.begin() as connection:
            # The aggregate row serializes fresh commands and retries alike.
            player = connection.execute(select(players).where(
                players.c.id == command.player_id,
            ).with_for_update()).mappings().one_or_none()
            if player is None or player["account_id"] != command.account_id or player["server_id"] != command.server_id:
                raise DomainFailure("FORBIDDEN", "Player is not owned in this server")
            saved = connection.execute(select(command_receipts).where(
                command_receipts.c.player_id == command.player_id,
                command_receipts.c.command_id == command.command_id,
            )).mappings().one_or_none()
            if saved:
                if saved["payload_hash"] != digest:
                    raise DomainFailure("CONFLICT", "Command key has different input")
                envelope = saved["result_json"]
                return CommandResult(command.command_id, saved["aggregate_version"],
                                     UUID(envelope["content_version_id"]), envelope["result"],
                                     tuple(UUID(value) for value in envelope["event_ids"]))
            if player["version"] != command.expected_version:
                raise DomainFailure("CONFLICT", "Stale player version")
            content = connection.execute(select(content_versions.c.id).join(
                game_servers, game_servers.c.active_content_version_id == content_versions.c.id,
            ).where(game_servers.c.id == command.server_id, game_servers.c.status == "OPEN",
                    content_versions.c.id == command.content_version_id,
                    content_versions.c.status == "PUBLISHED").with_for_update(read=True)).first()
            if content is None:
                raise DomainFailure("CONTENT_UNAVAILABLE", "Published server content is unavailable")
            work = UnitOfWork(connection, command)
            result = handler(work, payload)
            version = player["version"] + 1
            connection.execute(update(players).where(players.c.id == command.player_id).values(
                version=version, updated_at=func.now(),
            ))
            envelope = {"content_version_id": str(command.content_version_id), "result": result,
                        "event_ids": [str(value) for value in work.event_ids]}
            connection.execute(command_receipts.insert().values(
                player_id=command.player_id, command_id=command.command_id, route=command.route,
                payload_hash=digest, result_json=envelope, aggregate_version=version, status="COMMITTED",
                content_version_id=command.content_version_id,
            ))
        return CommandResult(command.command_id, version, command.content_version_id,
                             result, tuple(work.event_ids))
