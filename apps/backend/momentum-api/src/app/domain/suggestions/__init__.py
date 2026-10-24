"""Public suggestion contract recovered from DeepCopy; no dispatch capability."""

import re
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class SuggestionInput:
    symbol: str
    reason: str
    caller: str

    def __post_init__(self) -> None:
        symbol, reason = self.symbol.strip().upper(), self.reason.strip()
        if not re.fullmatch(r"[A-Z0-9^][A-Z0-9.^=_-]{0,31}", symbol):
            raise ValueError("Invalid ticker")
        if len(reason) > 500 or not re.fullmatch(r"[0-9a-f]{64}", self.caller):
            raise ValueError("Invalid suggestion")
        object.__setattr__(self, "symbol", symbol)
        object.__setattr__(self, "reason", reason)


@dataclass(frozen=True)
class Suggestion:
    id: UUID
    symbol: str
    reason: str
    status: str
    source: str
    created_at: datetime
    reviewed_at: datetime | None
    review_reason: str | None


class CurrentAnalysisExistsError(Exception):
    """A ticker with a current analysis cannot be proposed again."""


class SuggestionRateLimitError(Exception):
    """The original cooldown or daily limit was reached."""
