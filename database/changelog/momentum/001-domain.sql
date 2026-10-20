--liquibase formatted sql

--changeset deep-copy:momentum-domain-001 dbms:postgresql
CREATE SCHEMA _analysis AUTHORIZATION database_migrator;
REVOKE ALL ON SCHEMA _analysis FROM PUBLIC;
GRANT USAGE ON SCHEMA _analysis TO momentum_writer;
--rollback DROP SCHEMA _analysis;
