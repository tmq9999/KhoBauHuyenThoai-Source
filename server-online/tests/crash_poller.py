"""Crash only a child worker processing a disposable integration-test schema."""

from datetime import datetime, timezone
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))

from kbht_server.db.session import database_url, open_engine
from kbht_server.workers.outbox import OutboxConsumer
from kbht_server.workers.poller import OutboxPoller
from pg_lab import project_counter

schema, phase = sys.argv[1:]
engine = open_engine(database_url("test"), schema=schema)


def handler(connection, event):
    project_counter(connection, event)
    if phase == "in-handler":
        os._exit(81)


worker = OutboxPoller(OutboxConsumer(engine, "test-progress-v1", {"test.progress": handler}),
                      lease_seconds=2, clock=lambda: datetime(2026, 9, 16, tzinfo=timezone.utc))
worker.discover()
lease = worker.claim()
if lease is None:
    raise RuntimeError("test worker did not claim an event")
if phase == "after-claim":
    os._exit(80)
worker.perform(lease)
os._exit(82)
