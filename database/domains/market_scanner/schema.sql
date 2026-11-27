
\restrict deepcopy

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

CREATE DATABASE market_scanner WITH TEMPLATE = template0 ENCODING = 'UTF8' LOCALE_PROVIDER = libc LOCALE = 'en_US.utf8';

ALTER DATABASE market_scanner OWNER TO postgres;

\unrestrict deepcopy
\connect market_scanner
\restrict deepcopy

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

ALTER ROLE market_scanner_writer IN DATABASE market_scanner SET search_path TO '_analysis', 'pg_catalog';
ALTER ROLE market_scanner_writer IN DATABASE market_scanner SET statement_timeout TO '30s';
ALTER ROLE market_scanner_writer IN DATABASE market_scanner SET idle_in_transaction_session_timeout TO '30s';
ALTER ROLE market_scanner_reader IN DATABASE market_scanner SET search_path TO '_analysis', 'pg_catalog';
ALTER ROLE market_scanner_reader IN DATABASE market_scanner SET statement_timeout TO '30s';
ALTER ROLE market_scanner_reader IN DATABASE market_scanner SET idle_in_transaction_session_timeout TO '30s';

\unrestrict deepcopy
\connect market_scanner
\restrict deepcopy

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

CREATE SCHEMA _analysis;

ALTER SCHEMA _analysis OWNER TO database_migrator;

CREATE SCHEMA _sessions;

ALTER SCHEMA _sessions OWNER TO database_migrator;

CREATE SCHEMA liquibase;

ALTER SCHEMA liquibase OWNER TO database_migrator;

SET default_tablespace = '';

SET default_table_access_method = heap;

CREATE TABLE _analysis.market_scan_assets (
    id uuid NOT NULL,
    scan_id uuid NOT NULL,
    name text NOT NULL,
    symbol text NOT NULL,
    kind text DEFAULT 'market'::text NOT NULL,
    unit text,
    value numeric NOT NULL,
    trend text,
    analysis text NOT NULL,
    context text NOT NULL
);

ALTER TABLE _analysis.market_scan_assets OWNER TO database_migrator;

CREATE TABLE _analysis.market_scan_horizons (
    id uuid NOT NULL,
    asset_id uuid NOT NULL,
    horizon text NOT NULL,
    change_pct double precision NOT NULL,
    ref_price numeric NOT NULL,
    trend text NOT NULL
);

ALTER TABLE _analysis.market_scan_horizons OWNER TO database_migrator;

CREATE TABLE _analysis.market_scans (
    id uuid NOT NULL,
    scan_date date NOT NULL,
    session_id text NOT NULL,
    regime text NOT NULL,
    summary text NOT NULL,
    recommendation text,
    data_quality jsonb,
    report jsonb,
    created_at timestamp with time zone NOT NULL
);

ALTER TABLE _analysis.market_scans OWNER TO database_migrator;

CREATE TABLE _sessions.adk_internal_metadata (
    key character varying(128) NOT NULL,
    value character varying(256) NOT NULL
);

ALTER TABLE _sessions.adk_internal_metadata OWNER TO database_migrator;

CREATE TABLE _sessions.app_states (
    app_name character varying(128) NOT NULL,
    state jsonb NOT NULL,
    update_time timestamp without time zone NOT NULL
);

ALTER TABLE _sessions.app_states OWNER TO database_migrator;

CREATE TABLE _sessions.events (
    id character varying(128) NOT NULL,
    app_name character varying(128) NOT NULL,
    user_id character varying(128) NOT NULL,
    session_id character varying(128) NOT NULL,
    invocation_id character varying(256) NOT NULL,
    "timestamp" timestamp without time zone NOT NULL,
    event_data jsonb
);

ALTER TABLE _sessions.events OWNER TO database_migrator;

CREATE TABLE _sessions.sessions (
    app_name character varying(128) NOT NULL,
    user_id character varying(128) NOT NULL,
    id character varying(128) NOT NULL,
    state jsonb NOT NULL,
    create_time timestamp without time zone NOT NULL,
    update_time timestamp without time zone NOT NULL
);

ALTER TABLE _sessions.sessions OWNER TO database_migrator;

CREATE TABLE _sessions.user_states (
    app_name character varying(128) NOT NULL,
    user_id character varying(128) NOT NULL,
    state jsonb NOT NULL,
    update_time timestamp without time zone NOT NULL
);

ALTER TABLE _sessions.user_states OWNER TO database_migrator;

CREATE TABLE liquibase.databasechangelog (
    id character varying(255) NOT NULL,
    author character varying(255) NOT NULL,
    filename character varying(255) NOT NULL,
    dateexecuted timestamp without time zone NOT NULL,
    orderexecuted integer NOT NULL,
    exectype character varying(10) NOT NULL,
    md5sum character varying(35),
    description character varying(255),
    comments character varying(255),
    tag character varying(255),
    liquibase character varying(20),
    contexts character varying(255),
    labels character varying(255),
    deployment_id character varying(10)
);

