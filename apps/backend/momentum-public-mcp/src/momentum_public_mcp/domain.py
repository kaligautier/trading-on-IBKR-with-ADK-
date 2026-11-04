"""Validated MCP inputs and aggregated consultation results."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import ClassVar
from uuid import UUID

from momentum_public_mcp.api.momentum.dtos.response.analyses import AnalysisSummary


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


@dataclass(frozen=True, slots=True)
class AnalysisSummaries:
    """First-class collection of public analysis summaries."""

    items: tuple[AnalysisSummary, ...]

    def as_list(self) -> list[AnalysisSummary]:
        return list(self.items)
