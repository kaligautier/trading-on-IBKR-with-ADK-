-- Administrator only; create the login/password outside version control first.
-- Shared PUBLIC permissions must be audited/corrected before enabling this role.
BEGIN;
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '30s';
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'momentum_writer') THEN
        RAISE EXCEPTION 'Create the momentum_writer login before bootstrap';
    END IF;
    IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'momentum_writer'
        AND (rolsuper OR rolcreaterole OR rolcreatedb OR rolbypassrls)) THEN
        RAISE EXCEPTION 'momentum_writer must not have administrative attributes';
    END IF;
    IF EXISTS (SELECT FROM pg_auth_members m JOIN pg_roles r ON r.oid = m.member
        WHERE r.rolname = 'momentum_writer') THEN
        RAISE EXCEPTION 'momentum_writer must not inherit or assume another role';
    END IF;
    IF has_database_privilege('momentum_writer', current_database(), 'CREATE')
        OR has_database_privilege('momentum_writer', current_database(), 'TEMP')
        OR has_schema_privilege('momentum_writer', 'public', 'CREATE') THEN
        RAISE EXCEPTION 'Audit effective PUBLIC/direct privileges before bootstrap';
    END IF;
END $$;
ALTER ROLE momentum_writer NOINHERIT CONNECTION LIMIT 4;
ALTER ROLE momentum_writer SET search_path = momentum, pg_catalog;
ALTER ROLE momentum_writer SET statement_timeout = '30s';
ALTER ROLE momentum_writer SET idle_in_transaction_session_timeout = '30s';
COMMIT;
