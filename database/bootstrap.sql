-- Administrator only, once, after creating the three login roles.
-- Runtime services never receive this credential.
BEGIN;
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '30s';
DO $$ BEGIN
    EXECUTE format('GRANT CREATE ON DATABASE %I TO database_migrator', current_database());
END $$;
SET LOCAL ROLE database_migrator;
CREATE SCHEMA liquibase AUTHORIZATION database_migrator;
REVOKE ALL ON SCHEMA liquibase FROM PUBLIC;
RESET ROLE;
ALTER ROLE database_migrator CONNECTION LIMIT 1;
ALTER ROLE market_scanner_writer CONNECTION LIMIT 2;
ALTER ROLE market_scanner_reader CONNECTION LIMIT 4;
ALTER ROLE market_scanner_writer SET search_path = market_scanner, pg_catalog;
ALTER ROLE market_scanner_reader SET search_path = market_scanner, pg_catalog;
ALTER ROLE market_scanner_writer SET statement_timeout = '30s';
ALTER ROLE market_scanner_reader SET statement_timeout = '30s';
ALTER ROLE market_scanner_writer SET idle_in_transaction_session_timeout = '30s';
ALTER ROLE market_scanner_reader SET idle_in_transaction_session_timeout = '30s';
COMMIT;
