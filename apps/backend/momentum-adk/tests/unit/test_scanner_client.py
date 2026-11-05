"""The worker consumes the Scanner's versioned REST contract without fallback."""

from unittest.mock import Mock

import pytest
import requests

from app.components.tools.market_data import get_latest_market_scan


@pytest.mark.parametrize("trailing_slash", ["", "/"])
def test_reads_the_canonical_scanner_path(monkeypatch, trailing_slash):
    monkeypatch.setenv("TA_MARKET_SCANNER_API_URL", "http://reader" + trailing_slash)
    response = Mock(text='{"report": {"schema_version": 3}}')
    get = Mock(return_value=response)
    monkeypatch.setattr("app.components.tools.market_data.requests.get", get)
    assert get_latest_market_scan() == response.text
    get.assert_called_once_with("http://reader/v1/market-scans/latest", timeout=12)
    response.raise_for_status.assert_called_once_with()


def test_failure_does_not_retry_a_removed_path(monkeypatch):
    monkeypatch.setenv("TA_MARKET_SCANNER_API_URL", "http://reader")
    get = Mock(side_effect=requests.HTTPError("404"))
    monkeypatch.setattr("app.components.tools.market_data.requests.get", get)
    assert get_latest_market_scan() == "Market scanner API unavailable: 404"
    assert get.call_count == 1
