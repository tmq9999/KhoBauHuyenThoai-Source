CREATE TABLE equipment_source_snapshots (
    content_version_id UUID PRIMARY KEY REFERENCES content_versions(id),
    payload JSONB NOT NULL CHECK (jsonb_typeof(payload) = 'object')
);
CREATE TRIGGER immutable_equipment_source BEFORE UPDATE OR DELETE OR TRUNCATE
ON equipment_source_snapshots FOR EACH STATEMENT EXECUTE FUNCTION deny_content_source_change();

CREATE TABLE equipment_entities (
    content_version_id UUID NOT NULL REFERENCES content_versions(id),
    kind_id BIGINT NOT NULL CHECK (kind_id BETWEEN 1 AND 9007199254740991),
    payload JSONB NOT NULL CHECK (jsonb_typeof(payload) = 'object'),
    PRIMARY KEY (content_version_id,kind_id)
);
CREATE TABLE equipment_definitions (
    content_version_id UUID NOT NULL,
    kind_id BIGINT NOT NULL,
    next_kind_id BIGINT,
    effect JSONB NOT NULL CHECK (jsonb_typeof(effect) = 'object'),
    PRIMARY KEY (content_version_id,kind_id),
    FOREIGN KEY (content_version_id,kind_id) REFERENCES equipment_entities(content_version_id,kind_id),
    FOREIGN KEY (content_version_id,next_kind_id) REFERENCES equipment_definitions(content_version_id,kind_id)
      DEFERRABLE INITIALLY DEFERRED
);
CREATE TABLE equipment_requirements (
    content_version_id UUID NOT NULL,
    kind_id BIGINT NOT NULL,
    position INTEGER NOT NULL CHECK (position > 0),
    material_id BIGINT NOT NULL,
    quantity BIGINT NOT NULL CHECK (quantity BETWEEN 1 AND 9007199254740991),
    PRIMARY KEY (content_version_id,kind_id,position),
    UNIQUE (content_version_id,kind_id,material_id),
    FOREIGN KEY (content_version_id,kind_id) REFERENCES equipment_definitions(content_version_id,kind_id),
    FOREIGN KEY (content_version_id,material_id) REFERENCES equipment_entities(content_version_id,kind_id)
);
CREATE FUNCTION protect_equipment_content() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE version_id UUID; version_status VARCHAR(16);
BEGIN
    version_id := CASE WHEN TG_OP = 'INSERT' THEN NEW.content_version_id ELSE OLD.content_version_id END;
    SELECT status INTO version_status FROM content_versions WHERE id=version_id FOR SHARE;
    IF version_status IS DISTINCT FROM 'DRAFT' THEN
        RAISE EXCEPTION 'published equipment content is immutable' USING ERRCODE='23514';
    END IF;
    IF TG_OP='UPDATE' AND (
        NEW.content_version_id IS DISTINCT FROM OLD.content_version_id OR
        NEW.kind_id IS DISTINCT FROM OLD.kind_id OR
        to_jsonb(NEW)->'position' IS DISTINCT FROM to_jsonb(OLD)->'position'
    ) THEN RAISE EXCEPTION 'equipment identity is immutable' USING ERRCODE='23514'; END IF;
    IF TG_OP='DELETE' THEN RETURN OLD; END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER protect_equipment_entities BEFORE INSERT OR UPDATE OR DELETE
ON equipment_entities FOR EACH ROW EXECUTE FUNCTION protect_equipment_content();
CREATE TRIGGER protect_equipment_definitions BEFORE INSERT OR UPDATE OR DELETE
ON equipment_definitions FOR EACH ROW EXECUTE FUNCTION protect_equipment_content();
CREATE TRIGGER protect_equipment_requirements BEFORE INSERT OR UPDATE OR DELETE
ON equipment_requirements FOR EACH ROW EXECUTE FUNCTION protect_equipment_content();
CREATE TRIGGER deny_equipment_entities_truncate BEFORE TRUNCATE
ON equipment_entities FOR EACH STATEMENT EXECUTE FUNCTION deny_history_change();
CREATE TRIGGER deny_equipment_definitions_truncate BEFORE TRUNCATE
ON equipment_definitions FOR EACH STATEMENT EXECUTE FUNCTION deny_history_change();
CREATE TRIGGER deny_equipment_requirements_truncate BEFORE TRUNCATE
ON equipment_requirements FOR EACH STATEMENT EXECUTE FUNCTION deny_history_change();
