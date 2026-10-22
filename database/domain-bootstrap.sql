-- Supply domain from the supported allowlist and run in that database as administrator.
BEGIN;
DO $$ BEGIN
    IF current_database() NOT IN ('market_scanner', 'momentum') THEN
        RAISE EXCEPTION 'Unsupported application database';
    END IF;
END $$;
REVOKE ALL ON DATABASE :"domain" FROM PUBLIC;
GRANT CONNECT, CREATE ON DATABASE :"domain" TO database_migrator;
REVOKE ALL ON SCHEMA public FROM PUBLIC;
CREATE SCHEMA liquibase AUTHORIZATION database_migrator;
REVOKE ALL ON SCHEMA liquibase FROM PUBLIC;
DO $$
DECLARE runtime TEXT;
BEGIN
    FOREACH runtime IN ARRAY CASE current_database()
        WHEN 'market_scanner' THEN ARRAY['market_scanner_writer', 'market_scanner_reader']
        ELSE ARRAY['momentum_sessions_writer', 'momentum_results_writer'] END LOOP
        EXECUTE format('GRANT CONNECT ON DATABASE %I TO %I', current_database(), runtime);
        EXECUTE format('ALTER ROLE %I IN DATABASE %I SET search_path = %I, pg_catalog',
            runtime, current_database(), CASE WHEN runtime='momentum_sessions_writer'
            THEN '_sessions' ELSE '_analysis' END);
        EXECUTE format('ALTER ROLE %I IN DATABASE %I SET statement_timeout = %L', runtime, current_database(), '30s');
        EXECUTE format('ALTER ROLE %I IN DATABASE %I SET idle_in_transaction_session_timeout = %L', runtime, current_database(), '30s');
    END LOOP;
END $$;
COMMIT;
