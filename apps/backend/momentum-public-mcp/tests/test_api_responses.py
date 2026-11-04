"""Undeclared upstream fields must not enter public response DTOs."""

import pytest
from test_gateway import analysis_summary, market_scan, suggestion

from momentum_public_mcp.api.market_scanner.dtos.response.market_scan import MarketScan
from momentum_public_mcp.api.momentum.dtos.response.analyses import AnalysisSummary
from momentum_public_mcp.api.momentum.dtos.response.suggestions import Suggestion


@pytest.mark.parametrize(
    ("model", "payload"),
    [
        (AnalysisSummary, analysis_summary()),
        (Suggestion, suggestion()),
        (MarketScan, market_scan()),
    ],
)
def test_response_dtos_ignore_undeclared_upstream_fields(model, payload):
    response = model.model_validate({**payload, "internal_debug": "private detail"})
    serialized = response.model_dump()

    assert "internal_debug" not in serialized
    assert "suggested_by" not in serialized
    assert "reviewed_by" not in serialized
