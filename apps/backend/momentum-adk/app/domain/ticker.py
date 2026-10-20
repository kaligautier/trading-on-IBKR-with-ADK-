"""Momentum domain value objects shared by the ADK runtime.

Ported from DeepCopy 38d0736; reject non-text ticker input during validation.
"""

import re
from dataclasses import dataclass
from enum import StrEnum


class SuggestionStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class SuggestionSource(StrEnum):
    MCP = "mcp"
    ADMIN = "admin"


@dataclass(frozen=True, slots=True)
class TickerSymbol:
    """Canonical ticker accepted by the Momentum boundary."""

    value: str

    MAX_LENGTH = 32
    _PATTERN = re.compile(r"^[A-Z0-9^][A-Z0-9.^=_-]{0,31}$")

    def __post_init__(self) -> None:
        if not isinstance(self.value, str):
            raise ValueError("Ticker must be text")
        normalized = self.value.strip().upper()
        if not self._PATTERN.fullmatch(normalized):
            raise ValueError(
                "Ticker must contain 1 to 32 letters, digits, '.', '-', '_', '=', or '^'"
            )
        object.__setattr__(self, "value", normalized)

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class DailyWatchlist:
    """Ordered, duplicate-free ticker collection for the daily flow."""

    symbols: tuple[TickerSymbol, ...]

    @classmethod
    def from_csv(cls, raw_symbols: str) -> "DailyWatchlist":
        symbols = cls._normalized_symbols(raw_symbols)
        return cls(tuple(symbols))

    @classmethod
    def _normalized_symbols(cls, raw_symbols: str) -> list[TickerSymbol]:
        symbols: list[TickerSymbol] = []
        seen: set[str] = set()
        for raw_symbol in raw_symbols.split(","):
            cls._append_symbol(raw_symbol, symbols, seen)
        return symbols

    @staticmethod
    def _append_symbol(
        raw_symbol: str,
        symbols: list[TickerSymbol],
        seen: set[str],
    ) -> None:
        if not raw_symbol.strip():
            return
        symbol = TickerSymbol(raw_symbol)
        if symbol.value in seen:
            return
        seen.add(symbol.value)
        symbols.append(symbol)

    def values(self) -> list[str]:
        return [symbol.value for symbol in self.symbols]

    def is_empty(self) -> bool:
        return not self.symbols
