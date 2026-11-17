-- Schema-only baseline captured from Aiven PostgreSQL 18.6 on 2026-10-23.
-- Run as database_migrator; contains no business data.

-- _analysis
CREATE SCHEMA _analysis;

CREATE TABLE _analysis.analysis_results (
    session_id character varying(128) NOT NULL,
    invocation_id character varying(256) NOT NULL,
    user_id character varying(128) NOT NULL,
    id uuid NOT NULL,
    ticker character varying(32) NOT NULL,
    analysis_date date NOT NULL,
    llm_provider character varying(30) NOT NULL,
    deep_think_llm character varying(50) NOT NULL,
    quick_think_llm character varying(50) NOT NULL,
    next_analysis_date date,
    next_analysis_desc text,
    created_at timestamp with time zone NOT NULL
);

CREATE TABLE _analysis.debate_arguments (
    id uuid NOT NULL,
    result_id uuid NOT NULL,
    ticker character varying(32) NOT NULL,
    analysis_date date NOT NULL,
    debate_type character varying(20) NOT NULL,
    role character varying(20) NOT NULL,
    round_number integer NOT NULL,
    thesis text,
    conviction_level character varying(100),
    stance character varying(100),
    target_price double precision,
    recommended_entry double precision,
    recommended_position_size character varying(200),
    key_data_point text,
    argument_full text
);

CREATE TABLE _analysis.fundamentals (
    id uuid NOT NULL,
    result_id uuid NOT NULL,
    ticker character varying(32) NOT NULL,
    analysis_date date NOT NULL,
    market_cap double precision,
    market_cap_unit character varying(10),
    market_cap_trend character varying(20),
    market_cap_comment text,
    pe_ratio double precision,
    pe_ratio_trend character varying(20),
    pe_ratio_comment text,
    forward_pe double precision,
    forward_pe_trend character varying(20),
    forward_pe_comment text,
    peg_ratio double precision,
    peg_ratio_trend character varying(20),
    peg_ratio_comment text,
    eps_ttm double precision,
    eps_ttm_trend character varying(20),
    eps_ttm_comment text,
    forward_eps double precision,
    forward_eps_trend character varying(20),
    forward_eps_comment text,
    revenue double precision,
    revenue_trend character varying(20),
    revenue_comment text,
    net_income double precision,
    net_income_trend character varying(20),
    net_income_comment text,
    profit_margin double precision,
    profit_margin_trend character varying(20),
    profit_margin_comment text,
    operating_margin double precision,
    operating_margin_trend character varying(20),
    operating_margin_comment text,
    roe double precision,
    roe_trend character varying(20),
    roe_comment text,
    roa double precision,
    roa_trend character varying(20),
    roa_comment text,
    debt_to_equity double precision,
    debt_to_equity_trend character varying(20),
    debt_to_equity_comment text,
    current_ratio double precision,
    current_ratio_trend character varying(20),
    current_ratio_comment text,
    total_cash double precision,
    total_cash_trend character varying(20),
    total_cash_comment text,
    free_cash_flow double precision,
    free_cash_flow_trend character varying(20),
    free_cash_flow_comment text,
    capex double precision,
    capex_trend character varying(20),
    capex_comment text,
    dividend_yield double precision,
    dividend_yield_trend character varying(20),
    dividend_yield_comment text,
    beta double precision,
    beta_trend character varying(20),
    beta_comment text,
    financial_health character varying(30),
    growth_outlook character varying(30),
    valuation_assessment character varying(30),
    summary_short text,
    summary_long text
);

CREATE TABLE _analysis.news_items (
    id uuid NOT NULL,
    result_id uuid NOT NULL,
    ticker character varying(32) NOT NULL,
    analysis_date date NOT NULL,
    category character varying(30) NOT NULL,
    headline text NOT NULL,
    impact character varying(20) NOT NULL,
    urgency character varying(20) NOT NULL,
    comment text NOT NULL
);

CREATE TABLE _analysis.news_results (
    id uuid NOT NULL,
    result_id uuid NOT NULL,
    ticker character varying(32) NOT NULL,
    analysis_date date NOT NULL,
    overall_impact character varying(30),
    macro_environment character varying(20),
    sector_momentum character varying(20),
    key_catalyst text,
    key_risk text,
    summary_short text,
    summary_long text
);

