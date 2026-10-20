--liquibase formatted sql

--changeset deep-copy:adk-sessions-001 dbms:postgresql
--comment: JSON session schema and index required by google-adk 2.6.1 (schema v1).
CREATE SCHEMA _sessions AUTHORIZATION database_migrator;
REVOKE ALL ON SCHEMA _sessions FROM PUBLIC;
GRANT USAGE ON SCHEMA _sessions TO ${sessionRole};
CREATE TABLE _sessions.adk_internal_metadata (
    key VARCHAR(128) PRIMARY KEY,
    value VARCHAR(256) NOT NULL
);
INSERT INTO _sessions.adk_internal_metadata VALUES ('schema_version', '1');
CREATE TABLE _sessions.app_states (
    app_name VARCHAR(128) PRIMARY KEY,
    state JSONB NOT NULL,
    update_time TIMESTAMP WITHOUT TIME ZONE NOT NULL
);
CREATE TABLE _sessions.user_states (
    app_name VARCHAR(128) NOT NULL,
    user_id VARCHAR(128) NOT NULL,
    state JSONB NOT NULL,
    update_time TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    PRIMARY KEY (app_name, user_id)
);
CREATE TABLE _sessions.sessions (
    app_name VARCHAR(128) NOT NULL,
    user_id VARCHAR(128) NOT NULL,
    id VARCHAR(128) NOT NULL,
    state JSONB NOT NULL,
    create_time TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    update_time TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    PRIMARY KEY (app_name, user_id, id)
);
CREATE TABLE _sessions.events (
    id VARCHAR(128) NOT NULL,
    app_name VARCHAR(128) NOT NULL,
    user_id VARCHAR(128) NOT NULL,
    session_id VARCHAR(128) NOT NULL,
    invocation_id VARCHAR(256) NOT NULL,
    timestamp TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    event_data JSONB,
    PRIMARY KEY (id, app_name, user_id, session_id),
    FOREIGN KEY (app_name, user_id, session_id)
        REFERENCES _sessions.sessions(app_name, user_id, id) ON DELETE CASCADE
);
CREATE INDEX idx_events_app_user_session_ts ON _sessions.events
    (app_name, user_id, session_id, timestamp DESC);
REVOKE ALL ON _sessions.adk_internal_metadata, _sessions.app_states,
    _sessions.user_states, _sessions.sessions, _sessions.events FROM PUBLIC;
GRANT SELECT ON _sessions.adk_internal_metadata TO ${sessionRole};
GRANT SELECT, INSERT, UPDATE, DELETE ON _sessions.app_states,
    _sessions.user_states, _sessions.sessions, _sessions.events TO ${sessionRole};

--rollback DROP TABLE _sessions.events;
--rollback DROP TABLE _sessions.sessions;
--rollback DROP TABLE _sessions.user_states;
--rollback DROP TABLE _sessions.app_states;
--rollback DROP TABLE _sessions.adk_internal_metadata;
--rollback DROP SCHEMA _sessions;
