CREATE FUNCTION deny_history_change() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'transaction history is append-only' USING ERRCODE = '23514';
END
$$;

CREATE TRIGGER immutable_wallet_ledger BEFORE UPDATE OR DELETE OR TRUNCATE
ON wallet_ledger FOR EACH STATEMENT EXECUTE FUNCTION deny_history_change();
CREATE TRIGGER immutable_ledger_transactions BEFORE UPDATE OR DELETE OR TRUNCATE
ON ledger_transactions FOR EACH STATEMENT EXECUTE FUNCTION deny_history_change();
CREATE TRIGGER immutable_ledger_postings BEFORE UPDATE OR DELETE OR TRUNCATE
ON ledger_postings FOR EACH STATEMENT EXECUTE FUNCTION deny_history_change();
CREATE TRIGGER immutable_command_receipts BEFORE UPDATE OR DELETE OR TRUNCATE
ON command_receipts FOR EACH STATEMENT EXECUTE FUNCTION deny_history_change();
