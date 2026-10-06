"""The model schema goes directly to Gemini without request callbacks."""

import json

import pytest
from pydantic import ValidationError

from app.models.structured_output.market_analysis import MarketAnalysis
from test.report_fixtures import analysis_payload


def should_expose_a_provider_compatible_output_schema_directly():
    schema = json.dumps(MarketAnalysis.model_json_schema())
    for keyword in ("minLength", "maxLength", "minItems", "maxItems"):
        assert keyword not in schema
    assert '"required"' in schema and '"enum"' in schema
    MarketAnalysis.model_validate(analysis_payload(["sp500"]))


def should_keep_regime_and_source_validation():
    payload = analysis_payload(["sp500"])
    payload["regime"] = "invented"
    with pytest.raises(ValidationError):
        MarketAnalysis.model_validate(payload)
    payload["regime"] = "cautious"
    payload["asset_insights"][0]["interpretation"]["status"] = "documented"
    with pytest.raises(ValidationError, match="requires source_ids"):
        MarketAnalysis.model_validate(payload)


def should_supply_financial_rules_without_before_model_callbacks():
    from app.components.agents.market_scanner.agent import researcher, synthesizer

    for agent in (researcher, synthesizer):
        assert agent.before_model_callback is None
        assert "capitalization-weighted" in agent.instruction
        assert "Only analyse assets with status success" in agent.instruction
