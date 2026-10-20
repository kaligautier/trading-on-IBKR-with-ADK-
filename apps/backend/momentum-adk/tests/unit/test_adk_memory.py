from datetime import date
from uuid import uuid4

from app.domain.contracts import (
    AnalysisRequest,
    MemoryReflection,
    PendingOutcome,
    WorkflowResult,
)
from app.services.memory import TradingMemoryService


class RecordingLog:
    def __init__(self) -> None:
        self.updates = []
        self.decisions = []

    def get_pending_entries(self):
        return [{"ticker": "NVDA", "date": "2026-07-01", "decision": "Buy"}]

    def get_past_context(self, ticker):
        return f"Prior lessons for {ticker}"

    def batch_update_with_outcomes(self, updates):
        self.updates.extend(updates)

    def store_decision(self, **decision):
        self.decisions.append(decision)


class FixedResolver:
    def resolve(self, ticker, trade_date, decision):
        return PendingOutcome(
            ticker=ticker,
            trade_date=trade_date,
            decision=decision,
            raw_return=0.08,
            alpha_return=0.03,
            holding_days=5,
        )


def request() -> AnalysisRequest:
    return AnalysisRequest(
        ticker="NVDA",
        analysis_date=date(2026, 8, 2),
        requested_by="owner",
        session_id=uuid4(),
    )


def test_prepare_injects_resolved_pending_outcomes_and_prior_context():
    service = TradingMemoryService(RecordingLog(), FixedResolver())

    prepared = service.prepare(request())

    assert prepared.past_context == "Prior lessons for NVDA"
    assert prepared.pending_outcomes[0].alpha_return == 0.03


def test_complete_atomically_commits_reflection_then_current_decision():
    log = RecordingLog()
    service = TradingMemoryService(log, FixedResolver())
    result = WorkflowResult(
        ticker="NVDA",
        analysis_date=date(2026, 8, 2),
        signal="Hold",
        final_decision="Rating: Hold",
        structured={},
        reports={},
        memory_reflections=[
            MemoryReflection(
                ticker="NVDA",
                trade_date=date(2026, 7, 1),
                decision="Buy",
                raw_return=0.08,
                alpha_return=0.03,
                holding_days=5,
                reflection="The thesis held and outperformed.",
            )
        ],
    )

    service.complete(request(), result)

    assert log.updates[0]["reflection"] == "The thesis held and outperformed."
    assert log.decisions[0]["final_trade_decision"] == "Rating: Hold"
