from datetime import date
from unittest.mock import AsyncMock
from uuid import uuid4

from app.domain.contracts import AnalysisRequest, PendingOutcome
from app.infrastructure.memory.postgres import MemoryEntry, MemorySnapshot
from app.services.memory import TradingMemoryService


async def test_prepare_retains_source_id_and_user_scope():
    entry = MemoryEntry(uuid4(), "NVDA", date(2026, 7, 1), "Buy")
    repository = AsyncMock()
    repository.snapshot.return_value = MemorySnapshot("Prior lesson", (entry,))

    class Resolver:
        def resolve(self, ticker, trade_date, decision):
            repository.snapshot.assert_awaited_once()
            return PendingOutcome(
                ticker=ticker,
                trade_date=trade_date,
                decision=decision,
                raw_return=0.08,
                alpha_return=0.03,
                holding_days=5,
            )

    request = AnalysisRequest(
        ticker="NVDA",
        analysis_date=date(2026, 8, 2),
        requested_by="owner",
        session_id=uuid4(),
    )
    prepared = await TradingMemoryService(repository, Resolver()).prepare(request)
    repository.snapshot.assert_awaited_once_with("owner", "NVDA", request.analysis_date)
    assert prepared.past_context == "Prior lesson"
    assert prepared.pending_outcomes[0].memory_id == entry.id
    assert prepared.pending_outcomes[0].alpha_return == 0.03


def test_outcome_waits_for_aligned_market_sessions():
    from types import SimpleNamespace

    import pandas as pd

    from app.services.memory import MarketOutcomeResolver

    crypto = pd.DataFrame(
        {"Close": range(100, 110)}, index=pd.date_range("2026-10-01", periods=10)
    )
    spy = pd.DataFrame(
        {"Close": range(100, 107)}, index=pd.bdate_range("2026-10-01", periods=7)
    )

    class Data:
        def Ticker(self, ticker):  # noqa: N802 - provider interface
            return SimpleNamespace(
                history=lambda **kw: (spy if ticker == "SPY" else crypto).copy()
            )

    resolver = MarketOutcomeResolver(Data())
    outcome = resolver.resolve("BTC-USD", date(2026, 10, 1), "Buy")
    assert outcome.holding_days == 5
    assert outcome.raw_return == 0.07  # October 8 for both calendars.
    assert round(outcome.alpha_return, 8) == 0.02
    spy = spy.iloc[:5]
    assert resolver.resolve("BTC-USD", date(2026, 10, 1), "Buy") is None
