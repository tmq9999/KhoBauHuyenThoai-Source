from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from threading import Event
from uuid import uuid4

import pytest
from sqlalchemy import text, update
from sqlalchemy.exc import DBAPIError

from kbht_server.db.schema import outbox_deliveries
from kbht_server.db.migrations import check_invariants
from kbht_server.contracts import DomainFailure
from kbht_server.workers.poller import OutboxPoller
from pg_lab import project_counter


class Clock:
    def __init__(self):
        self.value = datetime(2026, 9, 16, tzinfo=timezone.utc)

    def __call__(self):
        return self.value

    def advance(self, seconds):
        self.value += timedelta(seconds=seconds)


def poller(lab, clock, **kwargs):
    return OutboxPoller(lab.consumer(), clock=clock, **kwargs)


def delivery(lab, event_id, consumer="test-progress-v1"):
    with lab.engine.connect() as connection:
        return connection.execute(text("SELECT * FROM outbox_deliveries WHERE consumer=:consumer AND event_id=:id"),
                                  {"consumer": consumer, "id": event_id}).mappings().one()


def test_poll_discovers_committed_events_and_projects_once(pg_lab):
    event_id = pg_lab.emit_progress_event(10001, "drawTimes", 2)
    worker = poller(pg_lab, Clock())
    assert worker.poll_once() == "DONE"
    assert worker.poll_once() == "IDLE"
    assert pg_lab.progress(10001, "drawTimes") == 2
    assert pg_lab.worker_receipt_count(event_id) == 1
    assert delivery(pg_lab, event_id)["attempts"] == 1


def test_discovery_is_bounded_and_ignores_unsupported_types(pg_lab):
    for _ in range(5):
        pg_lab.emit_progress_event(10001, "drawTimes", 1)
    command = pg_lab.purchase_command(player_id=10001, cost_gem=10, reward_coin=1, key="unrelated")
    pg_lab.execute(command)
    worker = poller(pg_lab, Clock())
    assert worker.discover(limit=2) == 2
    assert worker.discover(limit=2) == 2
    assert worker.discover(limit=2) == 1
    assert worker.discover(limit=2) == 0


def test_concurrent_pollers_do_not_duplicate_delivery(pg_lab):
    events = [pg_lab.emit_progress_event(10001, "drawTimes", 1) for _ in range(20)]
    clock = Clock()
    workers = [poller(pg_lab, clock) for _ in range(20)]
    with ThreadPoolExecutor(max_workers=20) as pool:
        results = list(pool.map(lambda worker: worker.poll_once(), workers))
    assert results.count("DONE") == 20
    assert pg_lab.progress(10001, "drawTimes") == 20
    assert all(pg_lab.worker_receipt_count(value) == 1 for value in events)


def test_claim_is_exclusive_and_expired_lease_is_fenced(pg_lab):
    event_id = pg_lab.emit_progress_event(10001, "drawTimes", 1)
    clock = Clock()
    first = poller(pg_lab, clock, lease_seconds=10)
    first.discover()
    lease = first.claim()
    assert lease is not None
    second = poller(pg_lab, clock, lease_seconds=10)
    assert second.claim() is None
    clock.advance(10)
    replacement = second.claim()
    assert replacement is not None
    assert replacement.token != lease.token
    assert replacement.attempt == 2
    assert first.perform(lease) == "LOST"
    assert second.perform(replacement) == "DONE"
    assert pg_lab.progress(10001, "drawTimes") == 1
    assert delivery(pg_lab, event_id)["lease_token"] is None


