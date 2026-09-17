CREATE TABLE content_chapter_sources (
    import_id UUID PRIMARY KEY REFERENCES content_source_imports(id),
    payload JSONB NOT NULL CHECK (jsonb_typeof(payload) = 'object')
);
CREATE TRIGGER immutable_chapter_sources BEFORE UPDATE OR DELETE OR TRUNCATE
ON content_chapter_sources FOR EACH STATEMENT EXECUTE FUNCTION deny_content_source_change();

CREATE TABLE normal_map_definitions (
    content_version_id UUID NOT NULL REFERENCES content_versions(id),
    kind_id BIGINT NOT NULL CHECK (kind_id BETWEEN 1 AND 9007199254740991),
    chapter_id BIGINT NOT NULL CHECK (chapter_id BETWEEN 1 AND 9007199254740991),
    chapter_rank BIGINT NOT NULL CHECK (chapter_rank > 0),
    rank BIGINT NOT NULL CHECK (rank > 0),
    predecessor_id BIGINT,
    chapter_level_limit BIGINT NOT NULL CHECK (chapter_level_limit >= 0),
    action_point BIGINT NOT NULL CHECK (action_point >= 0),
    level_limit BIGINT NOT NULL CHECK (level_limit >= 0),
    times BIGINT NOT NULL CHECK (times > 0),
    role_exp BIGINT NOT NULL CHECK (role_exp >= 0),
    coin BIGINT NOT NULL CHECK (coin >= 0),
    PRIMARY KEY (content_version_id, kind_id),
    UNIQUE (content_version_id, chapter_id, rank),
    FOREIGN KEY (content_version_id, predecessor_id)
      REFERENCES normal_map_definitions(content_version_id, kind_id)
      DEFERRABLE INITIALLY DEFERRED
);
CREATE TABLE normal_map_waves (
    content_version_id UUID NOT NULL,
    map_id BIGINT NOT NULL,
    zone INTEGER NOT NULL CHECK (zone BETWEEN 1 AND 2),
    position INTEGER NOT NULL CHECK (position > 0),
    mob_id BIGINT NOT NULL CHECK (mob_id BETWEEN 1 AND 9007199254740991),
    PRIMARY KEY (content_version_id, map_id, zone, position),
    FOREIGN KEY (content_version_id, map_id)
      REFERENCES normal_map_definitions(content_version_id, kind_id)
);
CREATE FUNCTION protect_normal_map_projection() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    version_id UUID;
    version_status VARCHAR(16);
BEGIN
    version_id := CASE WHEN TG_OP = 'INSERT' THEN NEW.content_version_id ELSE OLD.content_version_id END;
    SELECT status INTO version_status FROM content_versions WHERE id = version_id FOR SHARE;
    IF version_status IS DISTINCT FROM 'DRAFT' THEN
        RAISE EXCEPTION 'published normal map projection is immutable' USING ERRCODE = '23514';
    END IF;
    IF TG_OP = 'UPDATE' AND (
        NEW.content_version_id IS DISTINCT FROM OLD.content_version_id OR
        to_jsonb(NEW)->'kind_id' IS DISTINCT FROM to_jsonb(OLD)->'kind_id' OR
        to_jsonb(NEW)->'map_id' IS DISTINCT FROM to_jsonb(OLD)->'map_id' OR
        to_jsonb(NEW)->'zone' IS DISTINCT FROM to_jsonb(OLD)->'zone' OR
        to_jsonb(NEW)->'position' IS DISTINCT FROM to_jsonb(OLD)->'position'
    ) THEN
        RAISE EXCEPTION 'normal map projection identity is immutable' USING ERRCODE = '23514';
    END IF;
    IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER protect_normal_map BEFORE INSERT OR UPDATE OR DELETE
ON normal_map_definitions FOR EACH ROW EXECUTE FUNCTION protect_normal_map_projection();
CREATE TRIGGER protect_normal_wave BEFORE INSERT OR UPDATE OR DELETE
ON normal_map_waves FOR EACH ROW EXECUTE FUNCTION protect_normal_map_projection();
CREATE TRIGGER immutable_normal_map_truncate BEFORE TRUNCATE
ON normal_map_definitions FOR EACH STATEMENT EXECUTE FUNCTION deny_history_change();
CREATE TRIGGER immutable_normal_wave_truncate BEFORE TRUNCATE
ON normal_map_waves FOR EACH STATEMENT EXECUTE FUNCTION deny_history_change();
