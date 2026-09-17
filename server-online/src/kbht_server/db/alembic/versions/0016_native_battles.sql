CREATE TABLE native_battle_content (
 content_version_id UUID PRIMARY KEY,
 source_sha256 VARCHAR(64) NOT NULL,
 rules_id VARCHAR(160) NOT NULL,
 definition_sha256 VARCHAR(64) NOT NULL,
 definitions JSONB NOT NULL CHECK(jsonb_typeof(definitions)='object'),
 FOREIGN KEY(content_version_id,rules_id) REFERENCES native_player_content(content_version_id,rules_id)
);
CREATE TRIGGER native_battle_content_draft BEFORE INSERT ON native_battle_content
FOR EACH ROW EXECUTE FUNCTION native_player_content_insert();
CREATE TRIGGER native_battle_content_immutable BEFORE UPDATE OR DELETE OR TRUNCATE ON native_battle_content
FOR EACH STATEMENT EXECUTE FUNCTION deny_content_source_change();
CREATE TABLE native_battle_sessions (
 id UUID PRIMARY KEY,
 player_id BIGINT NOT NULL REFERENCES players(id),
 content_version_id UUID NOT NULL REFERENCES native_battle_content(content_version_id),
 smap_id INTEGER NOT NULL,
 seed BIGINT NOT NULL CHECK(seed BETWEEN 1 AND 4294967295),
 begin_body JSONB NOT NULL,
 battle_input JSONB NOT NULL,
 snapshot_sha256 VARCHAR(64) NOT NULL,
 content_sha256 VARCHAR(64) NOT NULL,
 engine_sha256 VARCHAR(64) NOT NULL,
 begin_response JSONB NOT NULL,
 created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
 expires_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()+interval '15 minutes',
 status VARCHAR(16) NOT NULL CHECK(status IN ('ACTIVE','SETTLED','EXPIRED')),
 UNIQUE(player_id,id), CHECK(expires_at>created_at)
);
CREATE UNIQUE INDEX native_battle_one_active ON native_battle_sessions(player_id) WHERE status='ACTIVE';
CREATE FUNCTION native_battle_session_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF TG_OP!='UPDATE' THEN RAISE EXCEPTION 'battle history immutable'; END IF;
 IF OLD.status!='ACTIVE' OR NEW.status NOT IN ('SETTLED','EXPIRED') OR
    (to_jsonb(NEW)-'status') IS DISTINCT FROM (to_jsonb(OLD)-'status') THEN
   RAISE EXCEPTION 'battle immutable snapshot';
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER native_battle_session_update BEFORE UPDATE OR DELETE ON native_battle_sessions
FOR EACH ROW EXECUTE FUNCTION native_battle_session_guard();
CREATE TRIGGER native_battle_session_truncate BEFORE TRUNCATE ON native_battle_sessions
FOR EACH STATEMENT EXECUTE FUNCTION deny_content_source_change();
CREATE TABLE native_battle_submissions (
 battle_id UUID PRIMARY KEY,
 player_id BIGINT NOT NULL,
 end_body JSONB NOT NULL,
 actions_sha256 VARCHAR(64) NOT NULL,
 FOREIGN KEY(player_id,battle_id) REFERENCES native_battle_sessions(player_id,id)
);
CREATE TRIGGER native_battle_submission_immutable BEFORE UPDATE OR DELETE OR TRUNCATE ON native_battle_submissions
FOR EACH STATEMENT EXECUTE FUNCTION deny_content_source_change();
CREATE TABLE native_battle_reports (
 battle_id UUID PRIMARY KEY,
 player_id BIGINT NOT NULL,
 end_body JSONB NOT NULL,
 actions_sha256 VARCHAR(64) NOT NULL,
 input_sha256 VARCHAR(64) NOT NULL,
 report JSONB NOT NULL,
 response JSONB NOT NULL,
 command_id UUID NOT NULL,
 FOREIGN KEY(player_id,battle_id) REFERENCES native_battle_sessions(player_id,id),
 FOREIGN KEY(player_id,command_id) REFERENCES command_receipts(player_id,command_id) DEFERRABLE INITIALLY DEFERRED
);
CREATE TRIGGER native_battle_report_immutable BEFORE UPDATE OR DELETE OR TRUNCATE ON native_battle_reports
FOR EACH STATEMENT EXECUTE FUNCTION deny_content_source_change();
CREATE TABLE native_battle_attempts (
 player_id BIGINT NOT NULL REFERENCES players(id),
 smap_id INTEGER NOT NULL,
 reset_day DATE NOT NULL,
 attempts INTEGER NOT NULL CHECK(attempts>0),
 PRIMARY KEY(player_id,smap_id,reset_day)
);
