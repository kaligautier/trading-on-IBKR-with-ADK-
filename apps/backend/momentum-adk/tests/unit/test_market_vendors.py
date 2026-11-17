"""Vendor adapter boundary checks without external market requests."""

from unittest.mock import Mock

import pytest

from app.infrastructure.market_data.alpha_vantage import common


def test_missing_alpha_key_fails_before_network(monkeypatch):
    monkeypatch.delenv("ALPHA_VANTAGE_API_KEY", raising=False)
    with pytest.raises(ValueError, match="not set"):
        common._make_api_request("OVERVIEW", {"symbol": "AAPL"})


def test_alpha_preserves_parameters_and_report(monkeypatch):
    monkeypatch.setenv("ALPHA_VANTAGE_API_KEY", "offline-test")
    response = Mock(text='{"Symbol":"AAPL"}')
    get = Mock(return_value=response)
    monkeypatch.setattr(common.requests, "get", get)
    params = {"symbol": "AAPL"}
    assert common._make_api_request("OVERVIEW", params) == response.text
    assert params == {"symbol": "AAPL"}
    assert get.call_args.kwargs["params"]["function"] == "OVERVIEW"
    response.raise_for_status.assert_called_once()