def test_handler_failure_rolls_back_and_waits_for_exponential_backoff(pg_lab):
    event_id = pg_lab.emit_progress_event(10001, "drawTimes", 1)
    clock = Clock()
    def failing(connection, event):
        project_counter(connection, event)
        raise ValueError("private diagnostic must never be saved")
    worker = OutboxPoller(pg_lab.consumer(handler=failing), clock=clock, max_attempts=3,
                          backoff_seconds=2, max_backoff_seconds=3)
    assert worker.poll_once() == "RETRY"
    assert pg_lab.progress(10001, "drawTimes") == 0
    assert pg_lab.worker_receipt_count(event_id) == 0
    assert delivery(pg_lab, event_id)["next_attempt_at"] == clock.value + timedelta(seconds=2)
    assert worker.poll_once() == "IDLE"
    clock.advance(2)
    assert worker.poll_once() == "RETRY"
    assert delivery(pg_lab, event_id)["next_attempt_at"] == clock.value + timedelta(seconds=3)
    clock.advance(3)
    assert worker.poll_once() == "DEAD"
    row = delivery(pg_lab, event_id)
    assert row["attempts"] == 3
    assert row["last_error_code"] == "HANDLER_ERROR"
    assert "private diagnostic" not in str(dict(row))
    clock.advance(1000)
    assert poller(pg_lab, clock).poll_once() == "IDLE"


def test_failed_event_does_not_block_next_event(pg_lab):
    bad = pg_lab.emit_progress_event(10001, "bad", 1)
    good = pg_lab.emit_progress_event(10001, "good", 1)
    def handler(connection, event):
        if event.id == bad:
            raise ValueError("bad event")
        project_counter(connection, event)
    worker = OutboxPoller(pg_lab.consumer(handler=handler), clock=Clock())
    assert worker.poll_once() == "RETRY"
    assert worker.poll_once() == "DONE"
    assert pg_lab.worker_receipt_count(good) == 1


def test_retry_after_worker_recreation_retains_attempts(pg_lab):
    event_id = pg_lab.emit_progress_event(10001, "drawTimes", 1)
    clock = Clock()
    def fail(connection, event):
        raise ValueError("retry")
    worker = OutboxPoller(pg_lab.consumer(handler=fail), clock=clock)
    assert worker.poll_once() == "RETRY"
    pg_lab.engine.dispose()
    clock.advance(1)
    assert poller(pg_lab, clock).poll_once() == "DONE"
    assert delivery(pg_lab, event_id)["attempts"] == 2
    assert pg_lab.progress(10001, "drawTimes") == 1


def test_lost_workers_reach_dead_letter_limit(pg_lab):
    event_id = pg_lab.emit_progress_event(10001, "drawTimes", 1)
    clock = Clock()
    worker = poller(pg_lab, clock, lease_seconds=2, max_attempts=2)
    worker.discover()
    assert worker.claim() is not None
    clock.advance(2)
    assert worker.claim() is not None
    clock.advance(2)
    assert worker.claim() is None
    row = delivery(pg_lab, event_id)
    assert row["status"] == "DEAD"
    assert row["last_error_code"] == "LEASE_EXPIRED"


def test_expiry_during_handler_rolls_back_projection(pg_lab):
    event_id = pg_lab.emit_progress_event(10001, "drawTimes", 1)
    clock = Clock()
    def delayed(connection, event):
        project_counter(connection, event)
        clock.advance(5)
    worker = OutboxPoller(pg_lab.consumer(handler=delayed), clock=clock, lease_seconds=5)
    assert worker.poll_once() == "LOST"
    assert pg_lab.progress(10001, "drawTimes") == 0
    assert pg_lab.worker_receipt_count(event_id) == 0
    assert poller(pg_lab, clock).poll_once() == "DONE"


def test_direct_consumer_race_finishes_without_second_projection(pg_lab):
    event_id = pg_lab.emit_progress_event(10001, "drawTimes", 1)
    worker = poller(pg_lab, Clock())
    worker.discover()
    lease = worker.claim()
    assert lease is not None
    assert pg_lab.consume_progress_event(event_id) is True
    assert worker.perform(lease) == "DONE"
    assert pg_lab.progress(10001, "drawTimes") == 1


