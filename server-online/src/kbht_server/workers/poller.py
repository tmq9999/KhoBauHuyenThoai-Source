"""Bounded, leased PostgreSQL delivery for transactional outbox handlers."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from threading import Event
from uuid import UUID, uuid4

from sqlalchemy import and_, exists, func, literal, or_, select, update
from sqlalchemy.dialects.postgresql import insert

from kbht_server.contracts import DomainFailure
from kbht_server.db.schema import outbox_deliveries, outbox_events, worker_receipts
from kbht_server.workers.outbox import OutboxConsumer


@dataclass(frozen=True)
class DeliveryLease:
    consumer: str
    event_id: UUID
    token: UUID
    attempt: int
    expires_at: datetime


class _LeaseExpired(Exception):
    pass


class OutboxPoller:
    """Persisted queue discovery, lease fencing, handler execution and retry."""

    def __init__(
        self,
        consumer: OutboxConsumer,
        *,
        lease_seconds: int = 30,
        max_attempts: int = 5,
        backoff_seconds: int = 1,
        max_backoff_seconds: int = 60,
        clock=None,
    ):
        if type(lease_seconds) is not int or not 0 < lease_seconds <= 3600:
            raise ValueError("lease_seconds must be between 1 and 3600")
        if type(max_attempts) is not int or not 1 <= max_attempts <= 100:
            raise ValueError("max_attempts must be between 1 and 100")
        if type(backoff_seconds) is not int or backoff_seconds < 0:
            raise ValueError("backoff_seconds must be nonnegative")
        if (type(max_backoff_seconds) is not int or not 1 <= max_backoff_seconds <= 86400
                or max_backoff_seconds < backoff_seconds):
            raise ValueError("max_backoff_seconds must be within 1..86400 and >= backoff_seconds")
        self.consumer = consumer
        self.lease_seconds = lease_seconds
        self.max_attempts = max_attempts
        self.backoff_seconds = backoff_seconds
        self.max_backoff_seconds = max_backoff_seconds
        self.clock = clock

    def _now(self, connection) -> datetime:
        now = self.clock() if self.clock is not None else connection.execute(select(func.clock_timestamp())).scalar_one()
        if not isinstance(now, datetime) or now.utcoffset() is None:
            raise ValueError("worker clock must return a timezone-aware datetime")
        return now

    def _key(self, event_id):
        return and_(outbox_deliveries.c.consumer == self.consumer.consumer,
                    outbox_deliveries.c.event_id == event_id)

    def discover(self, limit: int = 100) -> int:
        if type(limit) is not int or not 1 <= limit <= 1000:
            raise ValueError("limit must be between 1 and 1000")
        event_types = tuple(self.consumer.handlers)
        if not event_types:
            return 0
        with self.consumer.engine.begin() as connection:
            now = self._now(connection)
            statement = select(outbox_events.c.id).where(
                outbox_events.c.event_type.in_(event_types),
                ~exists().where(
                    outbox_deliveries.c.consumer == self.consumer.consumer,
                    outbox_deliveries.c.event_id == outbox_events.c.id,
                ),
                ~exists().where(worker_receipts.c.consumer == self.consumer.consumer,
                                worker_receipts.c.event_id == outbox_events.c.id),
            ).order_by(outbox_events.c.created_at, outbox_events.c.id).limit(limit)
            event_ids = connection.execute(statement).scalars().all()
            if not event_ids:
                return 0
            insert_statement = insert(outbox_deliveries).from_select(
                [outbox_deliveries.c.consumer, outbox_deliveries.c.event_id,
                 outbox_deliveries.c.next_attempt_at, outbox_deliveries.c.created_at, outbox_deliveries.c.max_attempts],
                select(
                    literal(self.consumer.consumer), outbox_events.c.id, literal(now), outbox_events.c.created_at,
                    literal(self.max_attempts),
                ).where(outbox_events.c.id.in_(event_ids)).order_by(outbox_events.c.id),
            ).on_conflict_do_nothing().returning(outbox_deliveries.c.event_id)
            return len(connection.execute(insert_statement).scalars().all())

    def claim(self) -> DeliveryLease | None:
        with self.consumer.engine.begin() as connection:
            now = self._now(connection)
            # Bound cleanup per claim; stale/poison rows cannot monopolize a transaction.
            for _ in range(100):
                row = connection.execute(select(outbox_deliveries).where(
                    outbox_deliveries.c.consumer == self.consumer.consumer,
                    or_(and_(outbox_deliveries.c.status.in_(["READY", "RETRY"]),
                             outbox_deliveries.c.next_attempt_at <= now),
                        and_(outbox_deliveries.c.status == "LEASED",
                             outbox_deliveries.c.lease_expires_at <= now)),
                ).order_by(outbox_deliveries.c.next_attempt_at, outbox_deliveries.c.created_at,
                           outbox_deliveries.c.event_id)
                .with_for_update(skip_locked=True).limit(1)).mappings().one_or_none()
                if row is None:
                    return None
                recorded = connection.execute(select(worker_receipts.c.event_id).where(
                    worker_receipts.c.consumer == self.consumer.consumer,
                    worker_receipts.c.event_id == row["event_id"],
                )).scalar_one_or_none()
                if recorded is not None:
                    connection.execute(update(outbox_deliveries).where(self._key(row["event_id"])).values(
                        status="DONE", lease_token=None, lease_expires_at=None,
                        last_error_code=None, updated_at=now,
                    ))
                    continue
                if row["attempts"] >= row["max_attempts"]:
                    connection.execute(update(outbox_deliveries).where(self._key(row["event_id"])).values(
                        status="DEAD", lease_token=None, lease_expires_at=None, updated_at=now,
                        last_error_code="LEASE_EXPIRED" if row["status"] == "LEASED" else "MAX_ATTEMPTS",
                    ))
                    continue
                token = uuid4()
                attempt = row["attempts"] + 1
                expires = now + timedelta(seconds=self.lease_seconds)
                connection.execute(update(outbox_deliveries).where(self._key(row["event_id"])).values(
                    status="LEASED", attempts=attempt, lease_token=token,
                    lease_expires_at=expires, updated_at=now,
                ))
                return DeliveryLease(self.consumer.consumer, row["event_id"], token, attempt, expires)
        return None

    def perform(self, lease: DeliveryLease) -> str:
        if not isinstance(lease, DeliveryLease) or lease.consumer != self.consumer.consumer:
            return "LOST"
        if type(lease.event_id) is not UUID or type(lease.token) is not UUID:
            return "LOST"
        try:
            with self.consumer.engine.begin() as connection:
                delivery = connection.execute(select(outbox_deliveries).where(
                    outbox_deliveries.c.consumer == lease.consumer,
                    outbox_deliveries.c.event_id == lease.event_id,
                    outbox_deliveries.c.lease_token == lease.token,
                    outbox_deliveries.c.status == "LEASED",
                ).with_for_update()).mappings().one_or_none()
                if delivery is None:
                    return "LOST"
                if self._now(connection) >= delivery["lease_expires_at"]:
                    return "LOST"
                self.consumer.consume_in_transaction(connection, lease.event_id)
                now = self._now(connection)
                if now >= delivery["lease_expires_at"]:
                    raise _LeaseExpired()
                connection.execute(update(outbox_deliveries).where(
                    outbox_deliveries.c.consumer == lease.consumer,
                    outbox_deliveries.c.event_id == lease.event_id,
                    outbox_deliveries.c.lease_token == lease.token,
                ).values(status="DONE", lease_token=None, lease_expires_at=None,
                         last_error_code=None, updated_at=now))
                return "DONE"
        except _LeaseExpired:
            # Leave the persisted lease for immediate fenced reclamation.
            return "LOST"
        except DomainFailure:
            return self._retry(lease, "DOMAIN_ERROR")
        except Exception:
            return self._retry(lease, "HANDLER_ERROR")

    def _retry(self, lease: DeliveryLease, error_code: str) -> str:
        with self.consumer.engine.begin() as connection:
            row = connection.execute(select(outbox_deliveries).where(
                outbox_deliveries.c.consumer == lease.consumer,
                outbox_deliveries.c.event_id == lease.event_id,
                outbox_deliveries.c.lease_token == lease.token,
                outbox_deliveries.c.status == "LEASED",
            ).with_for_update()).mappings().one_or_none()
            if row is None:
                return "LOST"
            now = self._now(connection)
            recorded = connection.execute(select(worker_receipts.c.event_id).where(
                worker_receipts.c.consumer == lease.consumer,
                worker_receipts.c.event_id == lease.event_id,
            )).scalar_one_or_none()
            if recorded is not None:
                connection.execute(update(outbox_deliveries).where(self._key(lease.event_id)).values(
                    status="DONE", lease_token=None, lease_expires_at=None,
                    last_error_code=None, updated_at=now,
                ))
                return "DONE"
            if now >= row["lease_expires_at"]:
                return "LOST"
            if row["attempts"] >= row["max_attempts"]:
                status, next_at = "DEAD", now
            else:
                delay = min(self.max_backoff_seconds, self.backoff_seconds * (2 ** (row["attempts"] - 1)))
                status, next_at = "RETRY", now + timedelta(seconds=delay)
            connection.execute(update(outbox_deliveries).where(
                outbox_deliveries.c.consumer == lease.consumer,
                outbox_deliveries.c.event_id == lease.event_id,
                outbox_deliveries.c.lease_token == lease.token,
                outbox_deliveries.c.status == "LEASED",
            ).values(status=status, lease_token=None, lease_expires_at=None,
                     next_attempt_at=next_at, last_error_code=error_code, updated_at=now))
            return "DEAD" if status == "DEAD" else "RETRY"

    def poll_once(self) -> str:
        self.discover()
        lease = self.claim()
        return "IDLE" if lease is None else self.perform(lease)

    def run(self, stop: Event, *, poll_interval: float = 0.5) -> None:
        if type(poll_interval) not in (int, float) or not 0 <= poll_interval <= 60:
            raise ValueError("poll_interval must be between 0 and 60")
        while not stop.is_set():
            self.poll_once()
            if not stop.is_set():
                stop.wait(poll_interval)
