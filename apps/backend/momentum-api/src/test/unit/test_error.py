"""The error module declares every public problem once."""

import json

import pytest

from app.domain.analyses.errors import (
    AnalysisNotFoundError,
    InvalidStoredAnalysisError,
    StoreConfigurationError,
    StoreUnavailableError,
)
from app.domain.suggestions import CurrentAnalysisExistsError, SuggestionRateLimitError
from app.presentation.http.problems import problem_bytes
from app.utils.error import (
    ERROR_MESSAGES,
    HTTP_STATUS_CODES,
    WIRE_CODES,
    AppError,
    ErrorCode,
    MissingCredentialsError,
)


def test_every_problem_type_has_a_status_message_and_wire_code() -> None:
    for code in ErrorCode:
        assert 400 <= HTTP_STATUS_CODES[code] < 600
        assert ERROR_MESSAGES[code]
        assert WIRE_CODES[code].isupper()


def test_invalid_request_shares_the_invalid_argument_wire_code() -> None:
    assert WIRE_CODES[ErrorCode.INVALID_REQUEST] == "INVALID_ARGUMENT"


@pytest.mark.parametrize(
    ("error", "code"),
    [
        (AnalysisNotFoundError(), ErrorCode.ANALYSIS_NOT_FOUND),
        (InvalidStoredAnalysisError("private"), ErrorCode.INVALID_STORED_ANALYSIS),
        (StoreConfigurationError(), ErrorCode.STORE_CONFIGURATION_ERROR),
        (StoreUnavailableError(), ErrorCode.STORE_UNAVAILABLE),
        (CurrentAnalysisExistsError(), ErrorCode.CURRENT_ANALYSIS_EXISTS),
        (SuggestionRateLimitError(), ErrorCode.SUGGESTION_RATE_LIMIT),
        (RuntimeError("private"), ErrorCode.INTERNAL_ERROR),
    ],
)
def test_domain_failures_map_without_exposing_their_text(
    error: Exception, code: ErrorCode
) -> None:
    translated = AppError.from_domain(error)
    assert translated.error_code is code
    assert "private" not in problem_bytes(translated).decode()


def test_status_override_keeps_the_declared_problem() -> None:
    error = AppError(ErrorCode.STORE_CONFIGURATION_ERROR, status_code=503)
    problem = json.loads(problem_bytes(error))
    assert problem["status"] == 503
    assert problem["title"] == "Service Unavailable"
    assert problem["code"] == "STORE_CONFIGURATION_ERROR"


def test_missing_credentials_is_a_bodyless_challenge() -> None:
    error = MissingCredentialsError()
    assert error.status_code == 401
    assert not error.has_body
