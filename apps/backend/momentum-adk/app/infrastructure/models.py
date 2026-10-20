"""SQLAlchemy persistence models for completed Momentum analyses.

Ported from DeepCopy 38d0736. Only completed-result tables are included;
explicit schema and execution correlation isolate the new worker's writes.
"""

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    metadata = MetaData(schema="_analysis")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


# ===========================================================================
# Main result (1 per job)
# ===========================================================================


class AnalysisResult(Base):
    __tablename__ = "analysis_results"
    __table_args__ = (
        Index("ix_analysis_results_session_invocation", "session_id", "invocation_id"),
    )

    # Correlation survives session cleanup; there is deliberately no ADK FK.
    session_id: Mapped[str] = mapped_column(String(128), nullable=False)
    invocation_id: Mapped[str] = mapped_column(String(256), nullable=False)
    user_id: Mapped[str] = mapped_column(String(128), nullable=False)
    # No unique constraint: multiple analyses per (ticker, date) are allowed.
    # The most recent (by created_at) is served to clients.

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    ticker: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    analysis_date: Mapped[date] = mapped_column(Date, nullable=False)

    # LLM model used
    llm_provider: Mapped[str] = mapped_column(String(30), nullable=False)
    deep_think_llm: Mapped[str] = mapped_column(String(50), nullable=False)
    quick_think_llm: Mapped[str] = mapped_column(String(50), nullable=False)

    # Next analysis recommendation
    next_analysis_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    next_analysis_desc: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )

    # Relationships
    technical_indicators: Mapped["TechnicalIndicators | None"] = relationship(
        back_populates="result", uselist=False
    )
    fundamentals: Mapped["Fundamentals | None"] = relationship(
        back_populates="result", uselist=False
    )
    sentiment: Mapped["SentimentResult | None"] = relationship(
        back_populates="result", uselist=False
    )
    sentiment_items: Mapped[list["SentimentItemRow"]] = relationship(
        back_populates="result"
    )
    news: Mapped["NewsResult | None"] = relationship(
        back_populates="result", uselist=False
    )
    news_items: Mapped[list["NewsItemRow"]] = relationship(back_populates="result")
    research_plan: Mapped["ResearchPlanRow | None"] = relationship(
        back_populates="result", uselist=False
    )
    trader_proposal: Mapped["TraderProposalRow | None"] = relationship(
        back_populates="result", uselist=False
    )
    portfolio_decision: Mapped["PortfolioDecisionRow | None"] = relationship(
        back_populates="result", uselist=False
    )
    debate_arguments: Mapped[list["DebateArgumentRow"]] = relationship(
        back_populates="result"
    )
    run_stats: Mapped["RunStats | None"] = relationship(
        back_populates="result", uselist=False
    )


# ===========================================================================
# Technical Indicators (Market Analyst)
# ===========================================================================


class TechnicalIndicators(Base):
    __tablename__ = "technical_indicators"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    result_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("_analysis.analysis_results.id"), nullable=False
    )
    ticker: Mapped[str] = mapped_column(String(32), nullable=False)
    analysis_date: Mapped[date] = mapped_column(Date, nullable=False)

    # Each indicator: value + signal + comment
    close_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    close_signal: Mapped[str | None] = mapped_column(String(30), nullable=True)
    close_comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    sma_50: Mapped[float | None] = mapped_column(Float, nullable=True)
    sma_50_signal: Mapped[str | None] = mapped_column(String(30), nullable=True)
    sma_50_comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    sma_200: Mapped[float | None] = mapped_column(Float, nullable=True)
    sma_200_signal: Mapped[str | None] = mapped_column(String(30), nullable=True)
    sma_200_comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    ema_10: Mapped[float | None] = mapped_column(Float, nullable=True)
    ema_10_signal: Mapped[str | None] = mapped_column(String(30), nullable=True)
    ema_10_comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    rsi: Mapped[float | None] = mapped_column(Float, nullable=True)
    rsi_signal: Mapped[str | None] = mapped_column(String(30), nullable=True)
    rsi_comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    macd: Mapped[float | None] = mapped_column(Float, nullable=True)
    macd_signal_state: Mapped[str | None] = mapped_column(String(30), nullable=True)
    macd_comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    macd_signal_val: Mapped[float | None] = mapped_column(Float, nullable=True)
    macd_signal_val_signal: Mapped[str | None] = mapped_column(
        String(30), nullable=True
    )
    macd_signal_val_comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    macd_histogram: Mapped[float | None] = mapped_column(Float, nullable=True)
    macd_histogram_signal: Mapped[str | None] = mapped_column(String(30), nullable=True)
    macd_histogram_comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    boll_upper: Mapped[float | None] = mapped_column(Float, nullable=True)
    boll_upper_signal: Mapped[str | None] = mapped_column(String(30), nullable=True)
    boll_upper_comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    boll_lower: Mapped[float | None] = mapped_column(Float, nullable=True)
    boll_lower_signal: Mapped[str | None] = mapped_column(String(30), nullable=True)
    boll_lower_comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    atr: Mapped[float | None] = mapped_column(Float, nullable=True)
    atr_signal: Mapped[str | None] = mapped_column(String(30), nullable=True)
    atr_comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    vwma: Mapped[float | None] = mapped_column(Float, nullable=True)
    vwma_signal: Mapped[str | None] = mapped_column(String(30), nullable=True)
    vwma_comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    mfi: Mapped[float | None] = mapped_column(Float, nullable=True)
    mfi_signal: Mapped[str | None] = mapped_column(String(30), nullable=True)
    mfi_comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Aggregated assessments
    trend_direction: Mapped[str | None] = mapped_column(String(30), nullable=True)
    momentum_state: Mapped[str | None] = mapped_column(String(30), nullable=True)
    volatility_regime: Mapped[str | None] = mapped_column(String(30), nullable=True)
    key_support: Mapped[float | None] = mapped_column(Float, nullable=True)
    key_resistance: Mapped[float | None] = mapped_column(Float, nullable=True)
    actionable_recommendation: Mapped[str | None] = mapped_column(
        String(30), nullable=True
    )
    summary_short: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary_long: Mapped[str | None] = mapped_column(Text, nullable=True)

    result: Mapped["AnalysisResult"] = relationship(
        back_populates="technical_indicators"
    )


