"""Typed financial sections and markdown outputs retained from Momentum."""

import pytest
from pydantic import ValidationError

from app.domain import analysis as a


@pytest.mark.parametrize(
    ("model", "renderer", "payload", "expected"),
    [
        (
            a.MarketAnalysis,
            a.render_market_analysis,
            {"rsi": {"value": 45, "signal": "Neutral"}},
            "**RSI** | 45.0 | Neutral",
        ),
        (
            a.FundamentalsAnalysis,
            a.render_fundamentals_analysis,
            {"pe_ratio": {"value": 20, "unit": "x"}},
            "**P/E** | 20.0 x",
        ),
        (
            a.SentimentAnalysis,
            a.render_sentiment_analysis,
            {"items": [{"topic": "earnings", "sentiment_score": 0.5}]},
            "earnings | 0.5",
        ),
        (
            a.NewsAnalysis,
            a.render_news_analysis,
            {"items": [{"headline": "Earnings published"}]},
            "Earnings published",
        ),
        (
            a.BullArgument,
            a.render_bull_argument,
            {"argument_full": "Growth thesis"},
            "Bull Analyst: Growth thesis",
        ),
        (
            a.BearArgument,
            a.render_bear_argument,
            {"argument_full": "Downside thesis"},
            "Bear Analyst: Downside thesis",
        ),
        (
            a.ResearchPlan,
            a.render_research_plan,
            {"recommendation": "Overweight"},
            "**Recommendation**: Overweight",
        ),
        (
            a.TraderProposal,
            a.render_trader_proposal,
            {"action": "Hold"},
            "FINAL TRANSACTION PROPOSAL: **HOLD**",
        ),
        (
            a.AggressiveArgument,
            a.render_aggressive_argument,
            {"argument_full": "Upside"},
            "Aggressive Analyst: Upside",
        ),
        (
            a.ConservativeArgument,
            a.render_conservative_argument,
            {"argument_full": "Risk"},
            "Conservative Analyst: Risk",
        ),
        (
            a.NeutralArgument,
            a.render_neutral_argument,
            {"argument_full": "Balance"},
            "Neutral Analyst: Balance",
        ),
        (
            a.PortfolioDecision,
            a.render_pm_decision,
            {"rating": "Underweight", "position_size": 0.05},
            "**Position Size**: 5%",
        ),
    ],
)
def test_financial_section_roundtrip_and_rendering(model, renderer, payload, expected):
    section = model.model_validate(payload)

    assert model.model_validate_json(section.model_dump_json()) == section
    assert expected in renderer(section)


@pytest.mark.parametrize(
    ("model", "payload"),
    [
        (a.ResearchPlan, {"recommendation": "Strong Buy"}),
        (a.PortfolioDecision, {"rating": "Unknown"}),
        (a.TraderProposal, {"action": "Overweight"}),
        (a.MarketAnalysis, {"rsi": {"value": "invalid"}}),
        (a.FundamentalsAnalysis, {"pe_ratio": {"value": "invalid"}}),
    ],
)
def test_invalid_financial_values_are_rejected(model, payload):
    with pytest.raises(ValidationError):
        model.model_validate(payload)
