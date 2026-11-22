"""The error module declares every public failure once."""

import json
import re

import pytest

from app.domain.analyses.errors import (
    AnalysisNotFoundError,
    InvalidStoredAnalysisError,
    StoreConfigurationError,
    StoreUnavailableError,
)
from app.domain.suggestions import CurrentAnalysisExistsError, SuggestionRateLimitError
from app.dto.response.error_response import error_bytes, error_responses, request_id_var
from app.utils.error import (
    CANONICAL_CODES,
    CANONICAL_HTTP_STATUS,
    ERROR_DOMAIN,
    ERROR_MESSAGES,
    HTTP_STATUS_CODES,
    RFC9110_STATUSES,
    AppError,
    CanonicalCode,
    ErrorCode,
    ErrorKind,
    MissingCredentialsError,
)

REASON = re.compile(r"[A-Z][A-Z0-9_]+[A-Z0-9]\Z")


def test_every_code_is_an_aip_193_reason_with_a_canonical_status() -> None:
    for code in ErrorCode:
        status = HTTP_STATUS_CODES[code]
        assert 400 <= status < 600
        assert ERROR_MESSAGES[code]
        assert REASON.match(code.name) and len(code.name) <= 63
        if status not in RFC9110_STATUSES:
            assert CANONICAL_HTTP_STATUS[CANONICAL_CODES[code]] == status


def test_error_body_is_a_google_rpc_status() -> None:
    token = request_id_var.set("req-1")
    try:
        body = json.loads(error_bytes(AppError(ErrorCode.ANALYSIS_NOT_FOUND)))
    finally:
        request_id_var.reset(token)
    error = body["error"]
    assert (error["code"], error["status"]) == (404, "NOT_FOUND")
    assert error["message"] == "The requested analysis does not exist."
    info, request, help_ = error["details"]
    assert info == {
        "@type": "type.googleapis.com/google.rpc.ErrorInfo",
        "reason": "ANALYSIS_NOT_FOUND",
        "domain": ERROR_DOMAIN,
        "metadata": {},
    }
    assert request["requestId"] == "req-1"
    assert help_["links"][0]["url"].endswith("README.md#analysis-not-found")


def test_rfc_9110_statuses_report_the_closest_canonical_code() -> None:
    assert AppError(ErrorCode.METHOD_NOT_ALLOWED).canonical is (
        CanonicalCode.UNIMPLEMENTED
    )
    assert AppError(ErrorCode.PRECONDITION_FAILED).canonical is (
        CanonicalCode.FAILED_PRECONDITION
    )


def test_kind_separates_caller_and_operator_failures() -> None:
    assert AppError(ErrorCode.ANALYSIS_NOT_FOUND).kind is ErrorKind.DOMAIN
    assert AppError(ErrorCode.STORE_UNAVAILABLE).kind is ErrorKind.TECHNICAL


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
    assert "private" not in error_bytes(translated).decode()


def test_status_override_keeps_the_declared_reason() -> None:
    error = AppError(ErrorCode.STORE_CONFIGURATION_ERROR, status_code=503)
    body = json.loads(error_bytes(error))["error"]
    assert (body["code"], body["status"]) == (503, "UNAVAILABLE")
    assert body["details"][0]["reason"] == "STORE_CONFIGURATION_ERROR"


def test_error_responses_list_each_code_under_its_status() -> None:
    responses = error_responses(ErrorCode.ANALYSIS_NOT_FOUND, ErrorCode.NOT_FOUND)
    assert list(responses) == [404]
    assert "`ANALYSIS_NOT_FOUND`" in responses[404]["description"]
    assert "`NOT_FOUND`" in responses[404]["description"]


def test_missing_credentials_is_a_bodyless_challenge() -> None:
    error = MissingCredentialsError()
    assert error.status_code == 401
    assert not error.has_body