# ===========================================================================
# Fundamentals (Fundamentals Analyst)
# ===========================================================================


class Fundamentals(Base):
    __tablename__ = "fundamentals"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    result_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("_analysis.analysis_results.id"), nullable=False
    )
    ticker: Mapped[str] = mapped_column(String(32), nullable=False)
    analysis_date: Mapped[date] = mapped_column(Date, nullable=False)

    # Each metric: value + unit + trend + comment
    market_cap: Mapped[float | None] = mapped_column(Float, nullable=True)
    market_cap_unit: Mapped[str | None] = mapped_column(String(10), nullable=True)
    market_cap_trend: Mapped[str | None] = mapped_column(String(20), nullable=True)
    market_cap_comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    pe_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    pe_ratio_trend: Mapped[str | None] = mapped_column(String(20), nullable=True)
    pe_ratio_comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    forward_pe: Mapped[float | None] = mapped_column(Float, nullable=True)
    forward_pe_trend: Mapped[str | None] = mapped_column(String(20), nullable=True)
    forward_pe_comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    peg_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    peg_ratio_trend: Mapped[str | None] = mapped_column(String(20), nullable=True)
    peg_ratio_comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    eps_ttm: Mapped[float | None] = mapped_column(Float, nullable=True)
    eps_ttm_trend: Mapped[str | None] = mapped_column(String(20), nullable=True)
    eps_ttm_comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    forward_eps: Mapped[float | None] = mapped_column(Float, nullable=True)
    forward_eps_trend: Mapped[str | None] = mapped_column(String(20), nullable=True)
    forward_eps_comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    revenue: Mapped[float | None] = mapped_column(Float, nullable=True)
    revenue_trend: Mapped[str | None] = mapped_column(String(20), nullable=True)
    revenue_comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    net_income: Mapped[float | None] = mapped_column(Float, nullable=True)
    net_income_trend: Mapped[str | None] = mapped_column(String(20), nullable=True)
    net_income_comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    profit_margin: Mapped[float | None] = mapped_column(Float, nullable=True)
    profit_margin_trend: Mapped[str | None] = mapped_column(String(20), nullable=True)
    profit_margin_comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    operating_margin: Mapped[float | None] = mapped_column(Float, nullable=True)
    operating_margin_trend: Mapped[str | None] = mapped_column(
        String(20), nullable=True
    )
    operating_margin_comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    roe: Mapped[float | None] = mapped_column(Float, nullable=True)
    roe_trend: Mapped[str | None] = mapped_column(String(20), nullable=True)
    roe_comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    roa: Mapped[float | None] = mapped_column(Float, nullable=True)
    roa_trend: Mapped[str | None] = mapped_column(String(20), nullable=True)
    roa_comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    debt_to_equity: Mapped[float | None] = mapped_column(Float, nullable=True)
    debt_to_equity_trend: Mapped[str | None] = mapped_column(String(20), nullable=True)
    debt_to_equity_comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    current_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    current_ratio_trend: Mapped[str | None] = mapped_column(String(20), nullable=True)
    current_ratio_comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    total_cash: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_cash_trend: Mapped[str | None] = mapped_column(String(20), nullable=True)
    total_cash_comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    free_cash_flow: Mapped[float | None] = mapped_column(Float, nullable=True)
    free_cash_flow_trend: Mapped[str | None] = mapped_column(String(20), nullable=True)
    free_cash_flow_comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    capex: Mapped[float | None] = mapped_column(Float, nullable=True)
    capex_trend: Mapped[str | None] = mapped_column(String(20), nullable=True)
    capex_comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    dividend_yield: Mapped[float | None] = mapped_column(Float, nullable=True)
    dividend_yield_trend: Mapped[str | None] = mapped_column(String(20), nullable=True)
    dividend_yield_comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    beta: Mapped[float | None] = mapped_column(Float, nullable=True)
    beta_trend: Mapped[str | None] = mapped_column(String(20), nullable=True)
    beta_comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Aggregated assessments
    financial_health: Mapped[str | None] = mapped_column(String(30), nullable=True)
    growth_outlook: Mapped[str | None] = mapped_column(String(30), nullable=True)
    valuation_assessment: Mapped[str | None] = mapped_column(String(30), nullable=True)
    summary_short: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary_long: Mapped[str | None] = mapped_column(Text, nullable=True)

    result: Mapped["AnalysisResult"] = relationship(back_populates="fundamentals")