ALTER TABLE liquibase.databasechangelog OWNER TO database_migrator;

CREATE TABLE liquibase.databasechangeloglock (
    id integer NOT NULL,
    locked boolean NOT NULL,
    lockgranted timestamp without time zone,
    lockedby character varying(255)
);

ALTER TABLE liquibase.databasechangeloglock OWNER TO database_migrator;

ALTER TABLE ONLY _analysis.market_scan_assets
    ADD CONSTRAINT market_scan_assets_pkey PRIMARY KEY (id);

ALTER TABLE ONLY _analysis.market_scan_horizons
    ADD CONSTRAINT market_scan_horizons_pkey PRIMARY KEY (id);

ALTER TABLE ONLY _analysis.market_scans
    ADD CONSTRAINT market_scans_pkey PRIMARY KEY (id);

ALTER TABLE ONLY _sessions.adk_internal_metadata
    ADD CONSTRAINT adk_internal_metadata_pkey PRIMARY KEY (key);

ALTER TABLE ONLY _sessions.app_states
    ADD CONSTRAINT app_states_pkey PRIMARY KEY (app_name);

ALTER TABLE ONLY _sessions.events
    ADD CONSTRAINT events_pkey PRIMARY KEY (id, app_name, user_id, session_id);

ALTER TABLE ONLY _sessions.sessions
    ADD CONSTRAINT sessions_pkey PRIMARY KEY (app_name, user_id, id);

ALTER TABLE ONLY _sessions.user_states
    ADD CONSTRAINT user_states_pkey PRIMARY KEY (app_name, user_id);

ALTER TABLE ONLY liquibase.databasechangeloglock
    ADD CONSTRAINT databasechangeloglock_pkey PRIMARY KEY (id);

CREATE INDEX market_scan_assets_scan_id_idx ON _analysis.market_scan_assets USING btree (scan_id);

CREATE INDEX market_scan_horizons_asset_id_idx ON _analysis.market_scan_horizons USING btree (asset_id);

CREATE INDEX market_scans_created_at_idx ON _analysis.market_scans USING btree (created_at DESC);

CREATE INDEX idx_events_app_user_session_ts ON _sessions.events USING btree (app_name, user_id, session_id, "timestamp" DESC);

ALTER TABLE ONLY _analysis.market_scan_assets
    ADD CONSTRAINT market_scan_assets_scan_id_fkey FOREIGN KEY (scan_id) REFERENCES _analysis.market_scans(id);

ALTER TABLE ONLY _analysis.market_scan_horizons
    ADD CONSTRAINT market_scan_horizons_asset_id_fkey FOREIGN KEY (asset_id) REFERENCES _analysis.market_scan_assets(id);

ALTER TABLE ONLY _sessions.events
    ADD CONSTRAINT events_app_name_user_id_session_id_fkey FOREIGN KEY (app_name, user_id, session_id) REFERENCES _sessions.sessions(app_name, user_id, id) ON DELETE CASCADE;

REVOKE CONNECT,TEMPORARY ON DATABASE market_scanner FROM PUBLIC;
GRANT CREATE,CONNECT ON DATABASE market_scanner TO database_migrator;
GRANT CONNECT ON DATABASE market_scanner TO market_scanner_writer;
GRANT CONNECT ON DATABASE market_scanner TO market_scanner_reader;

GRANT USAGE ON SCHEMA _analysis TO market_scanner_writer;
GRANT USAGE ON SCHEMA _analysis TO market_scanner_reader;

GRANT USAGE ON SCHEMA _sessions TO market_scanner_writer;

REVOKE USAGE ON SCHEMA public FROM PUBLIC;

GRANT INSERT ON TABLE _analysis.market_scan_assets TO market_scanner_writer;
GRANT SELECT ON TABLE _analysis.market_scan_assets TO market_scanner_reader;

GRANT INSERT ON TABLE _analysis.market_scan_horizons TO market_scanner_writer;
GRANT SELECT ON TABLE _analysis.market_scan_horizons TO market_scanner_reader;

GRANT INSERT ON TABLE _analysis.market_scans TO market_scanner_writer;
GRANT SELECT ON TABLE _analysis.market_scans TO market_scanner_reader;

GRANT SELECT ON TABLE _sessions.adk_internal_metadata TO market_scanner_writer;

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE _sessions.app_states TO market_scanner_writer;

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE _sessions.events TO market_scanner_writer;

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE _sessions.sessions TO market_scanner_writer;

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE _sessions.user_states TO market_scanner_writer;

\unrestrict deepcopy

