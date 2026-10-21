-- Administrator only, on each NEW dedicated Momentum database.
-- Create the databases and the two login passwords outside version control first.
-- Refuse defaultdb or any other existing application database.
BEGIN;
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '30s';
DO $$
DECLARE
    target TEXT := current_database();
    runtime TEXT;
BEGIN
    IF target NOT IN ('momentum_sessions', 'momentum_results') THEN
        RAISE EXCEPTION 'Bootstrap requires a dedicated Momentum database';
    END IF;
    runtime := target || '_writer';
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = runtime) THEN
        RAISE EXCEPTION 'Provision the dedicated runtime login first';
    END IF;
    IF EXISTS (SELECT FROM pg_roles WHERE rolname = runtime
        AND (rolsuper OR rolcreaterole OR rolcreatedb OR rolbypassrls))
        OR EXISTS (SELECT FROM pg_auth_members m JOIN pg_roles r ON r.oid=m.member
                   WHERE r.rolname=runtime) THEN
        RAISE EXCEPTION 'Runtime role must have no administrative or inherited rights';
    END IF;
    EXECUTE format('REVOKE ALL ON DATABASE %I FROM PUBLIC', target);
    EXECUTE format('REVOKE ALL ON DATABASE %I FROM %I', target, runtime);
    EXECUTE format('GRANT CONNECT ON DATABASE %I TO %I', target, runtime);
    EXECUTE format('GRANT CONNECT, CREATE ON DATABASE %I TO database_migrator', target);
    REVOKE CREATE ON SCHEMA public FROM PUBLIC;
    EXECUTE format('REVOKE ALL ON SCHEMA public FROM %I', runtime);
    EXECUTE format('ALTER ROLE %I NOINHERIT CONNECTION LIMIT 2', runtime);
    EXECUTE format('ALTER ROLE %I IN DATABASE %I SET search_path = momentum, pg_catalog', runtime, target);
    EXECUTE format('ALTER ROLE %I IN DATABASE %I SET statement_timeout = %L', runtime, target, '30s');
    EXECUTE format('ALTER ROLE %I IN DATABASE %I SET idle_in_transaction_session_timeout = %L', runtime, target, '30s');
    IF has_database_privilege(runtime, target, 'CREATE')
        OR has_database_privilege(runtime, target, 'TEMP')
        OR has_schema_privilege(runtime, 'public', 'CREATE') THEN
        RAISE EXCEPTION 'Runtime must not own the database or have CREATE/TEMP';
    END IF;
END $$;
COMMIT;
