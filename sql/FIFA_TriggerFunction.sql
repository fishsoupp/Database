-- (1) PLAYERS
CREATE OR REPLACE FUNCTION log_admin_action_players()
RETURNS TRIGGER AS $$
DECLARE
    admin_id INT;
    activity_type TEXT;
BEGIN

    -- Fetch the admin_id set in the custom configuration parameter
    admin_id := current_setting('myapp.admin_id', true)::INT;
    -- Map the TG_OP operation to the allowed values in the check constraint
    IF TG_OP = 'INSERT' THEN
        activity_type := 'create';
    ELSIF TG_OP = 'UPDATE' THEN
        activity_type := 'update';
    ELSIF TG_OP = 'DELETE' THEN
        activity_type := 'delete';
    ELSE
        RAISE EXCEPTION 'Unknown operation type: %', TG_OP;
    END IF;

    -- Insert log into admin_log table
    INSERT INTO admin_log (admin_id, activity_type, table_name, record_id, activity_timestamp)
    VALUES (admin_id, activity_type, TG_TABLE_NAME, COALESCE(NEW.player_id::TEXT, OLD.player_id::TEXT), CURRENT_TIMESTAMP);

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE TRIGGER log_player_action
AFTER INSERT OR UPDATE OR DELETE ON players
FOR EACH ROW EXECUTE FUNCTION log_admin_action_players();

------------------------------------------------------------------------------------------------------

-- (2) MATCHES
CREATE OR REPLACE FUNCTION log_admin_action_matches()
RETURNS TRIGGER AS $$
DECLARE
    admin_id INT;
    activity_type TEXT;
BEGIN

    -- Fetch the admin_id set in the custom configuration parameter
    admin_id := current_setting('myapp.admin_id', true)::INT;
    -- Map the TG_OP operation to the allowed values in the check constraint
    IF TG_OP = 'INSERT' THEN
        activity_type := 'create';
    ELSIF TG_OP = 'UPDATE' THEN
        activity_type := 'update';
    ELSIF TG_OP = 'DELETE' THEN
        activity_type := 'delete';
    ELSE
        RAISE EXCEPTION 'Unknown operation type: %', TG_OP;
    END IF;

    -- Insert log into admin_log table
    INSERT INTO admin_log (admin_id, activity_type, table_name, record_id, activity_timestamp)
    VALUES (admin_id, activity_type, TG_TABLE_NAME, COALESCE(NEW.match_id::TEXT, OLD.match_id::TEXT), CURRENT_TIMESTAMP);

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE TRIGGER log_match_action
AFTER INSERT OR UPDATE OR DELETE ON matches
FOR EACH ROW EXECUTE FUNCTION log_admin_action_matches();

------------------------------------------------------------------------------------------------------

-- (3) GOALS

CREATE OR REPLACE FUNCTION log_admin_action_goals()
RETURNS TRIGGER AS $$
DECLARE
    admin_id INT;
    activity_type TEXT;
BEGIN

    -- Fetch the admin_id set in the custom configuration parameter
    admin_id := current_setting('myapp.admin_id', true)::INT;
    -- Map the TG_OP operation to the allowed values in the check constraint
    IF TG_OP = 'INSERT' THEN
        activity_type := 'create';
    ELSIF TG_OP = 'UPDATE' THEN
        activity_type := 'update';
    ELSIF TG_OP = 'DELETE' THEN
        activity_type := 'delete';
    ELSE
        RAISE EXCEPTION 'Unknown operation type: %', TG_OP;
    END IF;

    -- Insert log into admin_log table
    INSERT INTO admin_log (admin_id, activity_type, table_name, record_id, activity_timestamp)
    VALUES (admin_id, activity_type, TG_TABLE_NAME, COALESCE(NEW.goal_id::TEXT, OLD.goal_id::TEXT), CURRENT_TIMESTAMP);

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE TRIGGER log_goal_action
AFTER INSERT OR UPDATE OR DELETE ON goals
FOR EACH ROW EXECUTE FUNCTION log_admin_action_goals();


------------------------------------------------------------------------------------------------------

-- (4) TOURNAMENTS

CREATE OR REPLACE FUNCTION log_admin_action_tournaments()
RETURNS TRIGGER AS $$
DECLARE
    admin_id INT;
    activity_type TEXT;
BEGIN

    -- Fetch the admin_id set in the custom configuration parameter
    admin_id := current_setting('myapp.admin_id', true)::INT;
    -- Map the TG_OP operation to the allowed values in the check constraint
    IF TG_OP = 'INSERT' THEN
        activity_type := 'create';
    ELSIF TG_OP = 'UPDATE' THEN
        activity_type := 'update';
    ELSIF TG_OP = 'DELETE' THEN
        activity_type := 'delete';
    ELSE
        RAISE EXCEPTION 'Unknown operation type: %', TG_OP;
    END IF;

    -- Insert log into admin_log table
    INSERT INTO admin_log (admin_id, activity_type, table_name, record_id, activity_timestamp)
    VALUES (admin_id, activity_type, TG_TABLE_NAME, COALESCE(NEW.tournament_id::TEXT, OLD.tournament_id::TEXT), CURRENT_TIMESTAMP);

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE TRIGGER log_tournament_action
AFTER INSERT OR UPDATE OR DELETE ON tournaments
FOR EACH ROW EXECUTE FUNCTION log_admin_action_tournaments();