-- Run as database_migrator after the administrator bootstrap.
BEGIN;
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '30s';
DO $$ BEGIN
    IF current_database() <> 'market_scanner' OR current_user <> 'database_migrator' THEN
        RAISE EXCEPTION 'Scanner migration bootstrap requires its dedicated database and identity';
    END IF;
END $$;
CREATE SCHEMA IF NOT EXISTS liquibase AUTHORIZATION database_migrator;
REVOKE ALL ON SCHEMA liquibase FROM PUBLIC;
COMMIT;
