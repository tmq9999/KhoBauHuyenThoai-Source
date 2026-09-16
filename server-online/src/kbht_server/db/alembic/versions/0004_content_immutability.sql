CREATE FUNCTION protect_published_content() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF OLD.status IN ('PUBLISHED', 'RETIRED') THEN
        RAISE EXCEPTION 'published content is immutable; select another release' USING ERRCODE = '23514';
    END IF;
    IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
    IF NEW.id IS DISTINCT FROM OLD.id THEN
        RAISE EXCEPTION 'content identity is immutable' USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END
$$;

CREATE TRIGGER protect_content_version BEFORE UPDATE OR DELETE
ON content_versions FOR EACH ROW EXECUTE FUNCTION protect_published_content();
CREATE TRIGGER immutable_content_truncate BEFORE TRUNCATE
ON content_versions FOR EACH STATEMENT EXECUTE FUNCTION deny_history_change();
