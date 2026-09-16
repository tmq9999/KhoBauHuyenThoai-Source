from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from kbht_server.contracts import DomainFailure
from kbht_server.workers.outbox import OutboxConsumer
from pg_lab import project_counter


def test_twenty_duplicate_deliveries_increment_once(pg_lab):
    event_id = pg_lab.emit_progress_event(10001, "upgradeEquipmentTimes", 1)
    with ThreadPoolExecutor(max_workers=20) as pool:
        results = list(pool.map(pg_lab.consume_progress_event, [event_id] * 20))
    assert results.count(True) == 1
    assert results.count(False) == 19
    assert pg_lab.progress(10001, "upgradeEquipmentTimes") == 1
    assert pg_lab.worker_receipt_count(event_id) == 1


def test_distinct_events_do_not_lose_updates_on_first_projection_row(pg_lab):
    events = [pg_lab.emit_progress_event(10001, "drawTimes", 1) for _ in range(20)]
    with ThreadPoolExecutor(max_workers=20) as pool:
        results = list(pool.map(pg_lab.consume_progress_event, events))
    assert results == [True] * 20
    assert pg_lab.progress(10001, "drawTimes") == 20


def test_handler_failure_rolls_back_receipt_and_projection(pg_lab):
    event_id = pg_lab.emit_progress_event(10001, "drawTimes", 1)

    def fail_after_update(connection, event):
        project_counter(connection, event)
        raise RuntimeError("test failure after projection")

    with pytest.raises(RuntimeError, match="after projection"):
        pg_lab.consumer(handler=fail_after_update).consume(event_id)
    assert pg_lab.progress(10001, "drawTimes") == 0
    assert pg_lab.worker_receipt_count(event_id) == 0
    assert pg_lab.consume_progress_event(event_id) is True
    assert pg_lab.progress(10001, "drawTimes") == 1


def test_receipt_insert_failure_prevents_projection(pg_lab):
    event_id = pg_lab.emit_progress_event(10001, "drawTimes", 1)
    with pg_lab.engine.begin() as connection:
        connection.execute(text("ALTER TABLE worker_receipts ADD CONSTRAINT fail_probe CHECK (false)"))
    with pytest.raises(DBAPIError):
        pg_lab.consume_progress_event(event_id)
    assert pg_lab.progress(10001, "drawTimes") == 0
    assert pg_lab.worker_receipt_count(event_id) == 0


def test_retry_after_worker_recreation_returns_saved_receipt(pg_lab):
    event_id = pg_lab.emit_progress_event(10002, "drawTimes", 2)
    assert pg_lab.consume_progress_event(event_id) is True
    pg_lab.engine.dispose()
    assert pg_lab.consumer().consume(event_id) is False
    assert pg_lab.progress(10002, "drawTimes") == 2
    assert pg_lab.progress(10001, "drawTimes") == 0


def test_receipts_are_per_consumer(pg_lab):
    event_id = pg_lab.emit_progress_event(10001, "drawTimes", 1)
    assert pg_lab.consume_progress_event(event_id) is True
    assert pg_lab.consumer(name="second-projection").consume(event_id) is True
    assert pg_lab.worker_receipt_count(event_id) == 2
    assert pg_lab.progress(10001, "drawTimes") == 2


def test_missing_or_unhandled_event_is_not_recorded_as_success(pg_lab):
    with pytest.raises(DomainFailure) as failure:
        pg_lab.consumer().consume(uuid4())
    assert failure.value.code == "NOT_FOUND"
    event_id = pg_lab.emit_progress_event(10001, "drawTimes", 1)
    with pytest.raises(DomainFailure) as failure:
        OutboxConsumer(pg_lab.engine, "unhandled", {}).consume(event_id)
    assert failure.value.code == "NOT_IMPLEMENTED"
    assert pg_lab.worker_receipt_count(event_id) == 0


@pytest.mark.parametrize("name", ["", " ", "a" * 81, None])
def test_bad_consumer_identity_is_rejected(pg_lab, name):
    with pytest.raises(ValueError):
        pg_lab.consumer(name=name)


def test_bad_event_identity_is_rejected(pg_lab):
    with pytest.raises(DomainFailure) as failure:
        pg_lab.consumer().consume("not-a-uuid")
    assert failure.value.code == "VALIDATION_ERROR"


@pytest.mark.parametrize("operation", ["UPDATE worker_receipts SET consumer = 'changed'", "DELETE FROM worker_receipts", "TRUNCATE worker_receipts"])
def test_receipts_are_append_only(pg_lab, operation):
    event_id = pg_lab.emit_progress_event(10001, "drawTimes", 1)
    assert pg_lab.consume_progress_event(event_id) is True
    with pytest.raises(DBAPIError, match="append-only"):
        with pg_lab.engine.begin() as connection:
            connection.execute(text(operation))


def test_event_cannot_change_between_consumer_deliveries(pg_lab):
    event_id = pg_lab.emit_progress_event(10001, "drawTimes", 1)
    assert pg_lab.consume_progress_event(event_id) is True
    with pytest.raises(DBAPIError, match="append-only"):
        with pg_lab.engine.begin() as connection:
            connection.execute(text("UPDATE outbox_events SET body = '{}'::jsonb WHERE id = :id"), {"id": event_id})
    assert pg_lab.consumer(name="second-projection").consume(event_id) is True
    assert pg_lab.progress(10001, "drawTimes") == 2
