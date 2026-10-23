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
    FOREACH runtime IN ARRAY ARRAY['momentum_sessions_writer', 'momentum_results_writer', 'momentum_results_reader'] LOOP
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
DO $$ BEGIN
    IF current_database() <> 'momentum' THEN
        RAISE EXCEPTION 'Reader bootstrap requires the momentum database';
    END IF;
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='momentum_results_reader' AND rolcanlogin)
        OR EXISTS (SELECT FROM pg_roles WHERE rolname='momentum_results_reader'
                   AND (rolsuper OR rolcreatedb OR rolcreaterole OR rolbypassrls OR rolreplication))
        OR EXISTS (SELECT FROM pg_auth_members m JOIN pg_roles r ON r.oid=m.member
                   WHERE r.rolname='momentum_results_reader') THEN
        RAISE EXCEPTION 'Provision a non-administrative reader login without memberships';
    END IF;
    IF EXISTS (SELECT FROM pg_database
               WHERE datallowconn AND datname <> 'momentum'
               AND NOT (datname = 'template1' AND datistemplate
                        AND pg_get_userbyid(datdba) = 'postgres'
                        AND coalesce(current_setting('momentum_reader.template1_pg_hba_denied', true), '') = 'on')
               AND has_database_privilege('momentum_results_reader', oid, 'CONNECT')) THEN
        RAISE EXCEPTION 'Remove effective reader CONNECT on non-Momentum databases before bootstrap';
    END IF;
    REVOKE ALL ON DATABASE momentum FROM momentum_results_reader;
    GRANT CONNECT ON DATABASE momentum TO momentum_results_reader;
    REVOKE ALL ON SCHEMA public FROM momentum_results_reader;
    ALTER ROLE momentum_results_reader NOINHERIT CONNECTION LIMIT 2;
    ALTER ROLE momentum_results_reader IN DATABASE momentum SET search_path = pg_catalog, _analysis;
    ALTER ROLE momentum_results_reader IN DATABASE momentum SET default_transaction_read_only = on;
    ALTER ROLE momentum_results_reader IN DATABASE momentum SET statement_timeout = '10s';
    ALTER ROLE momentum_results_reader IN DATABASE momentum SET idle_in_transaction_session_timeout = '10s';
    IF has_database_privilege('momentum_results_reader', 'momentum', 'CREATE')
        OR has_database_privilege('momentum_results_reader', 'momentum', 'TEMP')
        OR has_schema_privilege('momentum_results_reader', 'public', 'CREATE') THEN
        RAISE EXCEPTION 'Reader must not own the database or inherit CREATE/TEMP';
    END IF;
    IF EXISTS (
        SELECT FROM pg_namespace n
        WHERE left(n.nspname, 3) <> 'pg_' AND n.nspname <> 'information_schema'
          AND (has_schema_privilege('momentum_results_reader', n.oid, 'CREATE,USAGE WITH GRANT OPTION')
               OR (n.nspname IN ('_sessions', 'liquibase')
                   AND has_schema_privilege('momentum_results_reader', n.oid, 'USAGE')))
    ) OR EXISTS (
        SELECT FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
        WHERE left(n.nspname, 3) <> 'pg_' AND n.nspname <> 'information_schema'
          AND c.relkind IN ('r','p','v','m','f') AND (
            has_table_privilege('momentum_results_reader', c.oid,
                                'INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER,SELECT WITH GRANT OPTION')
            OR has_any_column_privilege('momentum_results_reader', c.oid,
                                        'INSERT,UPDATE,REFERENCES,SELECT WITH GRANT OPTION')
            OR (NOT (n.nspname='_analysis' AND c.relname IN (
                'analysis_results','technical_indicators','fundamentals',
                'sentiment_results','sentiment_items','news_results','news_items',
                'research_plans','trader_proposals','portfolio_decisions',
                'debate_arguments','run_stats')) AND (
                has_table_privilege('momentum_results_reader', c.oid, 'SELECT')
                OR has_any_column_privilege('momentum_results_reader', c.oid, 'SELECT')
            ))
        )
    ) THEN
        RAISE EXCEPTION 'Reader has unexpected effective storage privileges or ownership';
    END IF;
END $$;
COMMIT;
