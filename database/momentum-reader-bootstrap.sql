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
END $$;
COMMIT;
