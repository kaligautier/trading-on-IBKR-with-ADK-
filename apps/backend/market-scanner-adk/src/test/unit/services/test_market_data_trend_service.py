"""Compute indicators from snapshots without contacting market data providers."""

import copy
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest

from app.models.market_assets import AssetCatalog
from app.models.step_01_external_market_data import (
    ExternalMarketAsset,
    ExternalMarketData,
    ExternalMarketObservation,
)
from app.models.step_03_analysed_market_data import AnalysedMarketData
from app.models.structured_output.market_analysis import MarketAnalysis
from app.services.market_data_trend_service import MarketDataTrendService
from app.services.market_scan_assembler import MarketScanAssembler
from app.utils.error import ErrorCode, InvalidInputError


def snapshot(key, *prices, error=None):
    asset = AssetCatalog().get(key)
    return ExternalMarketAsset(
        name=asset.name,
        symbol=asset.symbol,
        kind=asset.kind,
        unit=asset.unit,
        source=asset.source,
        source_url=asset.source_url,
        value_field="Close",
        retrieved_at=datetime.now(UTC),
        status="error" if error else "success",
        error=error,
        observations=[
            ExternalMarketObservation(
                observed_on=day,
                value=str(value) if isinstance(value, Decimal) else value,
            )
            for day, value in prices
        ],
    )


def compute(key, *prices):
    data = ExternalMarketData(assets={key: snapshot(key, *prices)})
    before = copy.deepcopy(data)
    result = (
        MarketDataTrendService().define_trend(data).model_dump(mode="json")["assets"]
    )
    assert data == before
    return result[key]


@pytest.mark.parametrize("value", ["not-a-number", "NaN", "Infinity"])
def should_wrap_invalid_observations_with_asset_context_and_original_cause(value):
    asset = snapshot("sp500", (date(2026, 8, 14), value))
    with pytest.raises(InvalidInputError) as caught:
        MarketDataTrendService().define_trend(
            ExternalMarketData(assets={"sp500": asset})
        )
    error = caught.value
    assert error.error_code == ErrorCode.INVALID_INPUT
    assert error.details["symbol"] == "^GSPC"
    assert error.__cause__ is not None
    assert error.details["cause_type"] == type(error.__cause__).__name__


def should_compute_trends_from_a_snapshot_without_modifying_observations():
    result = compute("sp500", (date(2026, 8, 13), 100), (date(2026, 8, 14), 102))
    assert result["value"] == 102
    assert result["trend"] is None
    assert result["horizons"]["1d"] == {
        "change_pct": 2.0,
        "ref_price": 100.0,
        "trend": "rising",
    }


@pytest.mark.parametrize("numeric_type", [float, Decimal])
@pytest.mark.parametrize(
    ("current", "expected_trend"),
    [("100.001", "rising"), ("99.999", "falling"), ("100", "stable")],
)
def should_classify_small_changes_before_rounding(
    numeric_type, current, expected_trend
):
    result = compute(
        "sp500",
        (date(2026, 8, 13), numeric_type("100")),
        (date(2026, 8, 14), numeric_type(current)),
    )
    assert result["horizons"]["1d"]["trend"] == expected_trend
    assert result["horizons"]["1d"]["change_pct"] == 0.0


def should_classify_each_horizon_independently_without_thresholds():
    result = compute(
        "sp500",
        (date(2026, 8, 7), 100.2),
        (date(2026, 8, 13), 100),
        (date(2026, 8, 14), 100.1),
    )
    assert result["horizons"]["1d"]["trend"] == "rising"
    assert result["horizons"]["1w"]["trend"] == "falling"
    assert result["horizons"]["1m"] is None


@pytest.mark.parametrize(
    ("reference", "current", "expected_trend"),
    [(-100, -99, "rising"), (-100, -101, "falling"), (0, 1, "rising")],
)
def should_compare_values_even_with_nonpositive_references(
    reference, current, expected_trend
):
    result = compute(
        "sp500",
        (date(2026, 8, 13), reference),
        (date(2026, 8, 14), current),
    )
    assert result["horizons"]["1d"]["trend"] == expected_trend


def should_preserve_provider_errors_without_fabricating_indicators():
    raw = ExternalMarketData(
        assets={"sp500": snapshot("sp500", error="provider unavailable")}
    )
    result = (
        MarketDataTrendService()
        .define_trend(raw)
        .model_dump(mode="json")["assets"]["sp500"]
    )
    assert result["status"] == "error"
    assert result["error"] == "provider unavailable"
    assert result["horizons"] == {}
    assert result["value"] is None and result["trend"] is None


def should_keep_a_current_value_when_history_is_too_short():
    result = compute("vixeq", (date(2026, 8, 14), 37.72))
    assert result["value"] == 37.72
    assert all(horizon is None for horizon in result["horizons"].values())
    assert result["trend"] is None


@pytest.mark.parametrize("numeric_type", [float, Decimal])
@pytest.mark.parametrize(
    ("year_end", "expected_trend"),
    [("110", "falling"), ("90", "rising"), ("100", "stable")],
)
def should_use_only_ytd_for_the_overall_trend(numeric_type, year_end, expected_trend):
    result = compute(
        "sp500",
        (date(2025, 12, 31), numeric_type(year_end)),
        (date(2026, 1, 2), numeric_type("80")),
        (date(2026, 6, 1), numeric_type("85")),
        (date(2026, 8, 7), numeric_type("95")),
        (date(2026, 8, 13), numeric_type("99")),
        (date(2026, 8, 14), numeric_type("100")),
    )
    assert result["horizons"]["1d"]["trend"] == "rising"
    assert result["horizons"]["1w"]["trend"] == "rising"
    assert result["horizons"]["ytd"]["ref_price"] == (
        year_end if numeric_type is Decimal else float(year_end)
    )
    assert result["horizons"]["ytd"]["trend"] == expected_trend
    assert result["trend"] == expected_trend


