"""Transactional outbox consumption, independent of gameplay projections."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Connection, Engine

from kbht_server.contracts import DomainFailure
from kbht_server.db.schema import outbox_deliveries, outbox_events, worker_receipts


@dataclass(frozen=True)
class OutboxEvent:
    id: UUID
    player_id: int
    command_id: UUID
    event_type: str
    body: dict[str, Any]
    created_at: datetime


EventHandler = Callable[[Connection, OutboxEvent], None]


class OutboxConsumer:
    """Handlers make DB-only changes on the supplied connection, without commit."""

    def __init__(self, engine: Engine, consumer: str, handlers: dict[str, EventHandler]):
        if type(consumer) is not str or not consumer.strip() or len(consumer) > 80:
            raise ValueError("consumer name must be a nonempty string of at most 80 characters")
        self.engine = engine
        self.consumer = consumer
        self.handlers = dict(handlers)

    def consume(self, event_id: UUID) -> bool:
        with self.engine.begin() as connection:
            return self.consume_in_transaction(connection, event_id)

    def consume_in_transaction(self, connection: Connection, event_id: UUID) -> bool:
        """Share the caller's transaction; a handler failure must propagate for rollback."""
        if type(event_id) is not UUID:
            raise DomainFailure("VALIDATION_ERROR", "Invalid event identity")
        delivery = connection.execute(select(outbox_deliveries.c.status).where(
            outbox_deliveries.c.consumer == self.consumer,
            outbox_deliveries.c.event_id == event_id,
        ).with_for_update()).scalar_one_or_none()
        if delivery == "DEAD":
            raise DomainFailure("CONFLICT", "Outbox event is quarantined")
        if delivery == "DONE":
            return False
        # Lock delivery before the event so direct delivery and poller share one lock order.
        row = connection.execute(select(outbox_events).where(
            outbox_events.c.id == event_id,
        ).with_for_update(read=True)).mappings().one_or_none()
        if row is None:
            raise DomainFailure("NOT_FOUND", "Outbox event not found")
        handler = self.handlers.get(row["event_type"])
        if handler is None:
            raise DomainFailure("NOT_IMPLEMENTED", "Consumer does not handle this event type")
        # Claim before invoking a handler, including when a direct delivery races a poller.
        claimed = connection.execute(insert(worker_receipts).values(
            consumer=self.consumer, event_id=event_id,
        ).on_conflict_do_nothing(
            index_elements=[worker_receipts.c.consumer, worker_receipts.c.event_id],
        ).returning(worker_receipts.c.event_id)).scalar_one_or_none()
        if claimed is None:
            return False
        handler(connection, OutboxEvent(**row))
        return True
