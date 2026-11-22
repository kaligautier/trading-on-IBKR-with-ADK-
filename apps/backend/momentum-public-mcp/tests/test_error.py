"""The error module owns every public failure message, status and protocol code."""

import re

import pytest

from momentum_public_mcp.utils.error import (
    CANONICAL_CODES,
    CANONICAL_HTTP_STATUS,
    ERROR_DOMAIN,
    ERROR_MESSAGES,
    HTTP_STATUS_CODES,
    JSONRPC_ERROR_CODES,
    PROTOCOL_ERRORS,
    RFC9110_STATUSES,
    AppError,
    CanonicalCode,
    ErrorCode,
    ErrorKind,
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


REASON = re.compile(r"[A-Z][A-Z0-9_]+[A-Z0-9]\Z")


def test_every_code_is_an_aip_193_reason_with_a_canonical_status():
    for code in ErrorCode:
        assert REASON.match(code.name) and len(code.name) <= 63
        http = HTTP_STATUS_CODES[code]
        if http != 200 and http not in RFC9110_STATUSES:
            assert CANONICAL_HTTP_STATUS[CANONICAL_CODES[code]] == http


def test_http_errors_use_the_aip_193_status():
    assert AppError(ErrorCode.NOT_FOUND).to_status("req-1") == {
        "error": {
            "code": 404,
            "message": "Route not found",
            "status": "NOT_FOUND",
            "details": [
                {
                    "@type": "type.googleapis.com/google.rpc.ErrorInfo",
                    "reason": "NOT_FOUND",
                    "domain": ERROR_DOMAIN,
                    "metadata": {},
                },
                {
                    "@type": "type.googleapis.com/google.rpc.RequestInfo",
                    "requestId": "req-1",
                },
            ],
        }
    }
    assert HTTP_STATUS_CODES[ErrorCode.METHOD_NOT_ALLOWED] == 405
    assert AppError(ErrorCode.METHOD_NOT_ALLOWED).canonical is (
        CanonicalCode.UNIMPLEMENTED
    )


@pytest.mark.parametrize(
    ("status", "canonical"),
    [
        (400, CanonicalCode.INVALID_ARGUMENT),
        (413, CanonicalCode.FAILED_PRECONDITION),
        (503, CanonicalCode.UNAVAILABLE),
        (502, CanonicalCode.INTERNAL),
    ],
)
def test_undeclared_statuses_get_their_canonical_code(status, canonical):
    error = AppError(ErrorCode.REQUEST_FAILED, status_code=status)
    assert error.canonical is canonical
    assert error.to_status()["error"]["code"] == status


def test_kind_separates_caller_and_operator_failures():
    assert AppError(ErrorCode.NOT_FOUND).kind is ErrorKind.DOMAIN
    assert AppError(ErrorCode.UPSTREAM_UNAVAILABLE).kind is ErrorKind.TECHNICAL


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
