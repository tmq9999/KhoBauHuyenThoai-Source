CREATE TABLE outbox_deliveries (
    consumer VARCHAR(80) NOT NULL,
    event_id UUID NOT NULL REFERENCES outbox_events(id),
    status VARCHAR(16) NOT NULL DEFAULT 'READY',
    attempts INTEGER NOT NULL DEFAULT 0,
    max_attempts INTEGER NOT NULL DEFAULT 5,
    lease_token UUID,
    lease_expires_at TIMESTAMPTZ,
    next_attempt_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_error_code VARCHAR(64),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (consumer, event_id),
    CONSTRAINT ck_outbox_delivery_status CHECK (status IN ('READY', 'LEASED', 'DONE', 'RETRY', 'DEAD')),
    CONSTRAINT ck_outbox_delivery_attempts CHECK (attempts BETWEEN 0 AND 100),
    CONSTRAINT ck_outbox_delivery_budget CHECK (max_attempts BETWEEN 1 AND 100 AND attempts <= max_attempts),
    CONSTRAINT ck_outbox_delivery_lease CHECK (
        (status = 'LEASED' AND lease_token IS NOT NULL AND lease_expires_at IS NOT NULL) OR
        (status != 'LEASED' AND lease_token IS NULL AND lease_expires_at IS NULL))
);

CREATE INDEX ix_outbox_delivery_ready ON outbox_deliveries(consumer, next_attempt_at, event_id)
WHERE status IN ('READY', 'RETRY');
CREATE INDEX ix_outbox_delivery_expiry ON outbox_deliveries(consumer, lease_expires_at, event_id)
WHERE status = 'LEASED';
CREATE INDEX ix_outbox_event_discovery ON outbox_events(event_type, created_at, id);

CREATE FUNCTION protect_outbox_delivery() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF (NEW.consumer, NEW.event_id, NEW.max_attempts, NEW.created_at) IS DISTINCT FROM
       (OLD.consumer, OLD.event_id, OLD.max_attempts, OLD.created_at) THEN
        RAISE EXCEPTION 'outbox delivery identity and retry budget are immutable' USING ERRCODE = '23514';
    END IF;
    IF OLD.status IN ('DONE', 'DEAD') THEN
        RAISE EXCEPTION 'terminal outbox delivery cannot be reopened' USING ERRCODE = '23514';
    END IF;
    IF NEW.attempts < OLD.attempts THEN
        RAISE EXCEPTION 'outbox attempt count cannot decrease' USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END
$$;

CREATE TRIGGER protect_outbox_delivery BEFORE UPDATE
ON outbox_deliveries FOR EACH ROW EXECUTE FUNCTION protect_outbox_delivery();
CREATE TRIGGER immutable_outbox_delivery_delete BEFORE DELETE OR TRUNCATE
ON outbox_deliveries FOR EACH STATEMENT EXECUTE FUNCTION deny_history_change();

CREATE FUNCTION require_outbox_receipt() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.status = 'DONE' AND NOT EXISTS (
        SELECT 1 FROM worker_receipts r WHERE r.consumer = NEW.consumer AND r.event_id = NEW.event_id
    ) THEN
        RAISE EXCEPTION 'done outbox delivery requires a worker receipt' USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END
$$;

CREATE CONSTRAINT TRIGGER outbox_delivery_receipt_required
AFTER INSERT OR UPDATE ON outbox_deliveries
DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION require_outbox_receipt();