CREATE TABLE _analysis.portfolio_decisions (
    id uuid NOT NULL,
    result_id uuid NOT NULL,
    ticker character varying(32) NOT NULL,
    analysis_date date NOT NULL,
    rating character varying(20) NOT NULL,
    executive_summary text NOT NULL,
    investment_thesis text NOT NULL,
    price_target double precision,
    entry_price double precision,
    stop_loss double precision,
    position_size double precision,
    position_size_description character varying(200),
    time_horizon_months double precision,
    time_horizon_description character varying(200),
    risk_reward_ratio double precision,
    risk_reward_description character varying(200)
);

CREATE TABLE _analysis.research_plans (
    id uuid NOT NULL,
    result_id uuid NOT NULL,
    ticker character varying(32) NOT NULL,
    analysis_date date NOT NULL,
    recommendation character varying(20) NOT NULL,
    rationale text NOT NULL,
    strategic_actions text NOT NULL
);

CREATE TABLE _analysis.run_stats (
    id uuid NOT NULL,
    result_id uuid NOT NULL,
    agents_total integer NOT NULL,
    agents_completed integer NOT NULL,
    llm_calls integer NOT NULL,
    tool_calls integer NOT NULL,
    tokens_in bigint NOT NULL,
    tokens_out bigint NOT NULL,
    reports_total integer NOT NULL,
    reports_completed integer NOT NULL,
    duration_seconds double precision NOT NULL,
    created_at timestamp with time zone NOT NULL
);

CREATE TABLE _analysis.sentiment_items (
    id uuid NOT NULL,
    result_id uuid NOT NULL,
    ticker character varying(32) NOT NULL,
    analysis_date date NOT NULL,
    topic text NOT NULL,
    sentiment_score double precision,
    impact character varying(20) NOT NULL,
    source_type character varying(20) NOT NULL,
    comment text NOT NULL
);

CREATE TABLE _analysis.sentiment_results (
    id uuid NOT NULL,
    result_id uuid NOT NULL,
    ticker character varying(32) NOT NULL,
    analysis_date date NOT NULL,
    overall_sentiment double precision,
    overall_signal character varying(30),
    retail_sentiment character varying(30),
    institutional_sentiment character varying(30),
    key_risk text,
    key_catalyst text,
    summary_short text,
    summary_long text
);

CREATE TABLE _analysis.technical_indicators (
    id uuid NOT NULL,
    result_id uuid NOT NULL,
    ticker character varying(32) NOT NULL,
    analysis_date date NOT NULL,
    close_price double precision,
    close_signal character varying(30),
    close_comment text,
    sma_50 double precision,
    sma_50_signal character varying(30),
    sma_50_comment text,
    sma_200 double precision,
    sma_200_signal character varying(30),
    sma_200_comment text,
    ema_10 double precision,
    ema_10_signal character varying(30),
    ema_10_comment text,
    rsi double precision,
    rsi_signal character varying(30),
    rsi_comment text,
    macd double precision,
    macd_signal_state character varying(30),
    macd_comment text,
    macd_signal_val double precision,
    macd_signal_val_signal character varying(30),
    macd_signal_val_comment text,
    macd_histogram double precision,
    macd_histogram_signal character varying(30),
    macd_histogram_comment text,
    boll_upper double precision,
    boll_upper_signal character varying(30),
    boll_upper_comment text,
    boll_lower double precision,
    boll_lower_signal character varying(30),
    boll_lower_comment text,
    atr double precision,
    atr_signal character varying(30),
    atr_comment text,
    vwma double precision,
    vwma_signal character varying(30),
    vwma_comment text,
    mfi double precision,
    mfi_signal character varying(30),
    mfi_comment text,
    trend_direction character varying(30),
    momentum_state character varying(30),
    volatility_regime character varying(30),
    key_support double precision,
    key_resistance double precision,
    actionable_recommendation character varying(30),
    summary_short text,
    summary_long text
);

CREATE TABLE _analysis.trader_proposals (
    id uuid NOT NULL,
    result_id uuid NOT NULL,
    ticker character varying(32) NOT NULL,
    analysis_date date NOT NULL,
    action character varying(10) NOT NULL,
    reasoning text NOT NULL,
    entry_price double precision,
    stop_loss double precision,
    take_profit double precision,
    position_sizing character varying(100),
    risk_reward_ratio text
);

ALTER TABLE ONLY _analysis.analysis_results
    ADD CONSTRAINT analysis_results_pkey PRIMARY KEY (id);

ALTER TABLE ONLY _analysis.debate_arguments
    ADD CONSTRAINT debate_arguments_pkey PRIMARY KEY (id);

