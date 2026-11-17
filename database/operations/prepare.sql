-- Run as database_migrator in the application database after administrator bootstrap.
BEGIN;
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '30s';
DO $$ BEGIN
    IF current_user <> 'database_migrator'
        OR current_database() NOT IN ('market_scanner', 'momentum') THEN
        RAISE EXCEPTION 'Use database_migrator in its explicit application database';
    END IF;
END $$;
CREATE SCHEMA IF NOT EXISTS liquibase AUTHORIZATION database_migrator;
REVOKE ALL ON SCHEMA liquibase FROM PUBLIC;
COMMIT;
