"""Deferred-outcome memory services independent from the ADK runtime."""

from __future__ import annotations

import asyncio
import logging
from datetime import date, timedelta
from typing import Any

import yfinance

from app.domain.contracts import AnalysisRequest, PendingOutcome

logger = logging.getLogger(__name__)


class MarketOutcomeResolver:
    """Calculate a decision's raw and SPY-relative return."""

    def __init__(self, market_data: Any = yfinance) -> None:
        self._market_data = market_data

    def resolve(
        self,
        ticker: str,
        trade_date: date,
        decision: str,
        holding_days: int = 5,
    ) -> PendingOutcome | None:
        try:
            stock = self._history(ticker, trade_date, holding_days)
            benchmark = self._history("SPY", trade_date, holding_days)
            # Compare identical dates across different trading calendars.
            stock.index = stock.index.tz_localize(None).normalize()
            benchmark.index = benchmark.index.tz_localize(None).normalize()
            common = stock.index.intersection(benchmark.index).sort_values()
            stock, benchmark = stock.loc[common], benchmark.loc[common]
            actual_days = holding_days
            if holding_days < 1 or len(common) <= holding_days:
                return None
            raw_return = self._return(stock, actual_days)
            alpha_return = raw_return - self._return(benchmark, actual_days)
            return PendingOutcome(
                ticker=ticker,
                trade_date=trade_date,
                decision=decision,
                raw_return=raw_return,
                alpha_return=alpha_return,
                holding_days=actual_days,
            )
        except Exception as error:  # noqa: BLE001 - vendor failures are not stable
            logger.warning("Deferred outcome unavailable for %s: %s", ticker, error)
            return None

    def _history(self, ticker: str, trade_date: date, holding_days: int):
        end_date = trade_date + timedelta(days=holding_days + 7)
        instrument = self._market_data.Ticker(ticker)
        return instrument.history(start=str(trade_date), end=str(end_date))

    @staticmethod
    def _return(history, holding_days: int) -> float:
        start = history["Close"].iloc[0]
        end = history["Close"].iloc[holding_days]
        return float((end - start) / start)


class TradingMemoryService:
    """Read durable context, then resolve market outcomes outside SQL sessions."""

    def __init__(self, repository, outcome_resolver: MarketOutcomeResolver) -> None:
        self._repository = repository
        self._outcome_resolver = outcome_resolver

    async def prepare(self, request: AnalysisRequest) -> AnalysisRequest:
        snapshot = await self._repository.snapshot(
            request.requested_by or "system", request.ticker, request.analysis_date
        )
        pending = []
        for entry in snapshot.pending:
            outcome = await asyncio.to_thread(
                self._outcome_resolver.resolve,
                ticker=entry.ticker,
                trade_date=entry.analysis_date,
                decision=entry.decision,
            )
            if outcome is not None:
                pending.append(outcome.model_copy(update={"memory_id": entry.id}))
        return request.model_copy(
            update={
                "past_context": snapshot.context,
                "pending_outcomes": tuple(pending),
            }
        )
