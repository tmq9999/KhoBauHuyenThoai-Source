CREATE TABLE content_dependency_archives (
    id UUID PRIMARY KEY,
    source_sha256 VARCHAR(64) NOT NULL CHECK (source_sha256 ~ '^[0-9a-f]{64}$'),
    format VARCHAR(64) NOT NULL,
    bundle_sha256 VARCHAR(64) NOT NULL CHECK (bundle_sha256 ~ '^[0-9a-f]{64}$'),
    bundle JSONB NOT NULL CHECK (jsonb_typeof(bundle) = 'object'),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (source_sha256, format)
);
CREATE TRIGGER immutable_dependency_archives BEFORE UPDATE OR DELETE OR TRUNCATE
ON content_dependency_archives FOR EACH STATEMENT EXECUTE FUNCTION deny_content_source_change();
