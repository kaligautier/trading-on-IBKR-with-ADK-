-- Administrator only, once in the dedicated momentum database.
-- Existing isolated runtime logins may be reused; passwords stay outside SQL.
BEGIN;
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '30s';
DO $$
DECLARE
    runtime TEXT;
    target_schema TEXT;
BEGIN
    IF current_database() <> 'momentum' THEN
        RAISE EXCEPTION 'Bootstrap requires the momentum database';
    END IF;
    REVOKE ALL ON DATABASE momentum FROM PUBLIC;
    GRANT CONNECT, CREATE ON DATABASE momentum TO database_migrator;
    REVOKE CREATE ON SCHEMA public FROM PUBLIC;
    FOREACH runtime IN ARRAY ARRAY['momentum_sessions_writer', 'momentum_results_writer'] LOOP
        IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname=runtime)
            OR EXISTS (SELECT FROM pg_roles WHERE rolname=runtime
                       AND (rolsuper OR rolcreatedb OR rolcreaterole OR rolbypassrls))
            OR EXISTS (SELECT FROM pg_auth_members m JOIN pg_roles r ON r.oid=m.member
                       WHERE r.rolname=runtime) THEN
            RAISE EXCEPTION 'Provision non-administrative runtime logins without memberships';
        END IF;
        target_schema := CASE WHEN runtime='momentum_sessions_writer' THEN '_sessions' ELSE '_analysis' END;
        EXECUTE format('REVOKE ALL ON DATABASE momentum FROM %I', runtime);
        EXECUTE format('GRANT CONNECT ON DATABASE momentum TO %I', runtime);
        EXECUTE format('REVOKE ALL ON SCHEMA public FROM %I', runtime);
        EXECUTE format('ALTER ROLE %I NOINHERIT CONNECTION LIMIT 2', runtime);
        EXECUTE format('ALTER ROLE %I IN DATABASE momentum SET search_path = %I, pg_catalog', runtime, target_schema);
        EXECUTE format('ALTER ROLE %I IN DATABASE momentum SET statement_timeout = %L', runtime, '30s');
        EXECUTE format('ALTER ROLE %I IN DATABASE momentum SET idle_in_transaction_session_timeout = %L', runtime, '30s');
        IF has_database_privilege(runtime, current_database(), 'CREATE')
            OR has_database_privilege(runtime, current_database(), 'TEMP')
            OR has_schema_privilege(runtime, 'public', 'CREATE') THEN
            RAISE EXCEPTION 'Runtime must not own the database or have CREATE/TEMP';
        END IF;
    END LOOP;
END $$;
COMMIT;
