-- Administrator only, after reviewing current_database() and the affected roles.
-- Preserve TEMP for existing logins; remove its implicit grant to the new worker.
-- This changes only the currently connected database, never the LiteLLM database.
BEGIN;
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '30s';
DO $$
DECLARE existing_login RECORD;
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'momentum_writer') THEN
        RAISE EXCEPTION 'Create momentum_writer before correcting PUBLIC grants';
    END IF;
    FOR existing_login IN SELECT rolname FROM pg_roles
        WHERE rolcanlogin AND rolname <> 'momentum_writer'
    LOOP
        IF has_database_privilege(existing_login.rolname, current_database(), 'TEMP')
        THEN
            EXECUTE format('GRANT TEMPORARY ON DATABASE %I TO %I',
                current_database(), existing_login.rolname);
        END IF;
    END LOOP;
    EXECUTE format('REVOKE TEMPORARY ON DATABASE %I FROM PUBLIC',
        current_database());
    EXECUTE format('REVOKE TEMPORARY, CREATE ON DATABASE %I FROM momentum_writer',
        current_database());
END $$;
COMMIT;
