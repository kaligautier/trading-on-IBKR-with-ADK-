--liquibase formatted sql
--changeset deepcopy:momentum-ticker-suggestions-20261024
--comment: Recover public suggestion intake in Momentum API; no analysis dispatch.
CREATE SCHEMA _suggestions AUTHORIZATION database_migrator;
REVOKE ALL ON SCHEMA _suggestions FROM PUBLIC;
CREATE TABLE _suggestions.ticker_suggestions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol varchar(32) NOT NULL UNIQUE CHECK (symbol ~ '^[A-Z0-9^][A-Z0-9.^=_-]{0,31}$'),
    reason varchar(500) NOT NULL,
    status varchar(20) NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'approved', 'rejected')),
    suggested_by varchar(64) NOT NULL CHECK (suggested_by ~ '^[0-9a-f]{64}$'),
    source varchar(20) NOT NULL DEFAULT 'mcp' CHECK (source IN ('mcp', 'admin')),
    created_at timestamptz NOT NULL DEFAULT now(),
    reviewed_at timestamptz,
    reviewed_by varchar(255),
    review_reason varchar(500)
);
CREATE INDEX ticker_suggestions_caller_created
    ON _suggestions.ticker_suggestions(suggested_by, created_at DESC);
-- Reuse the API's existing bounded connection pool; no additional login/pool.
-- Existing _analysis and _sessions grants are deliberately untouched.
GRANT USAGE ON SCHEMA _suggestions TO momentum_results_reader;
GRANT SELECT ON _suggestions.ticker_suggestions TO momentum_results_reader;
GRANT INSERT(symbol, reason, suggested_by) ON _suggestions.ticker_suggestions
    TO momentum_results_reader;
-- No UPDATE, DELETE, DDL, review/status/source/timestamp INSERT or grant option.