# ===========================================================================
# Sentiment (Social Media Analyst) — header row
# ===========================================================================


class SentimentResult(Base):
    __tablename__ = "sentiment_results"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    result_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("_analysis.analysis_results.id"), nullable=False
    )
    ticker: Mapped[str] = mapped_column(String(32), nullable=False)
    analysis_date: Mapped[date] = mapped_column(Date, nullable=False)

    overall_sentiment: Mapped[float | None] = mapped_column(Float, nullable=True)
    overall_signal: Mapped[str | None] = mapped_column(String(30), nullable=True)
    retail_sentiment: Mapped[str | None] = mapped_column(String(30), nullable=True)
    institutional_sentiment: Mapped[str | None] = mapped_column(
        String(30), nullable=True
    )
    key_risk: Mapped[str | None] = mapped_column(Text, nullable=True)
    key_catalyst: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary_short: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary_long: Mapped[str | None] = mapped_column(Text, nullable=True)

    result: Mapped["AnalysisResult"] = relationship(back_populates="sentiment")


# ===========================================================================
# Sentiment items (child rows)
# ===========================================================================


class SentimentItemRow(Base):
    __tablename__ = "sentiment_items"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    result_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("_analysis.analysis_results.id"), nullable=False
    )
    ticker: Mapped[str] = mapped_column(String(32), nullable=False)
    analysis_date: Mapped[date] = mapped_column(Date, nullable=False)

    topic: Mapped[str] = mapped_column(Text, nullable=False)
    sentiment_score: Mapped[float] = mapped_column(Float, nullable=False)
    impact: Mapped[str] = mapped_column(String(20), nullable=False)
    source_type: Mapped[str] = mapped_column(String(20), nullable=False)
    comment: Mapped[str] = mapped_column(Text, nullable=False)

    result: Mapped["AnalysisResult"] = relationship(back_populates="sentiment_items")


# ===========================================================================
# News (News Analyst) — header row
# ===========================================================================


class NewsResult(Base):
    __tablename__ = "news_results"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    result_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("_analysis.analysis_results.id"), nullable=False
    )
    ticker: Mapped[str] = mapped_column(String(32), nullable=False)
    analysis_date: Mapped[date] = mapped_column(Date, nullable=False)

    overall_impact: Mapped[str | None] = mapped_column(String(30), nullable=True)
    macro_environment: Mapped[str | None] = mapped_column(String(20), nullable=True)
    sector_momentum: Mapped[str | None] = mapped_column(String(20), nullable=True)
    key_catalyst: Mapped[str | None] = mapped_column(Text, nullable=True)
    key_risk: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary_short: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary_long: Mapped[str | None] = mapped_column(Text, nullable=True)

    result: Mapped["AnalysisResult"] = relationship(back_populates="news")


# ===========================================================================
# News items (child rows)
# ===========================================================================


class NewsItemRow(Base):
    __tablename__ = "news_items"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    result_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("_analysis.analysis_results.id"), nullable=False
    )
    ticker: Mapped[str] = mapped_column(String(32), nullable=False)
    analysis_date: Mapped[date] = mapped_column(Date, nullable=False)

    category: Mapped[str] = mapped_column(String(30), nullable=False)
    headline: Mapped[str] = mapped_column(Text, nullable=False)
    impact: Mapped[str] = mapped_column(String(20), nullable=False)
    urgency: Mapped[str] = mapped_column(String(20), nullable=False)
    comment: Mapped[str] = mapped_column(Text, nullable=False)

    result: Mapped["AnalysisResult"] = relationship(back_populates="news_items")


# ===========================================================================
# Research Plan (Research Manager)
# ===========================================================================


