-- psql variables domain and writer are supplied from a validated domain allowlist.
BEGIN;
REVOKE ALL ON DATABASE :"domain" FROM PUBLIC;
GRANT CONNECT, CREATE ON DATABASE :"domain" TO database_migrator;
GRANT CONNECT ON DATABASE :"domain" TO :"writer";
REVOKE ALL ON SCHEMA public FROM PUBLIC;
CREATE SCHEMA liquibase AUTHORIZATION database_migrator;
REVOKE ALL ON SCHEMA liquibase FROM PUBLIC;
ALTER ROLE :"writer" IN DATABASE :"domain" SET search_path = _analysis, pg_catalog;
ALTER ROLE :"writer" IN DATABASE :"domain" SET statement_timeout = '30s';
ALTER ROLE :"writer" IN DATABASE :"domain" SET idle_in_transaction_session_timeout = '30s';
COMMIT;
