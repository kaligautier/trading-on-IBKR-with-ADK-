--liquibase formatted sql

--changeset deep-copy:momentum-results-001 dbms:postgresql
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:1 SELECT CASE WHEN current_database() = 'momentum_results' THEN 1 ELSE 0 END;
--comment: Completed financial results and durable ADK execution correlation.
CREATE SCHEMA momentum AUTHORIZATION database_migrator;
REVOKE ALL ON SCHEMA momentum FROM PUBLIC;
GRANT USAGE ON SCHEMA momentum TO momentum_results_writer;

CREATE TABLE momentum.analysis_results (
    session_id VARCHAR(128) NOT NULL,
    invocation_id VARCHAR(256) NOT NULL,
    user_id VARCHAR(128) NOT NULL,
    id UUID NOT NULL,
    ticker VARCHAR(32) NOT NULL,
    analysis_date DATE NOT NULL,
    llm_provider VARCHAR(30) NOT NULL,
    deep_think_llm VARCHAR(50) NOT NULL,
    quick_think_llm VARCHAR(50) NOT NULL,
    next_analysis_date DATE,
    next_analysis_desc TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    PRIMARY KEY (id)
);
CREATE INDEX ix_analysis_results_session_invocation ON momentum.analysis_results (session_id, invocation_id);
CREATE INDEX ix_momentum_analysis_results_ticker ON momentum.analysis_results (ticker);

CREATE TABLE momentum.debate_arguments (
    id UUID NOT NULL,
    result_id UUID NOT NULL,
    ticker VARCHAR(32) NOT NULL,
    analysis_date DATE NOT NULL,
    debate_type VARCHAR(20) NOT NULL,
    role VARCHAR(20) NOT NULL,
    round_number INTEGER NOT NULL,
    thesis TEXT,
    conviction_level VARCHAR(100),
    stance VARCHAR(100),
    target_price FLOAT,
    recommended_entry FLOAT,
    recommended_position_size VARCHAR(200),
    key_data_point TEXT,
    argument_full TEXT,
    PRIMARY KEY (id),
    FOREIGN KEY(result_id) REFERENCES momentum.analysis_results (id)
);

CREATE TABLE momentum.fundamentals (
    id UUID NOT NULL,
    result_id UUID NOT NULL,
    ticker VARCHAR(32) NOT NULL,
    analysis_date DATE NOT NULL,
    market_cap FLOAT,
    market_cap_unit VARCHAR(10),
    market_cap_trend VARCHAR(20),
    market_cap_comment TEXT,
    pe_ratio FLOAT,
    pe_ratio_trend VARCHAR(20),
    pe_ratio_comment TEXT,
    forward_pe FLOAT,
    forward_pe_trend VARCHAR(20),
    forward_pe_comment TEXT,
    peg_ratio FLOAT,
    peg_ratio_trend VARCHAR(20),
    peg_ratio_comment TEXT,
    eps_ttm FLOAT,
    eps_ttm_trend VARCHAR(20),
    eps_ttm_comment TEXT,
    forward_eps FLOAT,
    forward_eps_trend VARCHAR(20),
    forward_eps_comment TEXT,
    revenue FLOAT,
    revenue_trend VARCHAR(20),
    revenue_comment TEXT,
    net_income FLOAT,
    net_income_trend VARCHAR(20),
    net_income_comment TEXT,
    profit_margin FLOAT,
    profit_margin_trend VARCHAR(20),
    profit_margin_comment TEXT,
    operating_margin FLOAT,
    operating_margin_trend VARCHAR(20),
    operating_margin_comment TEXT,
    roe FLOAT,
    roe_trend VARCHAR(20),
    roe_comment TEXT,
    roa FLOAT,
    roa_trend VARCHAR(20),
    roa_comment TEXT,
    debt_to_equity FLOAT,
    debt_to_equity_trend VARCHAR(20),
    debt_to_equity_comment TEXT,
    current_ratio FLOAT,
    current_ratio_trend VARCHAR(20),
    current_ratio_comment TEXT,
    total_cash FLOAT,
    total_cash_trend VARCHAR(20),
    total_cash_comment TEXT,
    free_cash_flow FLOAT,
    free_cash_flow_trend VARCHAR(20),
    free_cash_flow_comment TEXT,
    capex FLOAT,
    capex_trend VARCHAR(20),
    capex_comment TEXT,
    dividend_yield FLOAT,
    dividend_yield_trend VARCHAR(20),
    dividend_yield_comment TEXT,
    beta FLOAT,
    beta_trend VARCHAR(20),
    beta_comment TEXT,
    financial_health VARCHAR(30),
    growth_outlook VARCHAR(30),
    valuation_assessment VARCHAR(30),
    summary_short TEXT,
    summary_long TEXT,
    PRIMARY KEY (id),
    FOREIGN KEY(result_id) REFERENCES momentum.analysis_results (id)
);

