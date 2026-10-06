"""Treasury observations use the same dated asset path without losing cents."""

import json
from datetime import date
from decimal import Decimal

import pytest

from app.client.treasury_client import TreasuryClient
from app.models.market_assets import MarketDataAsset
from app.services.market_data_trend_service import MarketDataTrendService


class TreasuryResponse:
    def __init__(self, rows):
        self.rows = rows
        self.url = None

    def get_text(self, url):
        self.url = url
        return json.dumps({"data": self.rows})


def should_keep_cents_in_the_shared_asset_and_horizon_contract():
    http = TreasuryResponse(
        [
            {"record_date": "2026-09-10", "tot_pub_debt_out_amt": "40047726949770.15"},
            {"record_date": "2026-08-10", "tot_pub_debt_out_amt": "39000000000000.05"},
            {"record_date": "2025-09-10", "tot_pub_debt_out_amt": "37000000000000.10"},
        ]
    )
    history = TreasuryClient(http).fetch_closing_prices(
        "US_PUBLIC_DEBT", "10y", as_of=date(2026, 9, 13)
    )
    result = MarketDataTrendService()._build_result("US_PUBLIC_DEBT", history)
    debt = MarketDataAsset(name="US federal debt", kind="macro", unit="USD", **result)
    assert debt.value == Decimal("40047726949770.15")
    assert debt.value - debt.horizons["1m"].ref_price == Decimal("1047726949770.10")
    assert debt.value - debt.horizons["1y"].ref_price == Decimal("3047726949770.05")
    assert debt.horizons["1w"] is None
    assert debt.observed_on == date(2026, 9, 10)
    payload = debt.model_dump(mode="json")
    assert payload["value"] == "40047726949770.15"
    assert MarketDataAsset.model_validate_json(json.dumps(payload)).value == debt.value


def should_report_missing_debt_without_a_fabricated_value():
    history = TreasuryClient(TreasuryResponse([])).fetch_closing_prices(
        "US_PUBLIC_DEBT", "10y", as_of=date(2026, 9, 13)
    )
    assert history.latest is None


def should_reject_a_future_debt_observation():
    http = TreasuryResponse(
        [
            {"record_date": "2026-09-14", "tot_pub_debt_out_amt": "40047726949770.15"},
        ]
    )
    with pytest.raises(ValueError, match="Invalid debt"):
        TreasuryClient(http).fetch_closing_prices(
            "US_PUBLIC_DEBT", "10y", as_of=date(2026, 9, 13)
        )
