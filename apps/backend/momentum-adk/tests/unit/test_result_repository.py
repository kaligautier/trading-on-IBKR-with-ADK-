"""Preserved financial mappings and required execution correlation."""

from datetime import date
from uuid import uuid4

import pytest

from app.domain.contracts import WorkflowExecution, WorkflowResult
from app.infrastructure.models import (
    AnalysisResult,
    DebateArgumentRow,
    Fundamentals,
    PortfolioDecisionRow,
    TechnicalIndicators,
    TraderProposalRow,
)
from app.infrastructure.result_writer import ModelMetadata, PostgresResultWriter


class RecordingSession:
    def __init__(self):
        self.rows = []

    def add(self, row):
        self.rows.append(row)

    async def flush(self):
        for row in self.rows:
            if row.id is None:
                row.id = uuid4()


def execution():
    return WorkflowExecution(
        user_id="operator",
        session_id="session",
        invocation_id="invocation",
        result=WorkflowResult(
            ticker="NVDA",
            analysis_date=date(2026, 1, 1),
            signal="Buy",
            final_decision="Buy",
            reports={},
            structured={
                "Market Analyst": {
                    "close_price": {
                        "value": 180,
                        "signal": "Bullish",
                        "interpretation": "Above support",
                    }
                },
                "Portfolio Manager": {"rating": "Buy", "price_target": 220},
                "Fundamentals Analyst": {"market_cap": {"value": 12, "unit": "Bn USD"}},
                "Bull Researcher": {"target_price": 0, "downside_target": 99},
            },
        ),
    )


async def test_writer_preserves_source_fields_and_adds_correlation():
    session = RecordingSession()
    writer = PostgresResultWriter(ModelMetadata("litellm", "deep", "quick"))
    await writer.write(session, execution())
    parent = next(r for r in session.rows if isinstance(r, AnalysisResult))
    assert (parent.user_id, parent.session_id, parent.invocation_id) == (
        "operator",
        "session",
        "invocation",
    )
    assert all(r.result_id == parent.id for r in session.rows if r is not parent)
    market = next(r for r in session.rows if isinstance(r, TechnicalIndicators))
    assert (market.close_price, market.close_signal, market.close_comment) == (
        180,
        "Bullish",
        "Above support",
    )
    portfolio = next(r for r in session.rows if isinstance(r, PortfolioDecisionRow))
    assert (portfolio.rating, portfolio.price_target) == ("Buy", 220)
    fundamentals = next(r for r in session.rows if isinstance(r, Fundamentals))
    assert fundamentals.market_cap_unit == "Bn USD"
    debate = next(r for r in session.rows if isinstance(r, DebateArgumentRow))
    assert debate.target_price == 0


@pytest.mark.parametrize(
    "field,value",
    [
        ("user_id", ""),
        ("session_id", " "),
        ("invocation_id", ""),
        ("user_id", "x" * 129),
        ("session_id", "x" * 129),
        ("invocation_id", "x" * 257),
    ],
)
async def test_writer_rejects_missing_or_oversized_correlation(field, value):
    session = RecordingSession()
    item = execution().model_copy(update={field: value})
    with pytest.raises(ValueError, match="execution correlation"):
        await PostgresResultWriter(ModelMetadata("litellm", "deep", "quick")).write(
            session, item
        )
    assert session.rows == []


@pytest.mark.parametrize("reasoning", [None, "", "Evidence-based rationale"])
async def test_optional_trader_reasoning_matches_nonnullable_storage(reasoning):
    session = RecordingSession()
    item = execution()
    item.result.structured["Trader"] = {"action": "Hold", "reasoning": reasoning}
    await PostgresResultWriter(ModelMetadata("litellm", "deep", "quick")).write(
        session, item
    )
    trader = next(row for row in session.rows if isinstance(row, TraderProposalRow))
    assert trader.reasoning == (reasoning or "")
