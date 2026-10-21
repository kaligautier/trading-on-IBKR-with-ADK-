"""Deferred-outcome memory services independent from the ADK runtime."""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any

import yfinance

from app.domain.contracts import AnalysisRequest, PendingOutcome, WorkflowResult

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
    """Prepare and commit the memory state of one analysis."""

    def __init__(
        self, memory_log: Any, outcome_resolver: MarketOutcomeResolver
    ) -> None:
        self._memory_log = memory_log
        self._outcome_resolver = outcome_resolver

    def prepare(self, request: AnalysisRequest) -> AnalysisRequest:
        pending = self._pending_outcomes(request.ticker)
        return request.model_copy(
            update={
                "past_context": self._memory_log.get_past_context(request.ticker),
                "pending_outcomes": tuple(pending),
            }
        )

    def complete(self, request: AnalysisRequest, result: WorkflowResult) -> None:
        updates = [self._update(item) for item in result.memory_reflections]
        if updates:
            self._memory_log.batch_update_with_outcomes(updates)
        self._memory_log.store_decision(
            ticker=request.ticker,
            trade_date=str(request.analysis_date),
            final_trade_decision=result.final_decision,
        )

    def _pending_outcomes(self, ticker: str) -> list[PendingOutcome]:
        entries = self._memory_log.get_pending_entries()
        return [
            outcome
            for entry in entries
            if entry["ticker"] == ticker
            if (outcome := self._resolve(entry)) is not None
        ]

    def _resolve(self, entry: dict) -> PendingOutcome | None:
        return self._outcome_resolver.resolve(
            ticker=entry["ticker"],
            trade_date=date.fromisoformat(entry["date"]),
            decision=entry.get("decision", ""),
        )

    @staticmethod
    def _update(reflection) -> dict:
        return {
            "ticker": reflection.ticker,
            "trade_date": str(reflection.trade_date),
            "raw_return": reflection.raw_return,
            "alpha_return": reflection.alpha_return,
            "holding_days": reflection.holding_days,
            "reflection": reflection.reflection,
        }
