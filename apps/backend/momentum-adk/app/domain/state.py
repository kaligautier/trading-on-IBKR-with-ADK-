"""Typed values flowing between Momentum workflow nodes."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field

from app.domain.analysis import (
    AggressiveArgument,
    BearArgument,
    BullArgument,
    ConservativeArgument,
    FundamentalsAnalysis,
    MarketAnalysis,
    NeutralArgument,
    NewsAnalysis,
    PortfolioDecision,
    ResearchPlan,
    SentimentAnalysis,
    TraderProposal,
)
from app.domain.contracts import AnalysisRequest, MemoryReflection


class AnalystReports(BaseModel):
    request: AnalysisRequest
    memory_reflections: list[MemoryReflection] = Field(default_factory=list)
    market: MarketAnalysis | None = None
    social: SentimentAnalysis | None = None
    news: NewsAnalysis | None = None
    fundamentals: FundamentalsAnalysis | None = None


class ResearchOutcome(BaseModel):
    reports: AnalystReports
    bull_arguments: list[BullArgument] = Field(default_factory=list)
    bear_arguments: list[BearArgument] = Field(default_factory=list)
    plan: ResearchPlan


class TraderOutcome(BaseModel):
    research: ResearchOutcome
    proposal: TraderProposal


class RiskOutcome(BaseModel):
    trader: TraderOutcome
    aggressive_arguments: list[AggressiveArgument] = Field(default_factory=list)
    conservative_arguments: list[ConservativeArgument] = Field(default_factory=list)
    neutral_arguments: list[NeutralArgument] = Field(default_factory=list)


class PortfolioOutcome(BaseModel):
    risk: RiskOutcome
    decision: PortfolioDecision


class NextAnalysisRecommendation(BaseModel):
    analysis_date: date
    description: str


class ReflectionText(BaseModel):
    reflection: str
