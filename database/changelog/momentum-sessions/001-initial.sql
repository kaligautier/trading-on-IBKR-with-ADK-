--liquibase formatted sql

--changeset deep-copy:momentum-sessions-001 dbms:postgresql
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:1 SELECT CASE WHEN current_database() = 'momentum_sessions' THEN 1 ELSE 0 END;
--comment: JSON session schema and index required by google-adk 2.6.1 (schema v1).
CREATE SCHEMA momentum AUTHORIZATION database_migrator;
REVOKE ALL ON SCHEMA momentum FROM PUBLIC;
GRANT USAGE ON SCHEMA momentum TO momentum_sessions_writer;

CREATE TABLE momentum.adk_internal_metadata (
    key VARCHAR(128) PRIMARY KEY,
    value VARCHAR(256) NOT NULL
);
INSERT INTO momentum.adk_internal_metadata VALUES ('schema_version', '1');
CREATE TABLE momentum.app_states (
    app_name VARCHAR(128) PRIMARY KEY,
    state JSONB NOT NULL,
    update_time TIMESTAMP WITHOUT TIME ZONE NOT NULL
);
CREATE TABLE momentum.user_states (
    app_name VARCHAR(128) NOT NULL,
    user_id VARCHAR(128) NOT NULL,
    state JSONB NOT NULL,
    update_time TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    PRIMARY KEY (app_name, user_id)
);
CREATE TABLE momentum.sessions (
    app_name VARCHAR(128) NOT NULL,
    user_id VARCHAR(128) NOT NULL,
    id VARCHAR(128) NOT NULL,
    state JSONB NOT NULL,
    create_time TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    update_time TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    PRIMARY KEY (app_name, user_id, id)
);
CREATE TABLE momentum.events (
    id VARCHAR(128) NOT NULL,
    app_name VARCHAR(128) NOT NULL,
    user_id VARCHAR(128) NOT NULL,
    session_id VARCHAR(128) NOT NULL,
    invocation_id VARCHAR(256) NOT NULL,
    timestamp TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    event_data JSONB,
    PRIMARY KEY (id, app_name, user_id, session_id),
    FOREIGN KEY (app_name, user_id, session_id)
        REFERENCES momentum.sessions(app_name, user_id, id) ON DELETE CASCADE
);
CREATE INDEX idx_events_app_user_session_ts ON momentum.events
    (app_name, user_id, session_id, timestamp DESC);
REVOKE ALL ON momentum.adk_internal_metadata, momentum.app_states,
    momentum.user_states, momentum.sessions, momentum.events FROM PUBLIC;
GRANT SELECT ON momentum.adk_internal_metadata TO momentum_sessions_writer;
GRANT SELECT, INSERT, UPDATE, DELETE ON momentum.app_states,
    momentum.user_states, momentum.sessions, momentum.events TO momentum_sessions_writer;

--rollback DROP TABLE momentum.events;
--rollback DROP TABLE momentum.sessions;
--rollback DROP TABLE momentum.user_states;
--rollback DROP TABLE momentum.app_states;
--rollback DROP TABLE momentum.adk_internal_metadata;
--rollback DROP SCHEMA momentum;
