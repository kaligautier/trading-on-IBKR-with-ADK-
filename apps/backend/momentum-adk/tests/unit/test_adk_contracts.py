from datetime import date

import pytest

from app.domain.contracts import (
    AnalysisRequest,
    AnalystKind,
    SelectedAnalysts,
    WorkflowExecution,
)


def test_analysis_request_normalizes_ticker_and_preserves_selected_order():
    request = AnalysisRequest(
        ticker=" nvda ",
        analysis_date=date(2026, 8, 2),
        selected_analysts=["news", "market"],
        requested_by="user-42",
        session_id="d33d8f79-6a90-4aad-a7d7-d990ed341c47",
    )

    assert request.ticker == "NVDA"
    assert request.selected_analysts.values == (
        AnalystKind.NEWS,
        AnalystKind.MARKET,
    )


def test_selected_analysts_rejects_duplicates():
    with pytest.raises(ValueError, match="duplicate"):
        SelectedAnalysts(["market", "market"])


def test_selected_analysts_rejects_empty_collection():
    with pytest.raises(ValueError, match="at least one"):
        SelectedAnalysts([])


def request_data(**overrides):
    return {
        "ticker": " nvda ",
        "analysis_date": "2026-08-02",
        "requested_by": "operator",
        "session_id": "d33d8f79-6a90-4aad-a7d7-d990ed341c47",
        **overrides,
    }


def test_default_roles_and_execution_limits_are_preserved():
    request = AnalysisRequest.model_validate(request_data())

    assert request.selected_analysts.values == tuple(AnalystKind)
    assert request.max_debate_rounds == request.max_risk_discuss_rounds == 1
    assert request.output_language == "English"
    assert request.invocation_id is None
    assert request.pending_outcomes == ()


@pytest.mark.parametrize(
    "overrides",
    [
        {"ticker": None},
        {"ticker": 42},
        {"ticker": "../etc/passwd"},
        {"selected_analysts": []},
        {"selected_analysts": ["news", "news"]},
        {"selected_analysts": ["unknown"]},
        {"selected_analysts": None},
        {"selected_analysts": 42},
        {"selected_analysts": {"market": "invalid"}},
        {"analysis_date": "2026-02-30"},
        {"session_id": "invalid"},
        {"max_debate_rounds": 0},
        {"max_debate_rounds": 11},
        {"max_risk_discuss_rounds": 0},
        {"max_risk_discuss_rounds": 11},
    ],
)
def test_invalid_analysis_requests_raise_validation_errors(overrides):
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        AnalysisRequest.model_validate(request_data(**overrides))


def test_request_json_roundtrip_preserves_resume_and_memory():
    request = AnalysisRequest.model_validate(
        request_data(
            selected_analysts=["news", "market"],
            invocation_id="resume-1",
            output_language="French",
            past_context="Previous decision",
            pending_outcomes=[
                {
                    "ticker": "NVDA",
                    "trade_date": "2026-07-01",
                    "decision": "Hold",
                    "raw_return": 0.03,
                    "alpha_return": 0.01,
                    "holding_days": 32,
                }
            ],
        )
    )

    assert AnalysisRequest.model_validate_json(request.model_dump_json()) == request


def test_execution_json_roundtrip_preserves_results_and_correlation():
    execution = WorkflowExecution.model_validate(
        {
            "user_id": "operator",
            "session_id": request_data()["session_id"],
            "invocation_id": "invocation-1",
            "result": {
                "ticker": "NVDA",
                "analysis_date": "2026-08-02",
                "signal": "Hold",
                "final_decision": "Wait for confirmation",
                "structured": {"portfolio": {"rating": "Hold"}},
                "reports": {"news": "Earnings next week"},
                "next_analysis_date": "2026-08-09",
                "next_analysis_desc": "Review earnings",
                "run_stats": {"llm_calls": 8, "tokens_in": 1200},
                "memory_reflections": [],
            },
        }
    )

    restored = WorkflowExecution.model_validate_json(execution.model_dump_json())
    assert restored == execution
    assert restored.result.run_stats.llm_calls == 8
    assert restored.result.structured["portfolio"]["rating"] == "Hold"


@pytest.mark.parametrize("field", ["raw_return", "alpha_return"])
@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf")])
def test_outcome_returns_must_survive_json_roundtrip(field, value):
    from app.domain.contracts import PendingOutcome

    outcome = {
        "ticker": "AAPL",
        "trade_date": "2026-10-21",
        "decision": "Hold",
        "raw_return": 0.1,
        "alpha_return": 0.0,
        "holding_days": 5,
    }
    outcome[field] = value
    with pytest.raises(ValueError):
        PendingOutcome.model_validate(outcome)
