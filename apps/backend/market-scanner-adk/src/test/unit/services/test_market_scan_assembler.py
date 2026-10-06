"""Contract and evidence failures must stop before publication or persistence."""

import json
from datetime import date

import pytest
from pydantic import ValidationError

from app.config.constants import ASSET_ENTRIES
from app.models.market_assets import MarketDataCollection
from app.models.market_report import ASSET_FAMILIES, ResearchSource
from app.models.structured_output.market_analysis import MarketAnalysis
from app.services.market_scan_assembler import (
    MarketScanAssembler,
    MarketScanAssemblyError,
)
from test.report_fixtures import analysis_payload


def data_for(keys=("sp500",)):
    return MarketDataCollection.from_json(
        json.dumps(
            {
                key: {
                    "name": ASSET_ENTRIES[key][1],
                    "symbol": ASSET_ENTRIES[key][0],
                    "status": "success",
                    "value": 110,
                    "observed_on": date.today().isoformat(),
                    "trend": None,
                    "horizons": {
                        "1d": {"change_pct": 10, "ref_price": 100, "trend": "rising"},
                        "ytd": None,
                    },
                }
                for key in keys
            }
        )
    )


def assemble(payload, data=None, sources=None):
    return MarketScanAssembler().assemble_regime(
        data or data_for(), MarketAnalysis.model_validate(payload), sources
    )


def should_cover_25_assets_once_in_six_families_and_preserve_observations():
    result = assemble(analysis_payload(ASSET_ENTRIES), data_for(ASSET_ENTRIES))
    assert len(result.assets) == 25
    assert len(result.themes) == 6
    assert {key for group in ASSET_FAMILIES.values() for key in group} == set(
        ASSET_ENTRIES
    )
    assert sorted(key for theme in result.themes for key in theme.asset_keys) == sorted(
        ASSET_ENTRIES
    )
    assert result.scope.available == 25
    assert result.scope.observation_dates == [date.today()]
    for asset in result.assets:
        assert asset.value == 110
        assert asset.horizons["1d"].change_pct == 10
        assert asset.trend is None
    assert result.schema_version == 3
    assert list(result.model_dump()).index("summary") < list(result.model_dump()).index(
        "assets"
    )
    assert "recommendation" not in result.model_dump()


@pytest.mark.parametrize(
    "mutation, message",
    [
        ("duplicate", "Duplicate"),
        ("missing", "missing"),
        ("unknown", "unknown"),
        ("family", "Theme"),
        ("horizon", "horizon"),
    ],
)
def should_reject_incomplete_or_invented_observations(mutation, message):
    payload = analysis_payload(["sp500", "vix"])
    if mutation == "duplicate":
        payload["asset_insights"].append(payload["asset_insights"][0])
    if mutation == "missing":
        payload["asset_insights"].pop()
    if mutation == "unknown":
        payload["asset_insights"][0]["asset_key"] = "invented"
    if mutation == "family":
        payload["themes"].pop()
    if mutation == "horizon":
        payload["asset_insights"][0]["horizon"] = "ytd"
    with pytest.raises(MarketScanAssemblyError, match=message):
        assemble(payload, data_for(["sp500", "vix"]))


@pytest.mark.parametrize(
    "field, value",
    [
        ("recommendation", "aggressive"),
        ("regime_probabilities", {"risk_on": 0.9}),
        ("sources", [{"id": "S1", "url": "https://invented.test"}]),
    ],
)
def should_reject_advice_probabilities_and_llm_authored_source_records(field, value):
    payload = analysis_payload(["sp500"])
    payload[field] = value
    with pytest.raises(ValidationError, match="Extra inputs"):
        MarketAnalysis.model_validate(payload)


@pytest.mark.parametrize("text", ["See https://invented.test", "Assertion [1.3.1]"])
def should_reject_inline_urls_and_unresolvable_citation_markers(text):
    payload = analysis_payload(["sp500"])
    payload["summary"] = text
    with pytest.raises(ValidationError, match="source_ids"):
        MarketAnalysis.model_validate(payload)


def should_bind_documented_explanations_to_provider_supports():
    payload = analysis_payload(["sp500"])
    interpretation = payload["asset_insights"][0]["interpretation"]
    interpretation.update(status="documented", source_ids=["S1"])
    with pytest.raises(MarketScanAssemblyError, match="Unknown research source"):
        assemble(payload)
    source = ResearchSource(id="S1", title="Bulletin", url="https://example.org/report")
    with pytest.raises(MarketScanAssemblyError, match="without grounding support"):
        assemble(payload, sources=[source])
    source.supported_claims = ["A dated factual statement."]
    result = assemble(payload, sources=[source])
    assert result.sources == [source]
    assert result.assets[0].interpretation.source_ids == ["S1"]


def should_reject_documented_interpretation_without_any_source_id():
    payload = analysis_payload(["sp500"])
    payload["asset_insights"][0]["interpretation"]["status"] = "documented"
    with pytest.raises(ValidationError, match="requires source_ids"):
        assemble(payload)


def should_keep_a_successful_asset_with_no_computable_history():
    data = data_for(["vixeq"])
    data.available_asset("vixeq").horizons = {"1d": None, "ytd": None}
    result = assemble(analysis_payload(["vixeq"], horizon="level"), data)
    assert result.assets[0].trend is None
    assert result.assets[0].horizons["1d"] is None


@pytest.mark.parametrize("trend", ["rising", "falling", "stable", None])
def should_preserve_ytd_without_a_vote(trend):
    data = data_for()
    data.available_asset("sp500").trend = trend
    assert assemble(analysis_payload(["sp500"]), data).assets[0].trend == trend
