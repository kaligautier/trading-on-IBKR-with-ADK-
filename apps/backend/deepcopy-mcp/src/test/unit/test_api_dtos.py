"""Request DTOs protect direct client callers as well as MCP callers."""

import pytest
from pydantic import ValidationError

from app.api.deepcopy.dtos.request.account_request import (
    GetAccountRequest,
    GetPositionsRequest,
)
from app.api.deepcopy.dtos.request.search_contracts_request import (
    SearchContractsRequest,
)


@pytest.mark.parametrize("request_type", [GetAccountRequest, GetPositionsRequest])
@pytest.mark.parametrize(
    "values",
    [
        {"account_id": "../secret"},
        {"account_id": "U1/summary"},
        {"account_id": "u1234567"},
        {"account_id": ""},
        {"account_id": 1234567},
        {"account_id": "U1", "url": "https://unexpected.example"},
    ],
)
def test_rejects_invalid_account_parameters(request_type, values):
    with pytest.raises(ValidationError):
        request_type(**values)


@pytest.mark.parametrize("page", [-1, 1001, "1"])
def test_rejects_invalid_pages(page):
    with pytest.raises(ValidationError):
        GetPositionsRequest(account_id="U1", page=page)


@pytest.mark.parametrize("symbol", ["aapl", "AAPL&x=1", "A" * 13, "", "AA PL"])
def test_rejects_invalid_symbols(symbol):
    with pytest.raises(ValidationError):
        SearchContractsRequest(symbol=symbol)