def test_other_consumer_cannot_use_lease(pg_lab):
    pg_lab.emit_progress_event(10001, "drawTimes", 1)
    clock = Clock()
    worker = poller(pg_lab, clock)
    worker.discover()
    lease = worker.claim()
    assert lease is not None
    other = OutboxPoller(pg_lab.consumer(name="other"), clock=clock)
    assert other.perform(lease) == "LOST"
    assert worker.perform(replace(lease, token=uuid4())) == "LOST"
    assert pg_lab.progress(10001, "drawTimes") == 0


@pytest.mark.parametrize("settings", [
    {"lease_seconds": 0}, {"max_attempts": True}, {"max_attempts": 101},
    {"backoff_seconds": -1}, {"max_backoff_seconds": 0}, {"lease_seconds": float("nan")},
])
def test_invalid_policy_is_rejected(pg_lab, settings):
    with pytest.raises(ValueError):
        poller(pg_lab, Clock(), **settings)


def test_loop_stops_after_current_delivery(pg_lab):
    event_id = pg_lab.emit_progress_event(10001, "drawTimes", 1)
    stop = Event()
    def handle(connection, event):
        project_counter(connection, event)
        stop.set()
    OutboxPoller(pg_lab.consumer(handler=handle), clock=Clock()).run(stop, poll_interval=0.01)
    assert pg_lab.worker_receipt_count(event_id) == 1


def test_retry_budget_survives_policy_change_and_restart(pg_lab):
    event_id = pg_lab.emit_progress_event(10001, "drawTimes", 1)
    clock = Clock()
    first = poller(pg_lab, clock, max_attempts=1, lease_seconds=1)
    first.discover()
    assert first.claim() is not None
    clock.advance(2)
    assert poller(pg_lab, clock, max_attempts=100).poll_once() == "IDLE"
    assert delivery(pg_lab, event_id)["status"] == "DEAD"


def test_direct_delivery_racing_active_poll_handler_cannot_duplicate(pg_lab):
    event_id = pg_lab.emit_progress_event(10001, "drawTimes", 1)
    entered, release = Event(), Event()
    def slow(connection, event):
        entered.set()
        assert release.wait(5)
        project_counter(connection, event)
    worker = OutboxPoller(pg_lab.consumer(handler=slow), clock=Clock())
    with ThreadPoolExecutor(max_workers=2) as pool:
        future = pool.submit(worker.poll_once)
        assert entered.wait(5)
        direct = pool.submit(pg_lab.consume_progress_event, event_id)
        release.set()
        assert future.result(timeout=10) == "DONE"
        assert direct.result(timeout=10) is False
    assert pg_lab.progress(10001, "drawTimes") == 1


def test_discovery_skips_completed_direct_receipts(pg_lab):
    event_id = pg_lab.emit_progress_event(10001, "drawTimes", 1)
    assert pg_lab.consume_progress_event(event_id) is True
    assert poller(pg_lab, Clock()).discover() == 0


def test_claim_skips_locked_row_without_waiting(pg_lab):
    first = pg_lab.emit_progress_event(10001, "first", 1)
    second = pg_lab.emit_progress_event(10001, "second", 1)
    worker = poller(pg_lab, Clock())
    worker.discover()
    with pg_lab.engine.begin() as connection:
        connection.execute(text("SELECT * FROM outbox_deliveries WHERE event_id=:id FOR UPDATE"), {"id": first})
        lease = worker.claim()
        assert lease.event_id == second
    assert worker.perform(lease) == "DONE"


def test_dead_event_cannot_be_reopened_without_an_audited_operation(pg_lab):
    event_id = pg_lab.emit_progress_event(10001, "drawTimes", 1)
    def fail(connection, event):
        raise ValueError("poison")
    assert OutboxPoller(pg_lab.consumer(handler=fail), clock=Clock(), max_attempts=1).poll_once() == "DEAD"
    with pytest.raises(DBAPIError):
        with pg_lab.engine.begin() as connection:
            connection.execute(update(outbox_deliveries).where(outbox_deliveries.c.event_id == event_id).values(status="READY"))


