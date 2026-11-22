"""Unit tests for the structured error module."""

import pytest

from app.utils.error import (
    ERROR_MESSAGES,
    HTTP_STATUS_CODES,
    AppError,
    ErrorCode,
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


@pytest.mark.parametrize(
    "error,code,status",
    [
        (InvalidArgumentError(), ErrorCode.INVALID_ARGUMENT, 422),
        (InvalidCursorError(), ErrorCode.INVALID_ARGUMENT, 422),
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


def test_envelope_exposes_code_and_message_but_never_details():
    error = AppError(ErrorCode.INVALID_RESPONSE, "Custom", {"fields": ["regime"]})
    assert error.to_dict() == {
        "error": {"code": "INVALID_RESPONSE", "message": "Custom"}
    }
    assert str(error) == "[INVALID_RESPONSE] Custom, details={'fields': ['regime']}"


def test_store_unavailable_keeps_a_safe_category():
    error = StoreUnavailableError("TimeoutError")
    assert error.category == "TimeoutError"
    assert error.details == {"category": "TimeoutError"}
    assert str(StoreUnavailableError()).startswith("[STORE_UNAVAILABLE]")
