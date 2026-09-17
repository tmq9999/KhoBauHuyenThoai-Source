CREATE TABLE fixed_box_definitions (
    content_version_id UUID NOT NULL,
    kind_id BIGINT NOT NULL,
    source_payload JSONB NOT NULL CHECK (jsonb_typeof(source_payload)='object'),
    PRIMARY KEY(content_version_id,kind_id),
    FOREIGN KEY(content_version_id,kind_id) REFERENCES item_definitions(content_version_id,kind_id)
);
CREATE TABLE fixed_box_rewards (
    content_version_id UUID NOT NULL,
    kind_id BIGINT NOT NULL,
    reward_kind_id BIGINT NOT NULL,
    quantity BIGINT NOT NULL CHECK (quantity BETWEEN 1 AND 9007199254740991),
    PRIMARY KEY(content_version_id,kind_id,reward_kind_id),
    CHECK (kind_id != reward_kind_id),
    FOREIGN KEY(content_version_id,kind_id) REFERENCES fixed_box_definitions(content_version_id,kind_id),
    FOREIGN KEY(content_version_id,reward_kind_id) REFERENCES item_definitions(content_version_id,kind_id)
);
CREATE FUNCTION protect_fixed_box_content() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE version_id UUID; version_status VARCHAR(16);
BEGIN
    version_id := CASE WHEN TG_OP='INSERT' THEN NEW.content_version_id ELSE OLD.content_version_id END;
    SELECT status INTO version_status FROM content_versions WHERE id=version_id FOR SHARE;
    IF version_status IS DISTINCT FROM 'DRAFT' THEN
        RAISE EXCEPTION 'published fixed box content is immutable' USING ERRCODE='23514';
    END IF;
    IF TG_OP='UPDATE' AND (
        NEW.content_version_id IS DISTINCT FROM OLD.content_version_id OR NEW.kind_id IS DISTINCT FROM OLD.kind_id OR
        to_jsonb(NEW)->'reward_kind_id' IS DISTINCT FROM to_jsonb(OLD)->'reward_kind_id'
    ) THEN RAISE EXCEPTION 'fixed box identity is immutable' USING ERRCODE='23514'; END IF;
    IF TG_OP='DELETE' THEN RETURN OLD; END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER protect_fixed_box_definition BEFORE INSERT OR UPDATE OR DELETE
ON fixed_box_definitions FOR EACH ROW EXECUTE FUNCTION protect_fixed_box_content();
CREATE TRIGGER protect_fixed_box_reward BEFORE INSERT OR UPDATE OR DELETE
ON fixed_box_rewards FOR EACH ROW EXECUTE FUNCTION protect_fixed_box_content();
CREATE TRIGGER deny_fixed_box_definition_truncate BEFORE TRUNCATE
ON fixed_box_definitions FOR EACH STATEMENT EXECUTE FUNCTION deny_history_change();
CREATE TRIGGER deny_fixed_box_reward_truncate BEFORE TRUNCATE
ON fixed_box_rewards FOR EACH STATEMENT EXECUTE FUNCTION deny_history_change();