ALTER TABLE ONLY _analysis.fundamentals
    ADD CONSTRAINT fundamentals_pkey PRIMARY KEY (id);

ALTER TABLE ONLY _analysis.news_items
    ADD CONSTRAINT news_items_pkey PRIMARY KEY (id);

ALTER TABLE ONLY _analysis.news_results
    ADD CONSTRAINT news_results_pkey PRIMARY KEY (id);

ALTER TABLE ONLY _analysis.portfolio_decisions
    ADD CONSTRAINT portfolio_decisions_pkey PRIMARY KEY (id);

ALTER TABLE ONLY _analysis.research_plans
    ADD CONSTRAINT research_plans_pkey PRIMARY KEY (id);

ALTER TABLE ONLY _analysis.run_stats
    ADD CONSTRAINT run_stats_pkey PRIMARY KEY (id);

ALTER TABLE ONLY _analysis.sentiment_items
    ADD CONSTRAINT sentiment_items_pkey PRIMARY KEY (id);

ALTER TABLE ONLY _analysis.sentiment_results
    ADD CONSTRAINT sentiment_results_pkey PRIMARY KEY (id);

ALTER TABLE ONLY _analysis.technical_indicators
    ADD CONSTRAINT technical_indicators_pkey PRIMARY KEY (id);

ALTER TABLE ONLY _analysis.trader_proposals
    ADD CONSTRAINT trader_proposals_pkey PRIMARY KEY (id);

CREATE INDEX ix__analysis_analysis_results_ticker ON _analysis.analysis_results USING btree (ticker);

CREATE INDEX ix__analysis_portfolio_decisions_rating ON _analysis.portfolio_decisions USING btree (rating);

CREATE INDEX ix__analysis_portfolio_decisions_ticker ON _analysis.portfolio_decisions USING btree (ticker);

CREATE INDEX ix_analysis_results_session_invocation ON _analysis.analysis_results USING btree (session_id, invocation_id);

CREATE INDEX ix_consultation_created ON _analysis.analysis_results USING btree (created_at DESC, id DESC);

CREATE INDEX ix_consultation_debate_arguments_result ON _analysis.debate_arguments USING btree (result_id, id);

CREATE INDEX ix_consultation_fundamentals_result ON _analysis.fundamentals USING btree (result_id, id);

CREATE INDEX ix_consultation_news_items_result ON _analysis.news_items USING btree (result_id, id);

CREATE INDEX ix_consultation_news_results_result ON _analysis.news_results USING btree (result_id, id);

CREATE INDEX ix_consultation_portfolio_decisions_result ON _analysis.portfolio_decisions USING btree (result_id, id);

CREATE INDEX ix_consultation_research_plans_result ON _analysis.research_plans USING btree (result_id, id);

CREATE INDEX ix_consultation_run_stats_result ON _analysis.run_stats USING btree (result_id, id);

CREATE INDEX ix_consultation_sentiment_items_result ON _analysis.sentiment_items USING btree (result_id, id);

CREATE INDEX ix_consultation_sentiment_results_result ON _analysis.sentiment_results USING btree (result_id, id);

CREATE INDEX ix_consultation_technical_indicators_result ON _analysis.technical_indicators USING btree (result_id, id);

CREATE INDEX ix_consultation_ticker_created ON _analysis.analysis_results USING btree (ticker, created_at DESC, id DESC);

CREATE INDEX ix_consultation_trader_proposals_result ON _analysis.trader_proposals USING btree (result_id, id);

ALTER TABLE ONLY _analysis.debate_arguments
    ADD CONSTRAINT debate_arguments_result_id_fkey FOREIGN KEY (result_id) REFERENCES _analysis.analysis_results(id);

ALTER TABLE ONLY _analysis.fundamentals
    ADD CONSTRAINT fundamentals_result_id_fkey FOREIGN KEY (result_id) REFERENCES _analysis.analysis_results(id);

ALTER TABLE ONLY _analysis.news_items
    ADD CONSTRAINT news_items_result_id_fkey FOREIGN KEY (result_id) REFERENCES _analysis.analysis_results(id);

ALTER TABLE ONLY _analysis.news_results
    ADD CONSTRAINT news_results_result_id_fkey FOREIGN KEY (result_id) REFERENCES _analysis.analysis_results(id);

