-- Run as database_migrator AFTER the administrator database bootstrap.
-- Aiven's administrator cannot SET ROLE to existing isolated migration identities.
BEGIN;
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '30s';
DO $$ BEGIN
    IF current_database() NOT IN ('momentum_sessions', 'momentum_results')
        OR current_user <> 'database_migrator' THEN
        RAISE EXCEPTION 'Migration bootstrap requires its dedicated database and identity';
    END IF;
END $$;
CREATE SCHEMA IF NOT EXISTS liquibase AUTHORIZATION database_migrator;
REVOKE ALL ON SCHEMA liquibase FROM PUBLIC;
COMMIT;
