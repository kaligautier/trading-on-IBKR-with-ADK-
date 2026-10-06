"""Unit tests for market scanner constants."""

from datetime import date


def should_define_versioned_market_state_keys():
    from app.config.constants import (
        STATE_ANALYSED_MARKET_DATA,
        STATE_MARKET_DATA,
        STATE_WEB_ANALYSIS,
    )

    assert STATE_ANALYSED_MARKET_DATA == "analysed_market_data"
    assert STATE_MARKET_DATA == "market_data"
    assert STATE_WEB_ANALYSIS == "web_analysis"


def should_define_a_valid_asset_catalog():
    from app.config.constants import ASSET_ENTRIES

    assert "sp500" in ASSET_ENTRIES
    assert "vix" in ASSET_ENTRIES
    assert ASSET_ENTRIES["dspx"][0] == "^DSPX"
    assert ASSET_ENTRIES["vixeq"][0] == "^VIXEQ"
    assert all(ticker and label for ticker, label in ASSET_ENTRIES.values())


def should_subtract_exact_calendar_months_and_years():
    from app.config.constants import HORIZONS

    horizons = {horizon.label: horizon for horizon in HORIZONS}

    assert horizons["1m"].target_date(date(2024, 3, 31)) == date(2024, 2, 29)
    assert horizons["1y"].target_date(date(2024, 2, 29)) == date(2023, 2, 28)


def should_anchor_ytd_to_previous_december_31():
    from app.config.constants import HORIZONS

    ytd = next(horizon for horizon in HORIZONS if horizon.label == "ytd")
    for observed_on in (date(2024, 1, 1), date(2024, 2, 29), date(2024, 12, 31)):
        assert ytd.target_date(observed_on) == date(2023, 12, 31)


def should_expose_dispersion_symbols_through_the_asset_catalog():
    from app.models.market_assets import AssetCatalog

    catalog = AssetCatalog()

    assert catalog.get("dspx").symbol == "^DSPX"
    assert catalog.get("vixeq").symbol == "^VIXEQ"
