-- Schema-only baseline captured from Aiven PostgreSQL 18.6 on 2026-10-23.
-- Run as database_migrator; contains no business data.

-- _analysis
CREATE SCHEMA _analysis;

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

CREATE TABLE _analysis.market_scan_horizons (
    id uuid NOT NULL,
    asset_id uuid NOT NULL,
    horizon text NOT NULL,
    change_pct double precision NOT NULL,
    ref_price numeric NOT NULL,
    trend text NOT NULL
);

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

ALTER TABLE ONLY _analysis.market_scan_assets
    ADD CONSTRAINT market_scan_assets_pkey PRIMARY KEY (id);

ALTER TABLE ONLY _analysis.market_scan_horizons
    ADD CONSTRAINT market_scan_horizons_pkey PRIMARY KEY (id);

ALTER TABLE ONLY _analysis.market_scans
    ADD CONSTRAINT market_scans_pkey PRIMARY KEY (id);

CREATE INDEX market_scan_assets_scan_id_idx ON _analysis.market_scan_assets USING btree (scan_id);

CREATE INDEX market_scan_horizons_asset_id_idx ON _analysis.market_scan_horizons USING btree (asset_id);

CREATE INDEX market_scans_created_at_idx ON _analysis.market_scans USING btree (created_at DESC);

ALTER TABLE ONLY _analysis.market_scan_assets
    ADD CONSTRAINT market_scan_assets_scan_id_fkey FOREIGN KEY (scan_id) REFERENCES _analysis.market_scans(id);

ALTER TABLE ONLY _analysis.market_scan_horizons
    ADD CONSTRAINT market_scan_horizons_asset_id_fkey FOREIGN KEY (asset_id) REFERENCES _analysis.market_scan_assets(id);

GRANT USAGE ON SCHEMA _analysis TO market_scanner_writer;
GRANT USAGE ON SCHEMA _analysis TO market_scanner_reader;

GRANT INSERT ON TABLE _analysis.market_scan_assets TO market_scanner_writer;
GRANT SELECT ON TABLE _analysis.market_scan_assets TO market_scanner_reader;

GRANT INSERT ON TABLE _analysis.market_scan_horizons TO market_scanner_writer;
GRANT SELECT ON TABLE _analysis.market_scan_horizons TO market_scanner_reader;

GRANT INSERT ON TABLE _analysis.market_scans TO market_scanner_writer;
GRANT SELECT ON TABLE _analysis.market_scans TO market_scanner_reader;

-- _sessions
CREATE SCHEMA _sessions;

CREATE TABLE _sessions.adk_internal_metadata (
    key character varying(128) NOT NULL,
    value character varying(256) NOT NULL
);

CREATE TABLE _sessions.app_states (
    app_name character varying(128) NOT NULL,
    state jsonb NOT NULL,
    update_time timestamp without time zone NOT NULL
);

CREATE TABLE _sessions.events (
    id character varying(128) NOT NULL,
    app_name character varying(128) NOT NULL,
    user_id character varying(128) NOT NULL,
    session_id character varying(128) NOT NULL,
    invocation_id character varying(256) NOT NULL,
    "timestamp" timestamp without time zone NOT NULL,
    event_data jsonb
);

CREATE TABLE _sessions.sessions (
    app_name character varying(128) NOT NULL,
    user_id character varying(128) NOT NULL,
    id character varying(128) NOT NULL,
    state jsonb NOT NULL,
    create_time timestamp without time zone NOT NULL,
    update_time timestamp without time zone NOT NULL
);

CREATE TABLE _sessions.user_states (
    app_name character varying(128) NOT NULL,
    user_id character varying(128) NOT NULL,
    state jsonb NOT NULL,
    update_time timestamp without time zone NOT NULL
);

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

CREATE INDEX idx_events_app_user_session_ts ON _sessions.events USING btree (app_name, user_id, session_id, "timestamp" DESC);

ALTER TABLE ONLY _sessions.events
    ADD CONSTRAINT events_app_name_user_id_session_id_fkey FOREIGN KEY (app_name, user_id, session_id) REFERENCES _sessions.sessions(app_name, user_id, id) ON DELETE CASCADE;

GRANT USAGE ON SCHEMA _sessions TO market_scanner_writer;

GRANT SELECT ON TABLE _sessions.adk_internal_metadata TO market_scanner_writer;

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE _sessions.app_states TO market_scanner_writer;

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE _sessions.events TO market_scanner_writer;

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE _sessions.sessions TO market_scanner_writer;

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE _sessions.user_states TO market_scanner_writer;

-- Required SDK metadata, not application/session data.
INSERT INTO _sessions.adk_internal_metadata (key, value) VALUES ('schema_version', '1');
