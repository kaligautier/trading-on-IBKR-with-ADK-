"""Unit tests for the structured error module."""

import re

import pytest

from app.utils.error import (
    CANONICAL_CODES,
    CANONICAL_HTTP_STATUS,
    ERROR_MESSAGES,
    HTTP_STATUS_CODES,
    RFC9110_STATUSES,
    AppError,
    ErrorCode,
    ErrorKind,
    InvalidArgumentError,
    InvalidCursorError,
    InvalidResponseError,
    InvalidStoredReportError,
    ScanNotFoundError,
    StoreUnavailableError,
)


def test_every_error_code_has_a_status_and_a_message():
    for code in ErrorCode:
        assert code in HTTP_STATUS_CODES
        assert ERROR_MESSAGES[code]


def test_every_code_is_an_aip_193_reason_with_a_canonical_status():
    for code in ErrorCode:
        assert re.fullmatch(r"[A-Z][A-Z0-9_]+[A-Z0-9]", code.name)
        status = HTTP_STATUS_CODES[code]
        if status not in RFC9110_STATUSES:
            assert CANONICAL_HTTP_STATUS[CANONICAL_CODES[code]] == status


@pytest.mark.parametrize(
    "error,code,status",
    [
        (InvalidArgumentError(), ErrorCode.INVALID_ARGUMENT, 400),
        (InvalidCursorError(), ErrorCode.INVALID_ARGUMENT, 400),
        (ScanNotFoundError(), ErrorCode.SCAN_NOT_FOUND, 404),
        (InvalidStoredReportError(), ErrorCode.INVALID_STORED_REPORT, 500),
        (InvalidResponseError(), ErrorCode.INVALID_RESPONSE, 500),
        (StoreUnavailableError(), ErrorCode.STORE_UNAVAILABLE, 503),
    ],
)
def test_subclasses_map_to_their_code_status_and_default_message(error, code, status):
    assert isinstance(error, AppError)
    assert error.error_code == code
    assert error.status_code == status
    assert error.message == ERROR_MESSAGES[code]


def test_status_is_aip_193_and_never_exposes_details():
    error = AppError(ErrorCode.INVALID_RESPONSE, "Custom", {"fields": ["regime"]})
    assert error.to_status("req-1") == {
        "error": {
            "code": 500,
            "message": "Custom",
            "status": "INTERNAL",
            "details": [
                {
                    "@type": "type.googleapis.com/google.rpc.ErrorInfo",
                    "reason": "INVALID_RESPONSE",
                    "domain": "market-scanner-api.deepcopy.fr",
                    "metadata": {},
                },
                {
                    "@type": "type.googleapis.com/google.rpc.RequestInfo",
                    "requestId": "req-1",
                },
            ],
        }
    }
    assert error.kind is ErrorKind.TECHNICAL
    assert str(error) == "[INVALID_RESPONSE] Custom, details={'fields': ['regime']}"


def test_store_unavailable_keeps_a_safe_category():
    error = StoreUnavailableError("TimeoutError")
    assert error.category == "TimeoutError"
    assert error.details == {"category": "TimeoutError"}
    assert str(StoreUnavailableError()).startswith("[STORE_UNAVAILABLE]")