ALTER TABLE ONLY _analysis.portfolio_decisions
    ADD CONSTRAINT portfolio_decisions_result_id_fkey FOREIGN KEY (result_id) REFERENCES _analysis.analysis_results(id);

ALTER TABLE ONLY _analysis.research_plans
    ADD CONSTRAINT research_plans_result_id_fkey FOREIGN KEY (result_id) REFERENCES _analysis.analysis_results(id);

ALTER TABLE ONLY _analysis.run_stats
    ADD CONSTRAINT run_stats_result_id_fkey FOREIGN KEY (result_id) REFERENCES _analysis.analysis_results(id);

ALTER TABLE ONLY _analysis.sentiment_items
    ADD CONSTRAINT sentiment_items_result_id_fkey FOREIGN KEY (result_id) REFERENCES _analysis.analysis_results(id);

ALTER TABLE ONLY _analysis.sentiment_results
    ADD CONSTRAINT sentiment_results_result_id_fkey FOREIGN KEY (result_id) REFERENCES _analysis.analysis_results(id);

ALTER TABLE ONLY _analysis.technical_indicators
    ADD CONSTRAINT technical_indicators_result_id_fkey FOREIGN KEY (result_id) REFERENCES _analysis.analysis_results(id);

ALTER TABLE ONLY _analysis.trader_proposals
    ADD CONSTRAINT trader_proposals_result_id_fkey FOREIGN KEY (result_id) REFERENCES _analysis.analysis_results(id);

GRANT USAGE ON SCHEMA _analysis TO momentum_results_writer;
GRANT USAGE ON SCHEMA _analysis TO momentum_results_reader;

GRANT SELECT,INSERT ON TABLE _analysis.analysis_results TO momentum_results_writer;
GRANT SELECT ON TABLE _analysis.analysis_results TO momentum_results_reader;

GRANT SELECT,INSERT ON TABLE _analysis.debate_arguments TO momentum_results_writer;
GRANT SELECT ON TABLE _analysis.debate_arguments TO momentum_results_reader;

GRANT SELECT,INSERT ON TABLE _analysis.fundamentals TO momentum_results_writer;
GRANT SELECT ON TABLE _analysis.fundamentals TO momentum_results_reader;

GRANT SELECT,INSERT ON TABLE _analysis.news_items TO momentum_results_writer;
GRANT SELECT ON TABLE _analysis.news_items TO momentum_results_reader;

GRANT SELECT,INSERT ON TABLE _analysis.news_results TO momentum_results_writer;
GRANT SELECT ON TABLE _analysis.news_results TO momentum_results_reader;

GRANT SELECT,INSERT ON TABLE _analysis.portfolio_decisions TO momentum_results_writer;
GRANT SELECT ON TABLE _analysis.portfolio_decisions TO momentum_results_reader;

GRANT SELECT,INSERT ON TABLE _analysis.research_plans TO momentum_results_writer;
GRANT SELECT ON TABLE _analysis.research_plans TO momentum_results_reader;

GRANT SELECT,INSERT ON TABLE _analysis.run_stats TO momentum_results_writer;
GRANT SELECT ON TABLE _analysis.run_stats TO momentum_results_reader;

GRANT SELECT,INSERT ON TABLE _analysis.sentiment_items TO momentum_results_writer;
GRANT SELECT ON TABLE _analysis.sentiment_items TO momentum_results_reader;

GRANT SELECT,INSERT ON TABLE _analysis.sentiment_results TO momentum_results_writer;
GRANT SELECT ON TABLE _analysis.sentiment_results TO momentum_results_reader;

GRANT SELECT,INSERT ON TABLE _analysis.technical_indicators TO momentum_results_writer;
GRANT SELECT ON TABLE _analysis.technical_indicators TO momentum_results_reader;

GRANT SELECT,INSERT ON TABLE _analysis.trader_proposals TO momentum_results_writer;
GRANT SELECT ON TABLE _analysis.trader_proposals TO momentum_results_reader;

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

GRANT USAGE ON SCHEMA _sessions TO momentum_sessions_writer;

GRANT SELECT ON TABLE _sessions.adk_internal_metadata TO momentum_sessions_writer;

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE _sessions.app_states TO momentum_sessions_writer;

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE _sessions.events TO momentum_sessions_writer;

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE _sessions.sessions TO momentum_sessions_writer;

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE _sessions.user_states TO momentum_sessions_writer;

-- Required SDK metadata, not application/session data.
INSERT INTO _sessions.adk_internal_metadata (key, value) VALUES ('schema_version', '1');
