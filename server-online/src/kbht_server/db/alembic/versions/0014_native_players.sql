CREATE TABLE native_player_content (
    content_version_id UUID PRIMARY KEY REFERENCES content_versions(id),
    source_sha256 VARCHAR(64) NOT NULL,
    rules_id VARCHAR(160) NOT NULL CHECK (length(rules_id)>0),
    definition_sha256 VARCHAR(64) NOT NULL,
    definitions JSONB NOT NULL CHECK (jsonb_typeof(definitions)='object'),
    policy JSONB NOT NULL CHECK (jsonb_typeof(policy)='object'),
    UNIQUE (content_version_id,rules_id)
);
CREATE FUNCTION native_player_content_insert() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM content_versions WHERE id=NEW.content_version_id
      AND status='DRAFT' AND source_sha256=NEW.source_sha256 FOR SHARE) THEN
        RAISE EXCEPTION 'native player content requires matching draft' USING ERRCODE='23514';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER native_player_content_draft BEFORE INSERT ON native_player_content
FOR EACH ROW EXECUTE FUNCTION native_player_content_insert();
CREATE TRIGGER native_player_content_immutable BEFORE UPDATE OR DELETE OR TRUNCATE
ON native_player_content FOR EACH STATEMENT EXECUTE FUNCTION deny_content_source_change();

CREATE SEQUENCE native_player_id_seq AS BIGINT MINVALUE 10001 MAXVALUE 9007199254740991 START 10001 NO CYCLE;
SELECT setval('native_player_id_seq', GREATEST(10001,COALESCE((SELECT max(id)+1 FROM players),10001)),false);
CREATE TABLE native_player_profiles (
    player_id BIGINT PRIMARY KEY REFERENCES players(id),
    content_version_id UUID NOT NULL,
    rules_id VARCHAR(160) NOT NULL,
    level INTEGER NOT NULL CHECK (level BETWEEN 1 AND 100),
    experience BIGINT NOT NULL CHECK (experience BETWEEN 0 AND 9007199254740991),
    first_rename_completed BOOLEAN NOT NULL,
    photo_img_id INTEGER NOT NULL CHECK (photo_img_id>0),
    ship_img_id INTEGER NOT NULL CHECK (ship_img_id>0),
    skill_point_cap INTEGER NOT NULL CHECK (skill_point_cap>=10),
    next_action_recover_ms BIGINT NOT NULL CHECK (next_action_recover_ms>=0),
    next_skill_recover_ms BIGINT NOT NULL CHECK (next_skill_recover_ms>=0),
    vip_level INTEGER NOT NULL CHECK (vip_level>=0),
    vip_top_up_gem BIGINT NOT NULL CHECK (vip_top_up_gem>=0),
    vip_gift_gem BIGINT NOT NULL CHECK (vip_gift_gem>=0),
    buy_action_point_times INTEGER NOT NULL CHECK (buy_action_point_times>=0),
    buy_skill_point_times INTEGER NOT NULL CHECK (buy_skill_point_times>=0),
    UNIQUE (player_id,content_version_id),
    FOREIGN KEY (content_version_id,rules_id) REFERENCES native_player_content(content_version_id,rules_id)
);
CREATE TABLE native_owned_roles (
    player_id BIGINT NOT NULL,
    slot INTEGER NOT NULL CHECK (slot BETWEEN 1 AND 10000),
    content_version_id UUID NOT NULL,
    kind_id BIGINT NOT NULL CHECK (kind_id BETWEEN 1 AND 9007199254740991),
    star INTEGER NOT NULL CHECK (star BETWEEN 1 AND 20),
    level INTEGER NOT NULL CHECK (level BETWEEN 1 AND 100),
    experience BIGINT NOT NULL CHECK (experience BETWEEN 0 AND 9007199254740991),
    awake_level INTEGER NOT NULL CHECK (awake_level BETWEEN 0 AND 20),
    awake_rate_increase_times INTEGER NOT NULL CHECK (awake_rate_increase_times>=0),
    PRIMARY KEY (player_id,slot), UNIQUE (player_id,kind_id),
    FOREIGN KEY (player_id,content_version_id) REFERENCES native_player_profiles(player_id,content_version_id)
);
CREATE TABLE native_role_skills (
    player_id BIGINT NOT NULL,
    role_slot INTEGER NOT NULL,
    kind_id BIGINT NOT NULL CHECK (kind_id BETWEEN 1 AND 9007199254740991),
    skill_group VARCHAR(16) NOT NULL CHECK (skill_group IN ('skills','awakeSkills')),
    level INTEGER NOT NULL CHECK (level BETWEEN 1 AND 100),
    PRIMARY KEY (player_id,role_slot,kind_id),
    FOREIGN KEY (player_id,role_slot) REFERENCES native_owned_roles(player_id,slot)
);
CREATE TABLE native_role_equipment (
    player_id BIGINT NOT NULL,
    role_slot INTEGER NOT NULL,
    equipment_slot INTEGER NOT NULL CHECK (equipment_slot BETWEEN 1 AND 6),
    kind_id BIGINT NOT NULL CHECK (kind_id BETWEEN 1 AND 9007199254740991),
    level INTEGER NOT NULL CHECK (level BETWEEN 1 AND 100),
    PRIMARY KEY (player_id,role_slot,equipment_slot),
    FOREIGN KEY (player_id,role_slot) REFERENCES native_owned_roles(player_id,slot)
);
CREATE TABLE native_map_progress (
    player_id BIGINT NOT NULL REFERENCES native_player_profiles(player_id),
    map_type INTEGER NOT NULL CHECK (map_type>0),
    chapter_id INTEGER NOT NULL CHECK (chapter_id>0),
    map_id INTEGER NOT NULL CHECK (map_id>0),
    star INTEGER NOT NULL CHECK (star BETWEEN 0 AND 3),
    attempts INTEGER NOT NULL CHECK (attempts>=0),
    PRIMARY KEY (player_id,map_id)
);