CREATE TABLE momentum.news_items (
    id UUID NOT NULL,
    result_id UUID NOT NULL,
    ticker VARCHAR(32) NOT NULL,
    analysis_date DATE NOT NULL,
    category VARCHAR(30) NOT NULL,
    headline TEXT NOT NULL,
    impact VARCHAR(20) NOT NULL,
    urgency VARCHAR(20) NOT NULL,
    comment TEXT NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY(result_id) REFERENCES momentum.analysis_results (id)
);

CREATE TABLE momentum.news_results (
    id UUID NOT NULL,
    result_id UUID NOT NULL,
    ticker VARCHAR(32) NOT NULL,
    analysis_date DATE NOT NULL,
    overall_impact VARCHAR(30),
    macro_environment VARCHAR(20),
    sector_momentum VARCHAR(20),
    key_catalyst TEXT,
    key_risk TEXT,
    summary_short TEXT,
    summary_long TEXT,
    PRIMARY KEY (id),
    FOREIGN KEY(result_id) REFERENCES momentum.analysis_results (id)
);

CREATE TABLE momentum.portfolio_decisions (
    id UUID NOT NULL,
    result_id UUID NOT NULL,
    ticker VARCHAR(32) NOT NULL,
    analysis_date DATE NOT NULL,
    rating VARCHAR(20) NOT NULL,
    executive_summary TEXT NOT NULL,
    investment_thesis TEXT NOT NULL,
    price_target FLOAT,
    entry_price FLOAT,
    stop_loss FLOAT,
    position_size FLOAT,
    position_size_description VARCHAR(200),
    time_horizon_months FLOAT,
    time_horizon_description VARCHAR(200),
    risk_reward_ratio FLOAT,
    risk_reward_description VARCHAR(200),
    PRIMARY KEY (id),
    FOREIGN KEY(result_id) REFERENCES momentum.analysis_results (id)
);
CREATE INDEX ix_momentum_portfolio_decisions_rating ON momentum.portfolio_decisions (rating);
CREATE INDEX ix_momentum_portfolio_decisions_ticker ON momentum.portfolio_decisions (ticker);

CREATE TABLE momentum.research_plans (
    id UUID NOT NULL,
    result_id UUID NOT NULL,
    ticker VARCHAR(32) NOT NULL,
    analysis_date DATE NOT NULL,
    recommendation VARCHAR(20) NOT NULL,
    rationale TEXT NOT NULL,
    strategic_actions TEXT NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY(result_id) REFERENCES momentum.analysis_results (id)
);

CREATE TABLE momentum.run_stats (
    id UUID NOT NULL,
    result_id UUID NOT NULL,
    agents_total INTEGER NOT NULL,
    agents_completed INTEGER NOT NULL,
    llm_calls INTEGER NOT NULL,
    tool_calls INTEGER NOT NULL,
    tokens_in BIGINT NOT NULL,
    tokens_out BIGINT NOT NULL,
    reports_total INTEGER NOT NULL,
    reports_completed INTEGER NOT NULL,
    duration_seconds FLOAT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY(result_id) REFERENCES momentum.analysis_results (id)
);

CREATE TABLE momentum.sentiment_items (
    id UUID NOT NULL,
    result_id UUID NOT NULL,
    ticker VARCHAR(32) NOT NULL,
    analysis_date DATE NOT NULL,
    topic TEXT NOT NULL,
    sentiment_score FLOAT NOT NULL,
    impact VARCHAR(20) NOT NULL,
    source_type VARCHAR(20) NOT NULL,
    comment TEXT NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY(result_id) REFERENCES momentum.analysis_results (id)
);

CREATE TABLE momentum.sentiment_results (
    id UUID NOT NULL,
    result_id UUID NOT NULL,
    ticker VARCHAR(32) NOT NULL,
    analysis_date DATE NOT NULL,
    overall_sentiment FLOAT,
    overall_signal VARCHAR(30),
    retail_sentiment VARCHAR(30),
    institutional_sentiment VARCHAR(30),
    key_risk TEXT,
    key_catalyst TEXT,
    summary_short TEXT,
    summary_long TEXT,
    PRIMARY KEY (id),
    FOREIGN KEY(result_id) REFERENCES momentum.analysis_results (id)
);

