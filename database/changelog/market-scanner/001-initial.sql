--liquibase formatted sql

--changeset deep-copy:market-scanner-001 dbms:postgresql
--comment: Create the isolated market scanner analysis schema and its runtime permissions.
CREATE SCHEMA _analysis AUTHORIZATION database_migrator;
REVOKE ALL ON SCHEMA _analysis FROM PUBLIC;
GRANT USAGE ON SCHEMA _analysis TO market_scanner_writer, market_scanner_reader;
CREATE TABLE _analysis.market_scans (
    id UUID PRIMARY KEY,
    scan_date DATE NOT NULL,
    session_id TEXT NOT NULL,
    regime TEXT NOT NULL,
    summary TEXT NOT NULL,
    recommendation TEXT,
    data_quality JSONB,
    report JSONB,
    created_at TIMESTAMPTZ NOT NULL
);
CREATE TABLE _analysis.market_scan_assets (
    id UUID PRIMARY KEY,
    scan_id UUID NOT NULL REFERENCES _analysis.market_scans(id),
    name TEXT NOT NULL,
    symbol TEXT NOT NULL,
    kind TEXT NOT NULL DEFAULT 'market',
    unit TEXT,
    value NUMERIC NOT NULL,
    trend TEXT,
    analysis TEXT NOT NULL,
    context TEXT NOT NULL
);
CREATE TABLE _analysis.market_scan_horizons (
    id UUID PRIMARY KEY,
    asset_id UUID NOT NULL REFERENCES _analysis.market_scan_assets(id),
    horizon TEXT NOT NULL,
    change_pct DOUBLE PRECISION NOT NULL,
    ref_price NUMERIC NOT NULL,
    trend TEXT NOT NULL
);
CREATE INDEX market_scans_created_at_idx
    ON _analysis.market_scans (created_at DESC);
CREATE INDEX market_scan_assets_scan_id_idx
    ON _analysis.market_scan_assets (scan_id);
CREATE INDEX market_scan_horizons_asset_id_idx
    ON _analysis.market_scan_horizons (asset_id);

REVOKE ALL ON ALL TABLES IN SCHEMA _analysis FROM PUBLIC;
GRANT INSERT ON _analysis.market_scans, _analysis.market_scan_assets,
    _analysis.market_scan_horizons TO market_scanner_writer;
GRANT SELECT ON _analysis.market_scans, _analysis.market_scan_assets,
    _analysis.market_scan_horizons TO market_scanner_reader;

--rollback DROP TABLE _analysis.market_scan_horizons;
--rollback DROP TABLE _analysis.market_scan_assets;
--rollback DROP TABLE _analysis.market_scans;
--rollback DROP SCHEMA _analysis;
