"""Public Momentum domain values and validated response models."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, ClassVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict


@dataclass(frozen=True, slots=True)
class TickerSymbol:
    """Canonical ticker accepted by the public boundary."""

    value: str

    _PATTERN = re.compile(r"^[A-Z0-9^][A-Z0-9.^=_-]{0,31}$")

    def __post_init__(self) -> None:
        normalized = self.value.strip().upper()
        if not self._PATTERN.fullmatch(normalized):
            raise ValueError(
                "Ticker must contain 1 to 32 letters, digits, '.', '-', '_', "
                "'=', or '^'."
            )
        object.__setattr__(self, "value", normalized)


@dataclass(frozen=True, slots=True)
class SuggestionReason:
    """Trimmed, bounded public suggestion rationale."""

    value: str

    def __post_init__(self) -> None:
        normalized = self.value.strip()
        if len(normalized) > 500:
            raise ValueError("Suggestion reason must contain at most 500 characters.")
        object.__setattr__(self, "value", normalized)


@dataclass(frozen=True, slots=True)
class AnalysisPage:
    """Bounded analysis pagination request."""

    limit: int = 50
    offset: int = 0

    def __post_init__(self) -> None:
        if not 1 <= self.limit <= 200:
            raise ValueError("Analysis limit must be between 1 and 200.")
        if self.offset < 0:
            raise ValueError("Analysis offset must be positive or zero.")


@dataclass(frozen=True, slots=True)
class Ratings:
    """Ordered, non-empty portfolio-rating collection."""

    values: tuple[str, ...]

    _CANONICAL: ClassVar[dict[str, str]] = {
        "buy": "Buy",
        "overweight": "Overweight",
        "hold": "Hold",
        "underweight": "Underweight",
        "sell": "Sell",
    }

    @classmethod
    def from_csv(cls, raw_ratings: str) -> Ratings:
        if len(raw_ratings) > 128:
            raise ValueError("Rating filter must contain at most 128 characters.")
        raw_values = tuple(
            value.strip() for value in raw_ratings.split(",") if value.strip()
        )
        if not raw_values:
            raise ValueError("At least one rating is required.")
        values = tuple(cls._canonical(value) for value in raw_values)
        unique_values = tuple(dict.fromkeys(values))
        return cls(unique_values)

    @classmethod
    def _canonical(cls, raw_rating: str) -> str:
        rating = cls._CANONICAL.get(raw_rating.casefold())
        if rating is None:
            allowed = ", ".join(cls._CANONICAL.values())
            raise ValueError(f"Allowed ratings: {allowed}.")
        return rating

    def as_csv(self) -> str:
        return ",".join(self.values)


@dataclass(frozen=True, slots=True)
class AnalysisId:
    value: UUID

    @classmethod
    def parse(cls, raw_identifier: str) -> AnalysisId:
        try:
            return cls(UUID(raw_identifier))
        except ValueError as error:
            raise ValueError("Analysis id must be a valid UUID.") from error


@dataclass(frozen=True, slots=True)
class SuggestionId:
    value: UUID

    @classmethod
    def parse(cls, raw_identifier: str) -> SuggestionId:
        try:
            return cls(UUID(raw_identifier))
        except ValueError as error:
            raise ValueError("Suggestion id must be a valid UUID.") from error


class PublicResponse(BaseModel):
    """Allow additive API changes without leaking undeclared fields."""

    model_config = ConfigDict(extra="ignore")


class AnalysisSummary(PublicResponse):
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


class RunStatistics(PublicResponse):
    agents_total: int
    agents_completed: int
    llm_calls: int
    tool_calls: int
    tokens_in: int
    tokens_out: int
    reports_total: int
    reports_completed: int
    duration_seconds: float


class AnalysisDetail(PublicResponse):
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


class Suggestion(PublicResponse):
    id: UUID
    symbol: str
    reason: str
    status: str
    source: str
    created_at: datetime
    reviewed_at: datetime | None
    review_reason: str | None


class MarketScan(PublicResponse):
    """Reader envelope; preserve report-v3 values, including decimal strings."""

    id: UUID
    scan_date: date
    created_at: datetime
    report: dict[str, Any]


@dataclass(frozen=True, slots=True)
class AnalysisSummaries:
    """First-class collection of public analysis summaries."""

    items: tuple[AnalysisSummary, ...]

    def as_list(self) -> list[AnalysisSummary]:
        return list(self.items)