def should_anchor_ytd_to_the_observation_year_and_last_available_year_end_close():
    result = compute(
        "sp500",
        (date(2023, 12, 29), 100),
        (date(2024, 1, 1), 105),
        (date(2024, 2, 29), 110),
    )
    assert result["horizons"]["ytd"] == {
        "change_pct": 10.0,
        "ref_price": 100.0,
        "trend": "rising",
    }


def should_leave_ytd_and_overall_trend_unavailable_without_a_year_end_reference():
    result = compute("sp500", (date(2026, 1, 1), 100), (date(2026, 1, 2), 101))
    assert result["horizons"]["1d"]["trend"] == "rising"
    assert result["horizons"]["ytd"] is None
    assert result["trend"] is None


def should_keep_static_guidance_out_of_computed_data():
    raw = ExternalMarketData(
        assets={
            key: snapshot(key, (date(2026, 8, 14), 37.72)) for key in ("dspx", "vixeq")
        }
    )
    result = (
        MarketDataTrendService().define_trend(raw).model_dump(mode="json")["assets"]
    )
    assert all("interpretation" not in asset for asset in result.values())
    assert all(
        "interpretation" not in asset for asset in raw.model_dump()["assets"].values()
    )


def should_use_calendar_years_for_assets_traded_every_day():
    first_day = date(2025, 8, 14)
    prices = [
        (first_day + timedelta(days=offset), 100.0 + offset) for offset in range(366)
    ]
    assert compute("bitcoin", *prices)["horizons"]["1y"]["ref_price"] == 100


def should_use_the_last_close_before_a_calendar_target():
    result = compute(
        "sp500",
        (date(2026, 7, 9), 90),
        (date(2026, 8, 3), 95),
        (date(2026, 8, 10), 100),
    )
    assert result["horizons"]["1m"]["ref_price"] == 90


def should_normalize_against_prior_observations_only_with_midrank_ties():
    current = date(2026, 9, 11)
    prices = [(current - timedelta(days=offset), 20) for offset in range(1, 253)] + [
        (current, 20)
    ]
    result = compute("vix", *prices)
    assert result["percentile_3y"] == 0.5
    assert result["history_points_3y"] == 252
    assert result["observed_on"] == "2026-09-11"


def should_exclude_history_older_than_three_calendar_years():
    result = compute(
        "vix", (date(2020, 1, 1), 100), (date(2026, 9, 10), 10), (date(2026, 9, 11), 20)
    )
    assert result["history_points_3y"] == 1
    assert result["percentile_3y"] is None


def should_preserve_exact_debt_amounts_in_the_existing_output_contract():
    amount = Decimal("40073558531201.68")
    result = compute("us_public_debt", (date(2026, 9, 23), amount))
    assert result["value"] == str(amount)
    assert result["unit"] == "USD"


def should_compute_an_independent_model_without_observations():
    data = ExternalMarketData(
        assets={
            "sp500": snapshot(
                "sp500",
                (date(2026, 8, 13), 100.123456789),
                (date(2026, 8, 14), 102.123456789),
            )
        }
    )
    original = data.model_dump(mode="json")
    computed = MarketDataTrendService().define_trend(data)
    enriched = computed.model_dump(mode="json")["assets"]["sp500"]
    for field, value in original["assets"]["sp500"].items():
        if field != "observations":
            assert enriched[field] == value
    assert {"horizons", "trend", "percentile_3y"} <= enriched.keys()
    assert "observations" not in enriched
    assert not isinstance(computed, ExternalMarketData)
    computed.assets["sp500"].horizons["1d"].change_pct = 999
    assert data.model_dump(mode="json") == original


def should_keep_only_identity_and_analysis_without_changing_market_data():
    external = ExternalMarketData(
        assets={
            "us_public_debt": snapshot(
                "us_public_debt",
                (date(2026, 8, 13), Decimal("39000000000000.05")),
                (date(2026, 8, 14), Decimal("40047726949770.15")),
            ),
            "sp500": snapshot("sp500", error="source unavailable"),
        }
    )
    trends = MarketDataTrendService().define_trend(external)
    original = trends.model_dump(mode="json")
    from test.report_fixtures import analysis_payload

    payload = analysis_payload(["us_public_debt"])
    payload["asset_insights"][0]["observation"] = "Debt is increasing."
    analysis = MarketAnalysis.model_validate(payload)
    analysed = MarketScanAssembler().enrich(trends, analysis)

    assert isinstance(analysed, AnalysedMarketData)
    assert not isinstance(analysed, type(trends))
    for key, asset in analysed.assets.items():
        assert asset.model_dump(mode="json", exclude={"insight"}) == {
            field: original["assets"][key][field] for field in ("name", "symbol")
        }
    assert analysed.assets["sp500"].insight is None
    assert (
        analysed.assets["us_public_debt"].insight.observation == "Debt is increasing."
    )
    assert "observations" not in analysed.assets["us_public_debt"].model_dump()
    analysed.assets["us_public_debt"].name = "Changed identity"
    assert trends.model_dump(mode="json") == original
    assert (
        external.assets["us_public_debt"].observations[0].value == "39000000000000.05"
    )
