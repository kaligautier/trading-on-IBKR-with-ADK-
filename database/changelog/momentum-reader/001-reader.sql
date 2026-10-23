--liquibase formatted sql
--changeset momentum:consultation-reader-001 dbms:postgresql
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:1 SELECT CASE WHEN current_database() = 'momentum' AND current_user = 'database_migrator' THEN 1 ELSE 0 END;
--comment: Allowlisted reader privileges and bounded consultation access paths.
GRANT USAGE ON SCHEMA _analysis TO momentum_results_reader;
GRANT SELECT ON _analysis.analysis_results,
    _analysis.debate_arguments,
    _analysis.fundamentals,
    _analysis.news_items,
    _analysis.news_results,
    _analysis.portfolio_decisions,
    _analysis.research_plans,
    _analysis.run_stats,
    _analysis.sentiment_items,
    _analysis.sentiment_results,
    _analysis.technical_indicators,
    _analysis.trader_proposals TO momentum_results_reader;

CREATE INDEX ix_consultation_created ON _analysis.analysis_results (created_at DESC, id DESC);
CREATE INDEX ix_consultation_ticker_created ON _analysis.analysis_results (ticker, created_at DESC, id DESC);
CREATE INDEX ix_consultation_debate_arguments_result ON _analysis.debate_arguments (result_id, id);
CREATE INDEX ix_consultation_fundamentals_result ON _analysis.fundamentals (result_id, id);
CREATE INDEX ix_consultation_news_items_result ON _analysis.news_items (result_id, id);
CREATE INDEX ix_consultation_news_results_result ON _analysis.news_results (result_id, id);
CREATE INDEX ix_consultation_portfolio_decisions_result ON _analysis.portfolio_decisions (result_id, id);
CREATE INDEX ix_consultation_research_plans_result ON _analysis.research_plans (result_id, id);
CREATE INDEX ix_consultation_run_stats_result ON _analysis.run_stats (result_id, id);
CREATE INDEX ix_consultation_sentiment_items_result ON _analysis.sentiment_items (result_id, id);
CREATE INDEX ix_consultation_sentiment_results_result ON _analysis.sentiment_results (result_id, id);
CREATE INDEX ix_consultation_technical_indicators_result ON _analysis.technical_indicators (result_id, id);
CREATE INDEX ix_consultation_trader_proposals_result ON _analysis.trader_proposals (result_id, id);

--rollback REVOKE SELECT ON _analysis.analysis_results, _analysis.debate_arguments, _analysis.fundamentals, _analysis.news_items, _analysis.news_results, _analysis.portfolio_decisions, _analysis.research_plans, _analysis.run_stats, _analysis.sentiment_items, _analysis.sentiment_results, _analysis.technical_indicators, _analysis.trader_proposals FROM momentum_results_reader;
--rollback REVOKE USAGE ON SCHEMA _analysis FROM momentum_results_reader;
--rollback DROP INDEX _analysis.ix_consultation_debate_arguments_result;
--rollback DROP INDEX _analysis.ix_consultation_fundamentals_result;
--rollback DROP INDEX _analysis.ix_consultation_news_items_result;
--rollback DROP INDEX _analysis.ix_consultation_news_results_result;
--rollback DROP INDEX _analysis.ix_consultation_portfolio_decisions_result;
--rollback DROP INDEX _analysis.ix_consultation_research_plans_result;
--rollback DROP INDEX _analysis.ix_consultation_run_stats_result;
--rollback DROP INDEX _analysis.ix_consultation_sentiment_items_result;
--rollback DROP INDEX _analysis.ix_consultation_sentiment_results_result;
--rollback DROP INDEX _analysis.ix_consultation_technical_indicators_result;
--rollback DROP INDEX _analysis.ix_consultation_trader_proposals_result;
--rollback DROP INDEX _analysis.ix_consultation_ticker_created;
--rollback DROP INDEX _analysis.ix_consultation_created;
