-- Disposable CI/local PostgreSQL only: never run against Aiven.
-- Creates the logins that the Aiven administrator provisions out of band, with a
-- test-only password (psql variable `password`). Each domain's bootstrap.sql then
-- applies the real limits.
\set ON_ERROR_STOP on
REVOKE CONNECT ON DATABASE postgres, template1 FROM PUBLIC;
CREATE ROLE database_migrator LOGIN NOINHERIT PASSWORD :'password' CONNECTION LIMIT 2;
CREATE ROLE market_scanner_writer LOGIN NOINHERIT PASSWORD :'password' CONNECTION LIMIT 4;
CREATE ROLE market_scanner_reader LOGIN NOINHERIT PASSWORD :'password' CONNECTION LIMIT 4;
CREATE ROLE momentum_sessions_writer LOGIN NOINHERIT PASSWORD :'password' CONNECTION LIMIT 4;
CREATE ROLE momentum_results_writer LOGIN NOINHERIT PASSWORD :'password' CONNECTION LIMIT 4;
CREATE ROLE momentum_results_reader LOGIN NOINHERIT PASSWORD :'password' CONNECTION LIMIT 2;
