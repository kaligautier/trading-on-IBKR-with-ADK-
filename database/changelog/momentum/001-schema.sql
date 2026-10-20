--liquibase formatted sql

--changeset deep-copy:momentum-001 dbms:postgresql context:@momentum
--comment: Isolate Momentum objects under the existing migration identity.
CREATE SCHEMA momentum AUTHORIZATION database_migrator;
REVOKE ALL ON SCHEMA momentum FROM PUBLIC;
GRANT USAGE ON SCHEMA momentum TO momentum_writer;

--rollback DROP SCHEMA momentum;