def test_done_requires_a_committed_worker_receipt(pg_lab):
    event_id = pg_lab.emit_progress_event(10001, "drawTimes", 1)
    poller(pg_lab, Clock()).discover()
    with pytest.raises(DBAPIError):
        with pg_lab.engine.begin() as connection:
            connection.execute(update(outbox_deliveries).where(outbox_deliveries.c.event_id == event_id).values(status="DONE"))


def test_deliveries_cannot_be_deleted_or_identity_retargeted(pg_lab):
    event_id = pg_lab.emit_progress_event(10001, "drawTimes", 1)
    poller(pg_lab, Clock()).discover()
    for statement in ("DELETE FROM outbox_deliveries", "TRUNCATE outbox_deliveries",
                      "UPDATE outbox_deliveries SET consumer='different'"):
        with pytest.raises(DBAPIError):
            with pg_lab.engine.begin() as connection:
                connection.execute(text(statement))
    assert delivery(pg_lab, event_id)["status"] == "READY"


def test_default_clock_uses_database_time(pg_lab):
    event_id = pg_lab.emit_progress_event(10001, "drawTimes", 1)
    worker = OutboxPoller(pg_lab.consumer())
    assert worker.poll_once() == "DONE"
    assert pg_lab.worker_receipt_count(event_id) == 1


def test_polling_with_receipt_failure_rolls_back_projection(pg_lab):
    event_id = pg_lab.emit_progress_event(10001, "drawTimes", 1)
    with pg_lab.engine.begin() as connection:
        connection.execute(text("ALTER TABLE worker_receipts ADD CONSTRAINT reject_receipt CHECK (false)"))
    assert poller(pg_lab, Clock()).poll_once() == "RETRY"
    assert pg_lab.progress(10001, "drawTimes") == 0
    assert pg_lab.worker_receipt_count(event_id) == 0


def test_stale_worker_error_cannot_overwrite_replacement_lease(pg_lab):
    event_id = pg_lab.emit_progress_event(10001, "drawTimes", 1)
    clock = Clock()
    worker = poller(pg_lab, clock, lease_seconds=1)
    worker.discover()
    original = worker.claim()
    clock.advance(1)
    replacement = poller(pg_lab, clock).claim()
    assert worker._retry(original, "HANDLER_ERROR") == "LOST"
    assert delivery(pg_lab, event_id)["lease_token"] == replacement.token


def test_completed_receipt_wins_over_expired_final_lease(pg_lab):
    event_id = pg_lab.emit_progress_event(10001, "drawTimes", 1)
    clock = Clock()
    worker = poller(pg_lab, clock, lease_seconds=1, max_attempts=1)
    worker.discover()
    assert worker.claim() is not None
    assert pg_lab.consume_progress_event(event_id) is True
    clock.advance(2)
    assert worker.poll_once() == "IDLE"
    assert delivery(pg_lab, event_id)["status"] == "DONE"
    assert pg_lab.progress(10001, "drawTimes") == 1


def test_database_error_rolls_back_handler_then_retries(pg_lab):
    event_id = pg_lab.emit_progress_event(10001, "drawTimes", 1)
    def invalid_statement(connection, event):
        project_counter(connection, event)
        connection.execute(text("SELECT 1 / 0"))
    clock = Clock()
    worker = OutboxPoller(pg_lab.consumer(handler=invalid_statement), clock=clock)
    assert worker.poll_once() == "RETRY"
    assert pg_lab.progress(10001, "drawTimes") == 0
    assert pg_lab.worker_receipt_count(event_id) == 0
    clock.advance(1)
    assert poller(pg_lab, clock).poll_once() == "DONE"


def test_transaction_consumer_rolls_back_with_outer_transaction(pg_lab):
    event_id = pg_lab.emit_progress_event(10001, "drawTimes", 1)
    with pytest.raises(RuntimeError):
        with pg_lab.engine.begin() as connection:
            assert pg_lab.consumer().consume_in_transaction(connection, event_id) is True
            raise RuntimeError("outer command failed")
    assert pg_lab.progress(10001, "drawTimes") == 0
    assert pg_lab.worker_receipt_count(event_id) == 0


