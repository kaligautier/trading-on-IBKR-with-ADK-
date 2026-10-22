"""Typed public responses, with UTC serialization and private fields excluded."""

from datetime import UTC, date, datetime
from uuid import UUID

from pydantic import AwareDatetime, field_validator

from app.sections import (
    DebateArgument,
    FinancialModel,
    Fundamentals,
    News,
    PortfolioDecision,
    ResearchPlan,
    RunStats,
    Sentiment,
    TechnicalIndicators,
    TraderProposal,
)


class AnalysisHeader(FinancialModel):
    id: UUID
    ticker: str
    analysis_date: date
    created_at: AwareDatetime
    llm_provider: str
    next_analysis_date: date | None = None

    @field_validator("created_at")
    @classmethod
    def utc_creation(cls, value: datetime) -> datetime:
        return value.astimezone(UTC)


class AnalysisSummary(AnalysisHeader):
    rating: str | None = None
    executive_summary: str | None = None
    price_target: float | None = None
    entry_price: float | None = None
    stop_loss: float | None = None
    position_size: float | None = None
    position_size_description: str | None = None
    time_horizon_months: float | None = None
    time_horizon_description: str | None = None
    risk_reward_ratio: float | None = None
    risk_reward_description: str | None = None
    trader_action: str | None = None
    trader_entry: float | None = None
    trader_stop: float | None = None
    trader_take_profit: float | None = None
    close_price: float | None = None
    rsi: float | None = None
    rsi_signal: str | None = None
    trend_direction: str | None = None
    key_support: float | None = None
    key_resistance: float | None = None
    pe_ratio: float | None = None
    peg_ratio: float | None = None
    beta: float | None = None


class AnalysisDetail(AnalysisHeader):
    deep_think_llm: str
    quick_think_llm: str
    next_analysis_desc: str | None = None
    technical_indicators: TechnicalIndicators | None
    fundamentals: Fundamentals | None
    sentiment: Sentiment | None
    news: News | None
    research_plan: ResearchPlan | None
    trader_proposal: TraderProposal | None
    portfolio_decision: PortfolioDecision | None
    debate_arguments: list[DebateArgument]
    run_stats: RunStats | None


class AnalysisPage(FinancialModel):
    items: list[AnalysisSummary]
    next_page_token: str
