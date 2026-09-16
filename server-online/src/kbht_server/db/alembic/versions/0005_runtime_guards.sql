CREATE FUNCTION protect_game_server_identity() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.id IS DISTINCT FROM OLD.id THEN
        RAISE EXCEPTION 'server identity is immutable' USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END
$$;

CREATE TRIGGER immutable_game_server_identity BEFORE UPDATE OF id
ON game_servers FOR EACH ROW EXECUTE FUNCTION protect_game_server_identity();
