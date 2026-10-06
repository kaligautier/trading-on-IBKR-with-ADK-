"""Provider-independent market data response DTOs."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from math import isfinite


@dataclass(frozen=True)
class ClosingPrice:
    """One authoritative closing price observed on a calendar date."""

    observed_on: date
    value: float | Decimal


class ClosingPriceHistory:
    """Chronological collection of dated closing prices."""

    def __init__(self, prices: tuple[ClosingPrice, ...]) -> None:
        if any(not isfinite(price.value) for price in prices):
            raise ValueError("Closing prices must be finite")
        by_date = {}
        for price in prices:
            previous = by_date.get(price.observed_on)
            if previous is not None and previous.value != price.value:
                raise ValueError("Conflicting observations for the same date")
            by_date[price.observed_on] = price
        self._prices = tuple(by_date[day] for day in sorted(by_date))

    @property
    def prices(self) -> tuple[ClosingPrice, ...]:
        return self._prices

    @property
    def latest(self) -> ClosingPrice | None:
        if not self._prices:
            return None
        return self._prices[-1]

    def on_or_before(self, target_date: date) -> ClosingPrice | None:
        eligible_prices = [
            price for price in self._prices if price.observed_on <= target_date
        ]
        if not eligible_prices:
            return None
        return eligible_prices[-1]
