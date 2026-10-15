"""New decisions require a concise summary; historical reports remain readable."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.models.market_regime import MarketRegime
from app.models.market_report import ReportArbitration
from app.models.structured_output.unsourced_market_analysis import (
    UnsourcedMarketAnalysis,
)
from test.report_fixtures import arbitration_payload, unsourced_analysis_payload

EXAMPLE = Path(__file__).resolve().parents[3] / "examples" / "report-v3.json"


@pytest.mark.parametrize("missing", [False, True])
def should_require_new_arbitration_without_fabricating_it_for_old_reports(missing):
    new_analysis = unsourced_analysis_payload(["sp500"])
    old_report = json.loads(EXAMPLE.read_text())["market_regime"]
    for payload in (new_analysis, old_report):
        if missing:
            payload.pop("arbitration")
        else:
            payload["arbitration"] = None

    with pytest.raises(ValidationError, match="arbitration"):
        UnsourcedMarketAnalysis.model_validate(new_analysis)
    assert MarketRegime.model_validate(old_report).arbitration is None


@pytest.mark.parametrize(
    "field, value",
    [
        ("decision_rationale", ""),
        ("decision_rationale", "   "),
        ("decision_rationale", "x" * 501),
        ("main_counterargument", ""),
        ("main_counterargument", "x" * 501),
        ("supporting_factors", []),
        ("supporting_factors", ["Observation"] * 4),
        ("supporting_factors", ["   "]),
        ("supporting_factors", ["x" * 501]),
        ("invalidation_conditions", ["Condition"] * 4),
        ("invalidation_conditions", [""]),
        ("invalidation_conditions", ["x" * 501]),
    ],
)
def should_reject_empty_or_excessive_arbitration(field, value):
    payload = arbitration_payload()
    payload[field] = value
    with pytest.raises(ValidationError, match="Arbitration"):
        ReportArbitration.model_validate(payload)


def should_allow_no_supported_invalidation_condition():
    payload = unsourced_analysis_payload(["sp500"])
    payload["arbitration"]["invalidation_conditions"] = []
    analysis = UnsourcedMarketAnalysis.model_validate(payload)
    assert analysis.arbitration.invalidation_conditions == []
    assert (
        analysis.arbitration.decision_rationale
        == payload["arbitration"]["decision_rationale"]
    )


def should_reject_citations_and_internal_critique_in_the_public_summary():
    payload = arbitration_payload()
    payload["decision_rationale"] = "See https://example.org/report"
    with pytest.raises(ValidationError, match="source_ids"):
        ReportArbitration.model_validate(payload)
    payload = arbitration_payload()
    payload["research_critique"] = {"challenges": []}
    with pytest.raises(ValidationError, match="extra_forbidden"):
        ReportArbitration.model_validate(payload)
