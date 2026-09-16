CREATE TABLE worker_receipts (
    consumer VARCHAR(80) NOT NULL,
    event_id UUID NOT NULL REFERENCES outbox_events(id),
    processed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (consumer, event_id),
    CONSTRAINT ck_worker_receipts_consumer CHECK (length(consumer) > 0)
);

CREATE INDEX ix_worker_receipts_event_id ON worker_receipts(event_id);

CREATE TRIGGER immutable_worker_receipts BEFORE UPDATE OR DELETE OR TRUNCATE
ON worker_receipts FOR EACH STATEMENT EXECUTE FUNCTION deny_history_change();

CREATE TRIGGER immutable_outbox_events BEFORE UPDATE OR DELETE OR TRUNCATE
ON outbox_events FOR EACH STATEMENT EXECUTE FUNCTION deny_history_change();