class ResearchPlanRow(Base):
    __tablename__ = "research_plans"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    result_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("_analysis.analysis_results.id"), nullable=False
    )
    ticker: Mapped[str] = mapped_column(String(32), nullable=False)
    analysis_date: Mapped[date] = mapped_column(Date, nullable=False)

    recommendation: Mapped[str] = mapped_column(String(20), nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    strategic_actions: Mapped[str] = mapped_column(Text, nullable=False)

    result: Mapped["AnalysisResult"] = relationship(back_populates="research_plan")


# ===========================================================================
# Trader Proposal
# ===========================================================================


class TraderProposalRow(Base):
    __tablename__ = "trader_proposals"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    result_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("_analysis.analysis_results.id"), nullable=False
    )
    ticker: Mapped[str] = mapped_column(String(32), nullable=False)
    analysis_date: Mapped[date] = mapped_column(Date, nullable=False)

    action: Mapped[str] = mapped_column(String(10), nullable=False)
    reasoning: Mapped[str] = mapped_column(Text, nullable=False)
    entry_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    stop_loss: Mapped[float | None] = mapped_column(Float, nullable=True)
    take_profit: Mapped[float | None] = mapped_column(Float, nullable=True)
    position_sizing: Mapped[str | None] = mapped_column(String(100), nullable=True)
    risk_reward_ratio: Mapped[str | None] = mapped_column(String(20), nullable=True)

    result: Mapped["AnalysisResult"] = relationship(back_populates="trader_proposal")


# ===========================================================================
# Portfolio Decision (final)
# ===========================================================================


class PortfolioDecisionRow(Base):
    __tablename__ = "portfolio_decisions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    result_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("_analysis.analysis_results.id"), nullable=False
    )
    ticker: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    analysis_date: Mapped[date] = mapped_column(Date, nullable=False)

    rating: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    executive_summary: Mapped[str] = mapped_column(Text, nullable=False)
    investment_thesis: Mapped[str] = mapped_column(Text, nullable=False)
    price_target: Mapped[float | None] = mapped_column(Float, nullable=True)
    entry_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    stop_loss: Mapped[float | None] = mapped_column(Float, nullable=True)
    position_size: Mapped[float | None] = mapped_column(Float, nullable=True)
    position_size_description: Mapped[str | None] = mapped_column(
        String(200), nullable=True
    )
    time_horizon_months: Mapped[float | None] = mapped_column(Float, nullable=True)
    time_horizon_description: Mapped[str | None] = mapped_column(
        String(200), nullable=True
    )
    risk_reward_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    risk_reward_description: Mapped[str | None] = mapped_column(
        String(200), nullable=True
    )

    result: Mapped["AnalysisResult"] = relationship(back_populates="portfolio_decision")


# ===========================================================================
# Debate arguments (all debaters, 1 row per round per role)
# ===========================================================================


class DebateArgumentRow(Base):
    __tablename__ = "debate_arguments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    result_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("_analysis.analysis_results.id"), nullable=False
    )
    ticker: Mapped[str] = mapped_column(String(32), nullable=False)
    analysis_date: Mapped[date] = mapped_column(Date, nullable=False)

    debate_type: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # investment / risk
    role: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # bull/bear/aggressive/conservative/neutral
    round_number: Mapped[int] = mapped_column(Integer, nullable=False)

    # Shared structured fields
    thesis: Mapped[str | None] = mapped_column(Text, nullable=True)
    conviction_level: Mapped[str | None] = mapped_column(String(100), nullable=True)
    stance: Mapped[str | None] = mapped_column(String(100), nullable=True)
    target_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    recommended_entry: Mapped[float | None] = mapped_column(Float, nullable=True)
    recommended_position_size: Mapped[str | None] = mapped_column(
        String(200), nullable=True
    )
    key_data_point: Mapped[str | None] = mapped_column(Text, nullable=True)
    argument_full: Mapped[str | None] = mapped_column(Text, nullable=True)

    result: Mapped["AnalysisResult"] = relationship(back_populates="debate_arguments")


# ===========================================================================
# Run Stats (pipeline metrics)
# ===========================================================================


class RunStats(Base):
    __tablename__ = "run_stats"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    result_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("_analysis.analysis_results.id"), nullable=False
    )

    agents_total: Mapped[int] = mapped_column(Integer, nullable=False)
    agents_completed: Mapped[int] = mapped_column(Integer, nullable=False)
    llm_calls: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tool_calls: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tokens_in: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    tokens_out: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    reports_total: Mapped[int] = mapped_column(Integer, nullable=False)
    reports_completed: Mapped[int] = mapped_column(Integer, nullable=False)
    duration_seconds: Mapped[float] = mapped_column(Float, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )

    result: Mapped["AnalysisResult"] = relationship(back_populates="run_stats")