CREATE TABLE momentum.technical_indicators (
    id UUID NOT NULL,
    result_id UUID NOT NULL,
    ticker VARCHAR(32) NOT NULL,
    analysis_date DATE NOT NULL,
    close_price FLOAT,
    close_signal VARCHAR(30),
    close_comment TEXT,
    sma_50 FLOAT,
    sma_50_signal VARCHAR(30),
    sma_50_comment TEXT,
    sma_200 FLOAT,
    sma_200_signal VARCHAR(30),
    sma_200_comment TEXT,
    ema_10 FLOAT,
    ema_10_signal VARCHAR(30),
    ema_10_comment TEXT,
    rsi FLOAT,
    rsi_signal VARCHAR(30),
    rsi_comment TEXT,
    macd FLOAT,
    macd_signal_state VARCHAR(30),
    macd_comment TEXT,
    macd_signal_val FLOAT,
    macd_signal_val_signal VARCHAR(30),
    macd_signal_val_comment TEXT,
    macd_histogram FLOAT,
    macd_histogram_signal VARCHAR(30),
    macd_histogram_comment TEXT,
    boll_upper FLOAT,
    boll_upper_signal VARCHAR(30),
    boll_upper_comment TEXT,
    boll_lower FLOAT,
    boll_lower_signal VARCHAR(30),
    boll_lower_comment TEXT,
    atr FLOAT,
    atr_signal VARCHAR(30),
    atr_comment TEXT,
    vwma FLOAT,
    vwma_signal VARCHAR(30),
    vwma_comment TEXT,
    mfi FLOAT,
    mfi_signal VARCHAR(30),
    mfi_comment TEXT,
    trend_direction VARCHAR(30),
    momentum_state VARCHAR(30),
    volatility_regime VARCHAR(30),
    key_support FLOAT,
    key_resistance FLOAT,
    actionable_recommendation VARCHAR(30),
    summary_short TEXT,
    summary_long TEXT,
    PRIMARY KEY (id),
    FOREIGN KEY(result_id) REFERENCES momentum.analysis_results (id)
);

CREATE TABLE momentum.trader_proposals (
    id UUID NOT NULL,
    result_id UUID NOT NULL,
    ticker VARCHAR(32) NOT NULL,
    analysis_date DATE NOT NULL,
    action VARCHAR(10) NOT NULL,
    reasoning TEXT NOT NULL,
    entry_price FLOAT,
    stop_loss FLOAT,
    take_profit FLOAT,
    position_sizing VARCHAR(100),
    risk_reward_ratio VARCHAR(20),
    PRIMARY KEY (id),
    FOREIGN KEY(result_id) REFERENCES momentum.analysis_results (id)
);

REVOKE ALL ON momentum.analysis_results,
    momentum.debate_arguments,
    momentum.fundamentals,
    momentum.news_items,
    momentum.news_results,
    momentum.portfolio_decisions,
    momentum.research_plans,
    momentum.run_stats,
    momentum.sentiment_items,
    momentum.sentiment_results,
    momentum.technical_indicators,
    momentum.trader_proposals FROM PUBLIC;
GRANT SELECT, INSERT ON momentum.analysis_results,
    momentum.debate_arguments,
    momentum.fundamentals,
    momentum.news_items,
    momentum.news_results,
    momentum.portfolio_decisions,
    momentum.research_plans,
    momentum.run_stats,
    momentum.sentiment_items,
    momentum.sentiment_results,
    momentum.technical_indicators,
    momentum.trader_proposals TO momentum_results_writer;

--rollback DROP TABLE momentum.trader_proposals;
--rollback DROP TABLE momentum.technical_indicators;
--rollback DROP TABLE momentum.sentiment_results;
--rollback DROP TABLE momentum.sentiment_items;
--rollback DROP TABLE momentum.run_stats;
--rollback DROP TABLE momentum.research_plans;
--rollback DROP TABLE momentum.portfolio_decisions;
--rollback DROP TABLE momentum.news_results;
--rollback DROP TABLE momentum.news_items;
--rollback DROP TABLE momentum.fundamentals;
--rollback DROP TABLE momentum.debate_arguments;
--rollback DROP TABLE momentum.analysis_results;
--rollback DROP SCHEMA momentum;
