import pytest
from pydantic import ValidationError

from app.domain.rating import RATINGS_5_TIER, parse_rating
from app.domain.state import (
    AnalystReports,
    NextAnalysisRecommendation,
    PortfolioOutcome,
    ReflectionText,
    ResearchOutcome,
    RiskOutcome,
    TraderOutcome,
)


@pytest.mark.parametrize("rating", RATINGS_5_TIER)
def test_parse_all_five_portfolio_ratings(rating):
    assert parse_rating(f"**Rating**: **{rating}**") == rating


def test_parse_rating_defaults_to_hold_without_a_label():
    assert parse_rating("No clear directional signal.") == "Hold"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("rating - **overweight**", "Overweight"),
        ("Rating: SELL", "Sell"),
        ("Buy scenario.\nRating: Underweight", "Underweight"),
        ("We recommend **Hold**.", "Hold"),
        ("An overweight position.", "Overweight"),
        ("No signal", "Hold"),
    ],
)
def test_normalization_preserves_label_priority_and_prose_fallback(text, expected):
    assert parse_rating(text) == expected


def test_every_workflow_state_keeps_its_upstream_financial_sections():
    reports = AnalystReports.model_validate(
        {
            "request": {
                "ticker": "nvda",
                "analysis_date": "2026-10-20",
                "requested_by": "operator",
                "session_id": "d33d8f79-6a90-4aad-a7d7-d990ed341c47",
                "invocation_id": "resume-1",
                "selected_analysts": ["news", "market"],
            },
            "market": {"rsi": {"value": 45}},
            "news": {"items": [{"headline": "Quarterly earnings"}]},
        }
    )
    research = ResearchOutcome(
        reports=reports,
        bull_arguments=[{"thesis": "Growth"}],
        bear_arguments=[{"thesis": "Valuation"}],
        plan={"recommendation": "Overweight"},
    )
    trader = TraderOutcome(research=research, proposal={"action": "Buy"})
    risk = RiskOutcome(
        trader=trader,
        aggressive_arguments=[{"stance": "Add"}],
        conservative_arguments=[{"stance": "Limit"}],
        neutral_arguments=[{"stance": "Balance"}],
    )
    portfolio = PortfolioOutcome(risk=risk, decision={"rating": "Hold"})

    restored = PortfolioOutcome.model_validate_json(portfolio.model_dump_json())
    assert restored == portfolio
    assert restored.risk.trader.research.reports.request.invocation_id == "resume-1"
    assert restored.risk.trader.research.reports.market.rsi.value == 45
    assert restored.risk.trader.research.reports.fundamentals is None
    assert restored.risk.conservative_arguments[0].stance == "Limit"


def test_typed_state_rejects_a_missing_research_decision():
    with pytest.raises(ValidationError):
        ResearchOutcome.model_validate({"reports": {}, "plan": {}})


def test_recommendation_and_reflection_keep_their_typed_output():
    next_analysis = NextAnalysisRecommendation.model_validate(
        {"analysis_date": "2026-10-27", "description": "Review earnings"}
    )
    reflection = ReflectionText(reflection="Size the next position conservatively")

    assert next_analysis.analysis_date.isoformat() == "2026-10-27"
    assert reflection.model_dump()["reflection"].startswith("Size the next")
