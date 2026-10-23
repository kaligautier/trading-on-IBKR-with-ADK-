from datetime import UTC, date, datetime
from uuid import UUID

import pytest

from app.assembly import InvalidStoredAnalysisError, StoredAnalysis, detail, summary


def stored(sections=None, **changes):
    return StoredAnalysis(
        header={
            "id": UUID(int=1),
            "ticker": "AAPL",
            "analysis_date": date(2026, 10, 22),
            "created_at": datetime(2026, 10, 22, tzinfo=UTC),
            "llm_provider": "gateway",
            "quick_think_llm": "quick",
            "deep_think_llm": "deep",
            "next_analysis_date": None,
            "next_analysis_desc": None,
            "user_id": "private-user",
            "session_id": "private-session",
            "invocation_id": "private-invocation",
            **changes,
        },
        sections=sections or {},
    )


def test_empty_sections_and_no_internal_fields():
    output = detail(stored()).model_dump(mode="json")
    assert output["created_at"] == "2026-10-22T00:00:00Z"
    assert output["technical_indicators"] is None
    assert output["debate_arguments"] == []
    assert output["run_stats"] is None
    assert not {"user_id", "session_id", "invocation_id"}.intersection(output)
    assert summary(stored()).rating is None


def test_aliases_numbers_and_item_order_are_preserved():
    row = stored(
        {
            "technical_indicators": [
                {
                    "id": UUID(int=2),
                    "rsi": 65.5,
                    "macd_signal_state": "rising",
                    "future_secret": "hidden",
                }
            ],
            "sentiment_results": [{"id": UUID(int=3), "overall_sentiment": None}],
            "sentiment_items": [
                {
                    "id": UUID(int=5),
                    "topic": "second",
                    "sentiment_score": None,
                    "impact": "low",
                    "comment": "unknown",
                },
                {
                    "id": UUID(int=4),
                    "topic": "first",
                    "sentiment_score": 0.8,
                    "impact": "high",
                    "comment": "observed",
                },
            ],
            "debate_arguments": [
                {
                    "id": UUID(int=7),
                    "debate_type": "risk",
                    "role": "bull",
                    "round_number": 1,
                    "conviction_level": "high",
                },
                {
                    "id": UUID(int=6),
                    "debate_type": "investment",
                    "role": "bear",
                    "round_number": 1,
                },
            ],
        }
    )
    output = detail(row).model_dump(mode="json")
    assert output["technical_indicators"]["macd_signal"] == "rising"
    assert output["technical_indicators"]["rsi"] == 65.5
    assert "future_secret" not in output["technical_indicators"]
    assert [item["topic"] for item in output["sentiment"]["items"]] == [
        "first",
        "second",
    ]
    assert output["sentiment"]["items"][1]["score"] is None
    assert output["debate_arguments"][0]["round"] == 1
    assert output["debate_arguments"][1]["conviction"] == "high"
    assert summary(row).rsi == 65.5


def test_summary_uses_portfolio_and_trader_projections():
    row = stored(
        {
            "portfolio_decisions": [
                {
                    "id": UUID(int=2),
                    "rating": "Sell",
                    "price_target": 180.5,
                    "position_size": None,
                }
            ],
            "trader_proposals": [
                {
                    "id": UUID(int=3),
                    "action": "SELL",
                    "entry_price": 190.0,
                    "stop_loss": 195.0,
                }
            ],
        }
    )
    output = summary(row)
    assert output.rating == "Sell"
    assert output.price_target == 180.5
    assert output.trader_entry == 190.0
    assert output.trader_stop == 195.0
    assert output.position_size is None


@pytest.mark.parametrize("number", [float("nan"), float("inf"), float("-inf")])
def test_invalid_stored_numbers_are_not_replaced(number):
    row = stored({"technical_indicators": [{"id": UUID(int=2), "rsi": number}]})
    for assembler in (detail, summary):
        with pytest.raises(InvalidStoredAnalysisError):
            assembler(row)


def test_required_header_and_duplicate_single_sections_fail():
    with pytest.raises(InvalidStoredAnalysisError):
        detail(stored(created_at=None))
    row = stored({"technical_indicators": [{"id": UUID(int=2)}, {"id": UUID(int=3)}]})
    for assembler in (detail, summary):
        with pytest.raises(InvalidStoredAnalysisError):
            assembler(row)
