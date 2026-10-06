"""Keep provider selection and failure behavior stable in the scanner workflow."""

from datetime import date

import pytest

from app.client.treasury_client import TreasuryClient
from app.client.yahoo_finance_client import YahooFinanceClient
from app.components.agents.market_scanner import agent as scanner
from app.dto.external.response.market_data_response_dto import (
    ClosingPrice,
    ClosingPriceHistory,
)
from app.models.market_assets import AssetCatalog

PROVIDERS = (YahooFinanceClient, TreasuryClient)


@pytest.mark.parametrize(
    ("symbol", "expected_provider"),
    [
        ("^GSPC", YahooFinanceClient),
        ("US_PUBLIC_DEBT", TreasuryClient),
    ],
)
def should_collect_each_instrument_from_its_configured_provider(
    monkeypatch, symbol, expected_provider
):
    requests = []

    def fetch(client, symbol, period):
        requests.append((type(client), symbol, period))
        return ClosingPriceHistory((ClosingPrice(date(2026, 9, 11), 100.0),))

    for provider in PROVIDERS:
        monkeypatch.setattr(provider, "fetch_closing_prices", fetch)

    result = scanner.market_data_collection_service.collect_asset(
        next(a for a in AssetCatalog().all().values() if a.symbol == symbol)
    )

    assert requests == [(expected_provider, symbol, "10y")]
    assert result.status == "success"
    assert result.observations[0].value == 100.0


def should_report_a_provider_failure_without_switching_sources(monkeypatch):
    requests = []

    def fetch(client, symbol, period):
        requests.append(type(client))
        raise RuntimeError("provider unavailable")

    for provider in PROVIDERS:
        monkeypatch.setattr(provider, "fetch_closing_prices", fetch)

    result = scanner.market_data_collection_service.collect_asset(
        AssetCatalog().get("sp500")
    )

    assert requests == [YahooFinanceClient]
    assert result.status == "error"
    assert result.error == "provider unavailable"
    assert result.observations == []


def should_exclude_removed_instruments_from_the_catalog():
    assets = AssetCatalog().all()
    assert len(assets) == 25
    assert {"move", "topix", "rvx", "vstoxx"}.isdisjoint(assets)


def should_collect_only_the_selected_development_assets():
    from unittest.mock import Mock

    from app.services.market_data_collection_service import MarketDataCollectionService

    client = Mock()
    client.fetch_closing_prices.return_value = ClosingPriceHistory(
        (ClosingPrice(date(2026, 9, 11), 100.0),)
    )
    service = MarketDataCollectionService(AssetCatalog(("nasdaq100", "vix")), client)

    result = service.collect()

    assert set(result.assets) == {"nasdaq100", "vix"}
    assert [call.args[0] for call in client.fetch_closing_prices.call_args_list] == [
        "^NDX",
        "^VIX",
    ]


@pytest.mark.parametrize("keys", [(), ("unknown",)])
def should_reject_an_invalid_asset_selection(keys):
    with pytest.raises(ValueError, match="known catalog keys"):
        AssetCatalog(keys)
