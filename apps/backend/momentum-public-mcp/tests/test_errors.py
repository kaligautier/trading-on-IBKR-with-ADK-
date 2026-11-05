"""Application errors preserve diagnostics without exposing them to clients."""

import json

import httpx
import pytest

from app.api.auth import MetadataIdentityTokenProvider
from app.api.errors import (
    MarketScannerApiError,
    MomentumApiError,
    ServiceIdentityError,
)
from app.api.market_scanner.client.market_scanner_client import (
    MarketScannerClient,
)
from app.api.momentum.client.momentum_client import MomentumClient
from app.api.momentum.client.signing import SuggestionSigner
from app.api.momentum.dtos.request.analyses import AnalysisPageRequest
from app.core_components.prompts.instructions import get_instruction
from app.errors import ErrorCode, InstructionError


@pytest.mark.parametrize("api", ["momentum", "scanner"])
@pytest.mark.parametrize(
    "failure", [400, 404, 409, 422, 429, 503, "timeout", "invalid_json"]
)
async def test_api_failures_keep_their_origin_status_and_public_message(api, failure):
    def handler(request):
        if failure == "timeout":
            raise httpx.ReadTimeout("private upstream context", request=request)
        status = failure if isinstance(failure, int) else 200
        return httpx.Response(status, text="private upstream context")

    async with httpx.AsyncClient(
        base_url="https://upstream.test", transport=httpx.MockTransport(handler)
    ) as http:
        if api == "momentum":
            client = MomentumClient(http, SuggestionSigner("test-secret"))
            operation = lambda: client.list_analyses(AnalysisPageRequest())  # noqa: E731
            error_type = MomentumApiError
            code = ErrorCode.MOMENTUM_API_ERROR
        else:
            client = MarketScannerClient(http)
            operation = client.latest_market_scan
            error_type = MarketScannerApiError
            code = ErrorCode.MARKET_SCANNER_API_ERROR
        with pytest.raises(error_type) as captured:
            await operation()

    error = captured.value
    expected_status = (
        None if failure == "timeout" else (failure if isinstance(failure, int) else 200)
    )
    assert error.upstream_status_code == expected_status
    assert error.error_code == code
    assert code.value in str(error)
    assert "private upstream context" not in str(error)
    assert "private upstream context" not in json.dumps(error.to_dict())


def test_public_error_serialization_excludes_internal_details_and_status():
    error = MomentumApiError(
        upstream_status_code=503, details={"internal": "private diagnostic context"}
    )
    assert error.details == {"internal": "private diagnostic context"}
    assert error.to_dict() == {
        "error_code": "MOMENTUM_API_ERROR",
        "message": "Momentum public API request failed.",
    }
    assert "private" not in str(error)
    assert "503" not in str(error)


def test_missing_instruction_has_a_safe_typed_error():
    with pytest.raises(InstructionError) as captured:
        get_instruction("missing-private-instruction")
    assert isinstance(captured.value.__cause__, FileNotFoundError)
    assert captured.value.error_code == ErrorCode.INSTRUCTION_ERROR
    assert captured.value.details == {"instruction": "missing-private-instruction"}
    assert "missing-private-instruction" not in str(captured.value)
    assert "missing-private-instruction" not in json.dumps(captured.value.to_dict())


@pytest.mark.parametrize("status", [200, 503])
async def test_unavailable_identity_has_a_separate_safe_code(status):
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(status, text=""))
    ) as http:
        provider = MetadataIdentityTokenProvider(http, "https://private-api.test")
        with pytest.raises(ServiceIdentityError) as captured:
            await provider.token()
    assert captured.value.error_code == ErrorCode.SERVICE_IDENTITY_ERROR
    assert "private-api" not in str(captured.value)
