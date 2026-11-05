"""Validated Momentum analysis responses."""

from datetime import date, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel


class AnalysisSummary(BaseModel):
    id: UUID
    ticker: str
    analysis_date: date
    created_at: datetime | None
    llm_provider: str
    next_analysis_date: date | None
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


class RunStatistics(BaseModel):
    agents_total: int
    agents_completed: int
    llm_calls: int
    tool_calls: int
    tokens_in: int
    tokens_out: int
    reports_total: int
    reports_completed: int
    duration_seconds: float


class AnalysisDetail(BaseModel):
    id: UUID
    ticker: str
    analysis_date: date
    created_at: datetime | None
    llm_provider: str
    deep_think_llm: str
    quick_think_llm: str
    next_analysis_date: date | None
    next_analysis_desc: str | None
    technical_indicators: dict[str, Any] | None
    fundamentals: dict[str, Any] | None
    sentiment: dict[str, Any] | None
    news: dict[str, Any] | None
    research_plan: dict[str, Any] | None
    trader_proposal: dict[str, Any] | None
    portfolio_decision: dict[str, Any] | None
    debate_arguments: list[dict[str, Any]]
    run_stats: RunStatistics | None


class ReaderPage(BaseModel):
    items: list[AnalysisSummary]
    next_page_token: str
