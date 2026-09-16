CREATE INDEX ix_inventory_owner ON inventory_items(player_id, kind_id, id);
CREATE INDEX ix_inventory_ledger_command ON inventory_ledger(player_id, command_id);
CREATE INDEX ix_inventory_ledger_grant ON inventory_ledger(reward_grant_id);
CREATE TRIGGER immutable_inventory_ledger BEFORE UPDATE OR DELETE OR TRUNCATE
ON inventory_ledger FOR EACH STATEMENT EXECUTE FUNCTION deny_history_change();
CREATE TRIGGER immutable_reward_grants BEFORE UPDATE OR DELETE OR TRUNCATE
ON reward_grants FOR EACH STATEMENT EXECUTE FUNCTION deny_history_change();
CREATE TRIGGER immutable_reward_items BEFORE UPDATE OR DELETE OR TRUNCATE
ON reward_items FOR EACH STATEMENT EXECUTE FUNCTION deny_history_change();
CREATE TRIGGER immutable_reward_currencies BEFORE UPDATE OR DELETE OR TRUNCATE
ON reward_currencies FOR EACH STATEMENT EXECUTE FUNCTION deny_history_change();

CREATE FUNCTION protect_published_item_definition() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    definition_version UUID;
    version_status VARCHAR(16);
BEGIN
    definition_version := CASE WHEN TG_OP = 'INSERT' THEN NEW.content_version_id ELSE OLD.content_version_id END;
    SELECT status INTO version_status FROM content_versions WHERE id = definition_version FOR SHARE;
    IF version_status != 'DRAFT' THEN
        RAISE EXCEPTION 'published item definition is immutable' USING ERRCODE = '23514';
    END IF;
    IF TG_OP = 'UPDATE' AND (NEW.content_version_id, NEW.kind_id) IS DISTINCT FROM (OLD.content_version_id, OLD.kind_id) THEN
        RAISE EXCEPTION 'item definition identity is immutable' USING ERRCODE = '23514';
    END IF;
    IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
    RETURN NEW;
END
$$;

CREATE TRIGGER protect_item_definition BEFORE INSERT OR UPDATE OR DELETE
ON item_definitions FOR EACH ROW EXECUTE FUNCTION protect_published_item_definition();
CREATE TRIGGER immutable_item_definition_truncate BEFORE TRUNCATE
ON item_definitions FOR EACH STATEMENT EXECUTE FUNCTION deny_history_change();
