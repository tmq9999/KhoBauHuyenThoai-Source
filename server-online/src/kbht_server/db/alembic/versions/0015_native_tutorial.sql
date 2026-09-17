CREATE TABLE native_tutorial_content (
    content_version_id UUID PRIMARY KEY,
    source_sha256 VARCHAR(64) NOT NULL,
    rules_id VARCHAR(160) NOT NULL,
    definition_sha256 VARCHAR(64) NOT NULL,
    definitions JSONB NOT NULL CHECK (jsonb_typeof(definitions)='object'),
    FOREIGN KEY (content_version_id,rules_id) REFERENCES native_player_content(content_version_id,rules_id)
);
CREATE TRIGGER native_tutorial_content_draft BEFORE INSERT ON native_tutorial_content
FOR EACH ROW EXECUTE FUNCTION native_player_content_insert();
CREATE TRIGGER native_tutorial_content_immutable BEFORE UPDATE OR DELETE OR TRUNCATE
ON native_tutorial_content FOR EACH STATEMENT EXECUTE FUNCTION deny_content_source_change();

CREATE TABLE native_tutorial_claims (
    player_id BIGINT NOT NULL,
    draw_kind VARCHAR(4) NOT NULL CHECK (draw_kind IN ('coin','gem')),
    content_version_id UUID NOT NULL REFERENCES native_tutorial_content(content_version_id),
    command_id UUID NOT NULL,
    role_slot INTEGER NOT NULL,
    role_kind_id BIGINT NOT NULL,
    source_drop_id INTEGER NOT NULL,
    claimed_at_ms BIGINT NOT NULL CHECK (claimed_at_ms>0),
    PRIMARY KEY (player_id,draw_kind),
    UNIQUE (player_id,command_id),
    FOREIGN KEY (player_id,role_slot) REFERENCES native_owned_roles(player_id,slot),
    FOREIGN KEY (player_id,command_id) REFERENCES command_receipts(player_id,command_id) DEFERRABLE INITIALLY DEFERRED,
    CHECK ((draw_kind='coin' AND role_slot=2 AND role_kind_id=100201 AND source_drop_id=10001)
        OR (draw_kind='gem' AND role_slot=3 AND role_kind_id=100301 AND source_drop_id=10028))
);
CREATE TRIGGER native_tutorial_claims_immutable BEFORE UPDATE OR DELETE OR TRUNCATE
ON native_tutorial_claims FOR EACH STATEMENT EXECUTE FUNCTION deny_content_source_change();

-- Only an explicit administrative cutover may repin existing opening profiles.
-- Defer this existing FK; no rows or historical receipts are rewritten here.
ALTER TABLE native_owned_roles ALTER CONSTRAINT native_owned_roles_player_id_content_version_id_fkey
DEFERRABLE INITIALLY DEFERRED;
