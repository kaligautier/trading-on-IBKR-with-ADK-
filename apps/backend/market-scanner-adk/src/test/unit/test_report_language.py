"""The public English contract and the active agent instructions stay aligned."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.config.constants import (
    ASSET_WEB_RESEARCHER_INSTRUCTION,
    MARKET_RESEARCH_CRITIC_INSTRUCTION,
    MARKET_SYNTHESIZER_INSTRUCTION,
)
from app.models.market_regime import MarketRegime
from app.models.step_04_market_data import MarketData

EXAMPLE = Path(__file__).resolve().parents[3] / "examples" / "report-v3.json"


def should_publish_the_documented_english_v3_contract():
    payload = json.loads(EXAMPLE.read_text())
    parsed = MarketData.model_validate(payload)
    report = parsed.model_dump(mode="json")["market_regime"]
    assert report == payload["market_regime"]
    assert report["schema_version"] == 3
    assert set(report) == {
        "title",
        "summary",
        "macro_overview",
        "regime",
        "horizon",
        "limitations",
        "watch_points",
        "schema_version",
        "scope",
        "themes",
        "assets",
        "sources",
        "data_quality",
    }
    assert set(report["scope"]) == {
        "requested",
        "available",
        "observation_dates",
        "unavailable",
        "stale",
    }
    assert report["regime"] == "cautious"
    assert report["themes"][0]["family"] == "equities"
    asset = report["assets"][0]
    assert asset["observation"] == "One-day observation."
    assert asset["horizons"]["1d"]["trend"] == "rising"
    assert asset["interpretation"] == {
        "text": "No verified catalyst in this synthetic data.",
        "status": "unestablished",
        "source_ids": [],
    }


def should_not_mislabel_a_report_as_the_previous_schema_version():
    report = json.loads(EXAMPLE.read_text())["market_regime"]
    report["schema_version"] = 2
    with pytest.raises(ValidationError, match="schema_version"):
        MarketRegime.model_validate(report)


def should_request_english_in_all_active_agent_instructions():
    assert "Write concise English prose" in ASSET_WEB_RESEARCHER_INSTRUCTION
    assert "Write concise English" in MARKET_RESEARCH_CRITIC_INSTRUCTION
    assert "Write a clear English market diagnosis" in MARKET_SYNTHESIZER_INSTRUCTION


@pytest.mark.parametrize("field", ["claim_ids", "research_evidence_audit"])
def should_reject_internal_evidence_fields_in_public_report(field):
    payload = json.loads(EXAMPLE.read_text())
    if field == "claim_ids":
        payload["market_regime"]["assets"][0]["interpretation"][field] = ["C1"]
    else:
        payload["market_regime"][field] = {"assets": {}, "themes": {}}
    with pytest.raises(ValidationError, match="extra_forbidden"):
        MarketData.model_validate(payload)
