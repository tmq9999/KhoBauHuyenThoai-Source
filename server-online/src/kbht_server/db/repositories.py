"""Inventory operations share the command executor's locked transaction."""

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import func, select, update

from kbht_server.contracts import DomainFailure
from kbht_server.db.schema import inventory_items, inventory_ledger, item_definitions

if TYPE_CHECKING:
    from kbht_server.db.uow import UnitOfWork

MAX_QUANTITY = 9_007_199_254_740_991
MAX_STACK_WRITES = 1000


def positive_int(value: int) -> None:
    if type(value) is not int or not 0 < value <= MAX_QUANTITY:
        raise DomainFailure("VALIDATION_ERROR", "Expected a positive safe integer")


def label(value: str, maximum: int) -> None:
    if type(value) is not str or not value.strip() or len(value) > maximum:
        raise DomainFailure("VALIDATION_ERROR", "Invalid operation label")


class InventoryRepository:
    def __init__(self, work: "UnitOfWork"):
        self.work = work

    def definition(self, kind_id: int) -> dict:
        positive_int(kind_id)
        row = self.work.connection.execute(select(item_definitions).where(
            item_definitions.c.content_version_id == self.work.command.content_version_id,
            item_definitions.c.kind_id == kind_id,
        ).with_for_update(read=True)).mappings().one_or_none()
        if row is None:
            raise DomainFailure("NOT_FOUND", "Item is absent from the command content version")
        return dict(row)

    def _owned_rows(self, kind_id: int) -> list[dict]:
        rows = self.work.connection.execute(select(inventory_items).where(
            inventory_items.c.player_id == self.work.command.player_id,
            inventory_items.c.kind_id == kind_id,
        ).order_by(inventory_items.c.id).with_for_update()).mappings().all()
        if any(row["content_version_id"] != self.work.command.content_version_id for row in rows):
            raise DomainFailure("CONTENT_UNAVAILABLE", "Inventory requires content migration")
        return [dict(row) for row in rows]

    def _record(self, row: dict, delta: int, *, reason: str, source_type: str,
                source_id: UUID, reward_grant_id: UUID | None) -> None:
        self.work.connection.execute(inventory_ledger.insert().values(
            id=uuid4(), inventory_id=row["id"], player_id=self.work.command.player_id,
            kind_id=row["kind_id"], command_id=self.work.command.command_id,
            content_version_id=self.work.command.content_version_id, delta=delta,
            quantity_after=row["quantity"], inventory_version=row["version"], reason=reason,
            source_type=source_type, source_id=source_id, reward_grant_id=reward_grant_id,
        ))

    def _change(self, row: dict, delta: int) -> dict:
        if row["version"] >= MAX_QUANTITY:
            raise DomainFailure("LIMIT_REACHED", "Inventory version exhausted")
        return dict(self.work.connection.execute(update(inventory_items).where(
            inventory_items.c.id == row["id"], inventory_items.c.player_id == self.work.command.player_id,
        ).values(quantity=row["quantity"] + delta, version=row["version"] + 1,
                 updated_at=func.now()).returning(inventory_items)).mappings().one())

    def add(self, kind_id: int, quantity: int, *, reason: str, source_type: str = "command",
            source_id: UUID | None = None, reward_grant_id: UUID | None = None) -> dict:
        positive_int(quantity)
        label(reason, 160)
        label(source_type, 64)
        source_id = self.work.command.command_id if source_id is None else source_id
        if type(source_id) is not UUID or (reward_grant_id is not None and type(reward_grant_id) is not UUID):
            raise DomainFailure("VALIDATION_ERROR", "Invalid inventory source")
        limit = self.definition(kind_id)["stack_limit"]
        rows = self._owned_rows(kind_id)
        total = sum(row["quantity"] for row in rows)
        if total + quantity > MAX_QUANTITY:
            raise DomainFailure("LIMIT_REACHED", "Inventory quantity capacity exceeded")
        if any(row["quantity"] > limit for row in rows):
            raise DomainFailure("CONTENT_UNAVAILABLE", "Inventory exceeds published stack limit")
        remaining = quantity
        changes = []
        for row in rows:
            delta = min(remaining, limit - row["quantity"])
            if delta:
                changes.append((row, delta))
                remaining -= delta
            if not remaining:
                break
        if len(changes) + (remaining + limit - 1) // limit > MAX_STACK_WRITES:
            raise DomainFailure("LIMIT_REACHED", "Inventory operation exceeds stack write limit")
        for row, delta in changes:
            after = self._change(row, delta)
            self._record(after, delta, reason=reason, source_type=source_type,
                         source_id=source_id, reward_grant_id=reward_grant_id)
        while remaining:
            delta = min(remaining, limit)
            after = dict(self.work.connection.execute(inventory_items.insert().values(
                player_id=self.work.command.player_id, content_version_id=self.work.command.content_version_id,
                kind_id=kind_id, stack_key=uuid4().hex, quantity=delta, version=1,
            ).returning(inventory_items)).mappings().one())
            self._record(after, delta, reason=reason, source_type=source_type,
                         source_id=source_id, reward_grant_id=reward_grant_id)
            remaining -= delta
        return {"kind_id": kind_id, "quantity": quantity, "total": total + quantity}

    def consume(self, kind_id: int, quantity: int, *, reason: str, inventory_id: int | None = None) -> dict:
        positive_int(quantity)
        label(reason, 160)
        self.definition(kind_id)
        rows = self._owned_rows(kind_id)
        if inventory_id is not None:
            positive_int(inventory_id)
            rows = [row for row in rows if row["id"] == inventory_id]
            if not rows:
                raise DomainFailure("NOT_FOUND", "Owned inventory record not found")
        total = sum(row["quantity"] for row in rows)
        if total < quantity:
            raise DomainFailure("INSUFFICIENT_FUNDS", "Insufficient item quantity")
        remaining = quantity
        changes = []
        for row in rows:
            delta = min(remaining, row["quantity"])
            if delta:
                changes.append((row, delta))
                remaining -= delta
            if not remaining:
                break
        if len(changes) > MAX_STACK_WRITES:
            raise DomainFailure("LIMIT_REACHED", "Inventory operation exceeds stack write limit")
        for row, delta in changes:
            after = self._change(row, -delta)
            self._record(after, -delta, reason=reason, source_type="command",
                         source_id=self.work.command.command_id, reward_grant_id=None)
        return {"kind_id": kind_id, "quantity": quantity, "remaining": total - quantity}
