-- Run as the database administrator in the dedicated market_scanner database.
-- Runtime passwords are retained and never supplied in this script.
BEGIN;
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '30s';
DO $$
DECLARE runtime TEXT;
BEGIN
    IF current_database() <> 'market_scanner' THEN
        RAISE EXCEPTION 'Scanner bootstrap requires the market_scanner database';
    END IF;
    REVOKE ALL ON DATABASE market_scanner FROM PUBLIC;
    GRANT CONNECT, CREATE ON DATABASE market_scanner TO database_migrator;
    REVOKE ALL ON SCHEMA public FROM PUBLIC;
    FOREACH runtime IN ARRAY ARRAY['market_scanner_writer', 'market_scanner_reader'] LOOP
        IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname=runtime)
            OR EXISTS (SELECT FROM pg_roles WHERE rolname=runtime
                       AND (rolsuper OR rolcreatedb OR rolcreaterole OR rolbypassrls))
            OR EXISTS (SELECT FROM pg_auth_members m JOIN pg_roles r ON r.oid=m.member
                       WHERE r.rolname=runtime) THEN
            RAISE EXCEPTION 'Runtime roles must exist without administrative rights or memberships';
        END IF;
        EXECUTE format('REVOKE ALL ON DATABASE market_scanner FROM %I', runtime);
        EXECUTE format('GRANT CONNECT ON DATABASE market_scanner TO %I', runtime);
        EXECUTE format('REVOKE ALL ON SCHEMA public FROM %I', runtime);
        EXECUTE format('ALTER ROLE %I NOINHERIT CONNECTION LIMIT %s', runtime,
                       CASE WHEN runtime='market_scanner_writer' THEN 4 ELSE 2 END);
        EXECUTE format('ALTER ROLE %I IN DATABASE market_scanner SET search_path = _analysis, pg_catalog', runtime);
        EXECUTE format('ALTER ROLE %I IN DATABASE market_scanner SET statement_timeout = %L', runtime, '30s');
        EXECUTE format('ALTER ROLE %I IN DATABASE market_scanner SET idle_in_transaction_session_timeout = %L', runtime, '30s');
        IF has_database_privilege(runtime, current_database(), 'CREATE')
            OR has_database_privilege(runtime, current_database(), 'TEMP')
            OR has_schema_privilege(runtime, 'public', 'CREATE') THEN
            RAISE EXCEPTION 'Runtime must not own the database or have CREATE/TEMP';
        END IF;
    END LOOP;
END $$;
COMMIT;
