"""Typed boundaries shared by the Momentum workflow and its adapters.

Ported from DeepCopy 38d0736; reject non-iterable analyst input during validation.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from enum import StrEnum
from typing import Any, Protocol
from uuid import UUID

from pydantic import (
    BaseModel,
    Field,
    FiniteFloat,
    RootModel,
    field_validator,
    model_validator,
)

from app.domain.ticker import TickerSymbol


class AnalystKind(StrEnum):
    MARKET = "market"
    SOCIAL = "social"
    NEWS = "news"
    FUNDAMENTALS = "fundamentals"


class SelectedAnalysts(RootModel[tuple[AnalystKind, ...]]):
    """Ordered, duplicate-free collection of analyst roles."""

    def __init__(self, values: Sequence[AnalystKind | str]) -> None:
        if not isinstance(values, Sequence) or isinstance(values, (str, bytes)):
            raise ValueError("analysts must be a collection of role names")
        super().__init__(root=tuple(AnalystKind(value) for value in values))

    @model_validator(mode="after")
    def validate_collection(self) -> SelectedAnalysts:
        if not self.root:
            raise ValueError("at least one analyst is required")
        if len(self.root) != len(set(self.root)):
            raise ValueError("duplicate analysts are not allowed")
        return self

    @property
    def values(self) -> tuple[AnalystKind, ...]:
        return self.root

    def serialized(self) -> list[str]:
        return [analyst.value for analyst in self.values]


class AnalysisRequest(BaseModel):
    """Authenticated, session-scoped input accepted by the ADK workflow."""

    ticker: str
    analysis_date: date
    selected_analysts: SelectedAnalysts = Field(
        default_factory=lambda: SelectedAnalysts(tuple(AnalystKind))
    )
    requested_by: str
    session_id: UUID
    invocation_id: str | None = None
    past_context: str = ""
    max_debate_rounds: int = Field(default=1, ge=1, le=10)
    max_risk_discuss_rounds: int = Field(default=1, ge=1, le=10)
    output_language: str = "English"
    pending_outcomes: tuple[PendingOutcome, ...] = ()

    @field_validator("ticker", mode="before")
    @classmethod
    def normalize_ticker(cls, value: str) -> str:
        return str(TickerSymbol(value))

    @field_validator("selected_analysts", mode="before")
    @classmethod
    def build_analyst_collection(cls, value: Any) -> SelectedAnalysts:
        if isinstance(value, SelectedAnalysts):
            return value
        return SelectedAnalysts(value)


class RunStatistics(BaseModel):
    agents_total: int = 0
    agents_completed: int = 0
    llm_calls: int = 0
    tool_calls: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    reports_total: int = 0
    reports_completed: int = 0
    duration_seconds: float = 0.0


class PendingOutcome(BaseModel):
    ticker: str
    trade_date: date
    decision: str
    raw_return: FiniteFloat
    alpha_return: FiniteFloat
    holding_days: int


class MemoryReflection(PendingOutcome):
    reflection: str


class WorkflowResult(BaseModel):
    """Stable result returned by every Momentum analysis engine."""

    ticker: str
    analysis_date: date
    signal: str
    final_decision: str
    structured: dict[str, Any]
    reports: dict[str, str]
    next_analysis_date: date | None = None
    next_analysis_desc: str | None = None
    run_stats: RunStatistics = Field(default_factory=RunStatistics)
    memory_reflections: list[MemoryReflection] = Field(default_factory=list)


class WorkflowExecution(BaseModel):
    result: WorkflowResult
    user_id: str
    session_id: str
    invocation_id: str


class AnalysisEngine(Protocol):
    async def execute(
        self,
        request: AnalysisRequest,
        invocation_id: str | None = None,
    ) -> WorkflowExecution:
        """Execute one complete, resumable Momentum analysis."""
