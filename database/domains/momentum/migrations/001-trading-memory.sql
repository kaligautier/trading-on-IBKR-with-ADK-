--liquibase formatted sql

--changeset deepcopy:momentum-trading-memory-001
CREATE TABLE _analysis.trading_memory (
    id uuid PRIMARY KEY,
    user_id varchar(128) NOT NULL CHECK (length(btrim(user_id)) > 0),
    session_id varchar(128) NOT NULL CHECK (length(btrim(session_id)) > 0),
    invocation_id varchar(256) NOT NULL CHECK (length(btrim(invocation_id)) > 0),
    ticker varchar(32) NOT NULL,
    analysis_date date NOT NULL,
    decision text NOT NULL,
    completion_digest varchar(64) NOT NULL CHECK (completion_digest ~ '^[0-9a-f]{64}$'),
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    raw_return double precision,
    alpha_return double precision,
    holding_days integer CHECK (holding_days > 0),
    reflection text,
    resolved_at timestamptz,
    CONSTRAINT trading_memory_execution UNIQUE (user_id, session_id, invocation_id),
    CONSTRAINT trading_memory_resolution CHECK (
        (reflection IS NULL AND resolved_at IS NULL AND raw_return IS NULL
            AND alpha_return IS NULL AND holding_days IS NULL)
        OR
        (reflection IS NOT NULL AND resolved_at IS NOT NULL AND raw_return IS NOT NULL
            AND alpha_return IS NOT NULL AND holding_days IS NOT NULL)
    )
);

CREATE INDEX trading_memory_pending ON _analysis.trading_memory
    (user_id, ticker, analysis_date, id) WHERE reflection IS NULL;
CREATE INDEX trading_memory_ticker_context ON _analysis.trading_memory
    (user_id, ticker, created_at DESC, id DESC) WHERE reflection IS NOT NULL;
CREATE INDEX trading_memory_recent_context ON _analysis.trading_memory
    (user_id, created_at DESC, id DESC) WHERE reflection IS NOT NULL;

GRANT SELECT, INSERT ON _analysis.trading_memory TO momentum_results_writer;
GRANT UPDATE (raw_return, alpha_return, holding_days, reflection, resolved_at)
    ON _analysis.trading_memory TO momentum_results_writer;

-- No session FK: expiring ADK sessions must not erase durable trading memory.
-- No reader grant: decisions/reflections carry private user context.
-- Forward-only once populated; roll back the application, not retained memory.