def test_poller_handles_backdated_late_commit_without_watermark_loss(pg_lab):
    first = pg_lab.emit_progress_event(10001, "drawTimes", 1)
    worker = poller(pg_lab, Clock())
    assert worker.poll_once() == "DONE"
    # Producer transactions can start before others yet commit later.
    with pg_lab.engine.begin() as connection:
        event_id = uuid4()
        connection.execute(text("""INSERT INTO outbox_events (id, player_id, command_id, event_type, body, created_at)
            SELECT :new_id, player_id, :cmd, event_type, body, created_at - interval '1 hour'
            FROM outbox_events WHERE id=:id"""), {"new_id": event_id, "cmd": uuid4(), "id": first})
    assert worker.poll_once() == "DONE"
    assert pg_lab.progress(10001, "drawTimes") == 2


@pytest.mark.parametrize("limit", [0, -1, 1001, True, 1.5])
def test_invalid_discovery_bound_is_rejected(pg_lab, limit):
    with pytest.raises(ValueError):
        poller(pg_lab, Clock()).discover(limit)


@pytest.mark.parametrize("interval", [-1, True, float("nan"), float("inf"), 61])
def test_invalid_poll_interval_is_rejected(pg_lab, interval):
    stop = Event()
    stop.set()
    with pytest.raises(ValueError):
        poller(pg_lab, Clock()).run(stop, poll_interval=interval)


def test_invariants_detect_delivery_marked_done_without_receipt(pg_lab):
    event_id = pg_lab.emit_progress_event(10001, "drawTimes", 1)
    poller(pg_lab, Clock()).discover()
    with pg_lab.engine.begin() as connection:
        # Corrupt only the generated test schema to exercise restore reconciliation.
        connection.execute(text("ALTER TABLE outbox_deliveries DISABLE TRIGGER USER"))
        connection.execute(update(outbox_deliveries).where(outbox_deliveries.c.event_id == event_id).values(status="DONE"))
        connection.execute(text("ALTER TABLE outbox_deliveries ENABLE TRIGGER USER"))
    with pytest.raises(RuntimeError, match="delivery_mismatches"):
        check_invariants(pg_lab.engine)


def test_poison_state_is_not_an_economy_invariant_failure(pg_lab):
    pg_lab.emit_progress_event(10001, "drawTimes", 1)
    def fail(connection, event):
        raise ValueError("poison event")
    assert OutboxPoller(pg_lab.consumer(handler=fail), clock=Clock(), max_attempts=1).poll_once() == "DEAD"
    assert not any(check_invariants(pg_lab.engine).values())


@pytest.mark.parametrize("options", [{"max_backoff_seconds": 86401}, {"backoff_seconds": 86401}])
def test_retry_delay_policy_is_bounded(pg_lab, options):
    with pytest.raises(ValueError):
        poller(pg_lab, Clock(), **options)


def test_direct_delivery_cannot_bypass_dead_letter_quarantine(pg_lab):
    event_id = pg_lab.emit_progress_event(10001, "drawTimes", 1)
    def fail(connection, event):
        raise ValueError("bad event")
    assert OutboxPoller(pg_lab.consumer(handler=fail), clock=Clock(), max_attempts=1).poll_once() == "DEAD"
    with pytest.raises(DomainFailure) as error:
        pg_lab.consume_progress_event(event_id)
    assert error.value.code == "CONFLICT"
    assert pg_lab.progress(10001, "drawTimes") == 0


def test_successful_direct_delivery_wins_over_failure_recording(pg_lab):
    event_id = pg_lab.emit_progress_event(10001, "drawTimes", 1)
    worker = poller(pg_lab, Clock(), max_attempts=1)
    worker.discover()
    lease = worker.claim()
    # A failed handler releases its transaction before retry metadata is recorded.
    assert pg_lab.consume_progress_event(event_id) is True
    assert worker._retry(lease, "HANDLER_ERROR") == "DONE"
    assert delivery(pg_lab, event_id)["status"] == "DONE"
    assert pg_lab.progress(10001, "drawTimes") == 1
