-- Administrator-only preparation, AFTER momentum-unified-bootstrap.sql.
-- Provision the login/password outside version control before running this file.
BEGIN;
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '30s';
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
