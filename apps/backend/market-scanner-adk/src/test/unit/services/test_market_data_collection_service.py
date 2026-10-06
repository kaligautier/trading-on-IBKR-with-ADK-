"""The collection boundary preserves observations and rejects invalid series."""

import json
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from unittest.mock import Mock

import pytest

from app.dto.external.response.market_data_response_dto import (
    ClosingPrice,
    ClosingPriceHistory,
)
from app.models.market_assets import AssetCatalog
from app.models.step_01_external_market_data import (
    ExternalMarketAsset,
    ExternalMarketData,
)
from app.services.market_data_collection_service import MarketDataCollectionService
from app.services.market_data_trend_service import MarketDataTrendService
from app.utils.error import InvalidInputError, MarketDataCollectionError
from app.utils.wide_event import wide_event


def service_with(prices):
    client = Mock()
    client.fetch_closing_prices.side_effect = lambda *_: ClosingPriceHistory(prices)
    return MarketDataCollectionService(AssetCatalog(), client), client


def should_return_only_observations_and_provenance_without_rounding():
    today = date.today()
    prices = (ClosingPrice(today - timedelta(days=1), 100.123456789),)
    service, client = service_with(prices)
    collection = service.collect()
    assert isinstance(collection, ExternalMarketData)
    result = collection.model_dump(mode="json")["assets"]
    assert len(result) == 25
    assert client.fetch_closing_prices.call_count == 25
    asset = result["sp500"]
    assert set(asset) == {
        "name",
        "symbol",
        "kind",
        "unit",
        "source",
        "source_url",
        "retrieved_at",
        "status",
        "observations",
        "error",
        "value_field",
    }
    assert asset["observations"] == [
        {
            "observed_on": prices[0].observed_on.isoformat(),
            "value": 100.123456789,
        }
    ]
    assert asset["source"] == "Yahoo Finance"
    assert asset["value_field"] == "Close"
    assert asset["source_url"].startswith("https://")
    assert datetime.fromisoformat(asset["retrieved_at"]).tzinfo is not None
    assert json.loads(json.dumps(result, allow_nan=False)) == result


def should_preserve_debt_cents_through_json_and_validation():
    amount = Decimal("40073558531201.68")
    service, _ = service_with((ClosingPrice(date.today(), amount),))
    asset = service.collect().model_dump(mode="json")["assets"]["us_public_debt"]
    assert asset["observations"][0]["value"] == str(amount)
    reloaded = ExternalMarketAsset.model_validate(json.loads(json.dumps(asset)))
    assert MarketDataTrendService._validated_history(reloaded).latest.value == amount


@pytest.mark.parametrize(
    "prices",
    [
        (),
        (ClosingPrice(date.today() + timedelta(days=1), 100),),
        (ClosingPrice(date.today(), float("nan")),),
        (ClosingPrice(date.today(), float("inf")),),
        (ClosingPrice(date.today(), 100), ClosingPrice(date.today(), 101)),
    ],
)
def should_reject_empty_future_nonfinite_or_conflicting_data(prices):
    service, _ = service_with(prices)
    result = service.collect_asset(AssetCatalog().get("sp500"))
    assert result.status == "error"
    assert result.error
    assert result.observations == []


def should_sort_history_and_accept_identical_duplicates():
    today = date.today()
    service, _ = service_with(
        (
            ClosingPrice(today, 101),
            ClosingPrice(today - timedelta(days=1), 100),
            ClosingPrice(today, 101),
        )
    )
    result = service.collect_asset(AssetCatalog().get("sp500"))
    assert [p.value for p in result.observations] == [100, 101]


@pytest.mark.parametrize("age", [0, 10])
def should_keep_observations_without_adding_freshness_indicators(age):
    service, _ = service_with((ClosingPrice(date.today() - timedelta(days=age), 100),))
    result = service.collect_asset(AssetCatalog().get("sp500"))
    assert result.status == "success"
    assert "warnings" not in result.model_dump()


def should_preserve_tls_failures_without_a_fallback():
    from urllib.error import URLError

    service, default = service_with(())
    selected = Mock()
    selected.fetch_closing_prices.side_effect = URLError("certificate verify failed")
    service._clients_by_symbol["US_PUBLIC_DEBT"] = selected
    result = service.collect_asset(AssetCatalog().get("us_public_debt"))
    assert result.status == "error"
    assert "certificate" in result.error
    assert result.source == "U.S. Treasury"
    default.fetch_closing_prices.assert_not_called()


def should_record_collection_counts_separately_from_score_coverage():
    service, _ = service_with((ClosingPrice(date.today(), 100),))
    scope = wide_event.start({"event": "http.request"})
    try:
        service.collect()
        event = dict(wide_event.current() or {})
    finally:
        wide_event.reset(scope)
    assert event["market_data.requested_count"] == 25
    assert event["market_data.available_count"] == 25
    assert event["market_data.unavailable_count"] == 0


def should_reject_calculated_fields_in_the_raw_contract():
    service, _ = service_with((ClosingPrice(date.today(), 100),))
    raw = service.collect().model_dump(mode="json")["assets"]["sp500"]
    for field in ("horizons", "trend", "percentile_3y", "interpretation"):
        with pytest.raises(ValueError, match="Extra inputs"):
            ExternalMarketAsset.model_validate({**raw, field: {}})


def should_reject_future_observations_in_reloaded_snapshots():
    service, _ = service_with((ClosingPrice(date.today(), 100),))
    raw = service.collect().model_dump(mode="json")["assets"]["sp500"]
    raw["retrieved_at"] = datetime(2020, 1, 1, tzinfo=UTC).isoformat()
    with pytest.raises(InvalidInputError, match="future observation"):
        MarketDataTrendService().define_trend(
            ExternalMarketData(
                assets={"sp500": ExternalMarketAsset.model_validate(raw)}
            )
        )


def should_refuse_to_label_yahoo_observations_as_another_provider():
    from app.client.yahoo_finance_client import YahooFinanceClient

    ticker_factory = Mock()
    client = YahooFinanceClient(ticker_factory)
    service = MarketDataCollectionService(AssetCatalog(), client)
    result = service.collect_asset(AssetCatalog().get("us_public_debt"))
    assert result.status == "error"
    assert "provider_source_mismatch" in result.error
    assert result.observations == []
    ticker_factory.assert_not_called()


@pytest.mark.parametrize(
    "provider_error",
    [
        TimeoutError("Provider timed out"),
        MarketDataCollectionError("No usable history"),
    ],
)
def should_record_typed_collection_errors_and_continue_other_assets(provider_error):
    service, client = service_with((ClosingPrice(date.today(), 100),))

    def fetch(symbol, _period):
        if symbol == "^GSPC":
            raise provider_error
        return ClosingPriceHistory((ClosingPrice(date.today(), 100),))

    client.fetch_closing_prices.side_effect = fetch
    scope = wide_event.start()
    try:
        result = service.collect()
        errors = wide_event.current()["market_data.errors"]
    finally:
        wide_event.reset(scope)

    assert result.assets["sp500"].status == "error"
    assert result.assets["vix"].status == "success"
    failure = next(error for error in errors if error["symbol"] == "^GSPC")
    assert failure["error_code"] == "MARKET_DATA_COLLECTION_ERROR"
    assert failure["status_code"] == 502
    assert failure["message"] == result.assets["sp500"].error
