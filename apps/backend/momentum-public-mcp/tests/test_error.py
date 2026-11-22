"""The error module owns every public failure message, status and protocol code."""

import pytest

from momentum_public_mcp.utils.error import (
    ERROR_MESSAGES,
    HTTP_STATUS_CODES,
    JSONRPC_ERROR_CODES,
    PROTOCOL_ERRORS,
    AppError,
    ErrorCode,
    MomentumApiError,
    ProtocolError,
)


def test_every_code_has_a_message_and_status():
    for code in ErrorCode:
        assert ERROR_MESSAGES[code]
        assert HTTP_STATUS_CODES[code] in {200, 400, 404, 405}


def test_protocol_errors_are_http_rejections_with_jsonrpc_codes():
    for code in PROTOCOL_ERRORS:
        assert HTTP_STATUS_CODES[code] == 400
        assert code in JSONRPC_ERROR_CODES


def test_protocol_error_builds_the_jsonrpc_envelope():
    error = ProtocolError(
        ErrorCode.UNSUPPORTED_PROTOCOL_VERSION,
        data={"requested": "2025-01-01", "supported": ["2026-07-28"]},
    )
    assert error.to_jsonrpc("call-1") == {
        "jsonrpc": "2.0",
        "id": "call-1",
        "error": {
            "code": -32022,
            "message": "Unsupported protocol version.",
            "data": {
                "code": "UNSUPPORTED_PROTOCOL_VERSION",
                "requested": "2025-01-01",
                "supported": ["2026-07-28"],
            },
        },
    }
    assert ProtocolError(ErrorCode.CLIENT_INFO_REQUIRED).to_jsonrpc(1)["error"][
        "data"
    ] == {"code": "CLIENT_INFO_REQUIRED"}


def test_http_errors_use_the_shared_envelope():
    assert AppError(ErrorCode.NOT_FOUND).to_response() == {
        "error": {"code": "NOT_FOUND", "message": "Route not found"}
    }
    assert HTTP_STATUS_CODES[ErrorCode.METHOD_NOT_ALLOWED] == 405


@pytest.mark.parametrize(
    ("status", "code"),
    [
        (404, ErrorCode.UPSTREAM_NOT_FOUND),
        (409, ErrorCode.CURRENT_ANALYSIS_EXISTS),
        (422, ErrorCode.UPSTREAM_INPUT_REJECTED),
        (429, ErrorCode.UPSTREAM_RATE_LIMITED),
        (500, ErrorCode.UPSTREAM_REQUEST_FAILED),
        (401, ErrorCode.UPSTREAM_REQUEST_FAILED),
    ],
)
def test_upstream_statuses_map_to_public_failures(status, code):
    error = MomentumApiError.for_status(status)
    assert error.error_code is code
    assert error.message == ERROR_MESSAGES[code]
    assert error.details == {"upstream_status": status}
    assert str(status) not in error.message


def test_details_stay_out_of_the_public_message():
    error = MomentumApiError(
        ErrorCode.UPSTREAM_UNAVAILABLE, details={"error_type": "ConnectError"}
    )
    assert error.message == "Momentum public API is unavailable."
    assert "ConnectError" in str(error)
