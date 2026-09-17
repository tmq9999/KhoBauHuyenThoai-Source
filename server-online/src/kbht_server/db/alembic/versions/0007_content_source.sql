CREATE TABLE content_source_imports (
  id UUID PRIMARY KEY, source_sha256 VARCHAR(64) NOT NULL UNIQUE,
  table_name VARCHAR(64) NOT NULL, status VARCHAR(16) NOT NULL,
  row_count INTEGER NOT NULL CHECK (row_count > 0), created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT ck_content_source_import_status CHECK (status IN ('STAGED','VALIDATED','PUBLISHED','RETIRED'))
);
CREATE TABLE content_source_rows (
  import_id UUID NOT NULL REFERENCES content_source_imports(id),
  kind_id BIGINT NOT NULL, payload JSONB NOT NULL,
  PRIMARY KEY (import_id, kind_id)
);
CREATE FUNCTION deny_content_source_change() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'content source imports are immutable' USING ERRCODE = '23514'; END $$;
CREATE TRIGGER immutable_content_source_imports BEFORE UPDATE OR DELETE OR TRUNCATE ON content_source_imports FOR EACH STATEMENT EXECUTE FUNCTION deny_content_source_change();
CREATE TRIGGER immutable_content_source_rows BEFORE UPDATE OR DELETE OR TRUNCATE ON content_source_rows FOR EACH STATEMENT EXECUTE FUNCTION deny_content_source_change();
