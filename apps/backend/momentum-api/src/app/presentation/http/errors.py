"""Translate application failures at the HTTP boundary only."""

from app.domain.analyses.errors import (
    AnalysisNotFoundError,
    ConsultationError,
    InvalidStoredAnalysisError,
    StoreConfigurationError,
    StoreUnavailableError,
)
from app.presentation.http.problems import APIError

PROBLEMS: dict[type[ConsultationError], tuple[int, str]] = {
    AnalysisNotFoundError: (404, "analysis-not-found"),
    InvalidStoredAnalysisError: (500, "invalid-stored-data"),
    StoreConfigurationError: (500, "configuration-error"),
    StoreUnavailableError: (503, "store-unavailable"),
}


def application_problem(error: ConsultationError) -> APIError:
    status, code = PROBLEMS.get(type(error), (500, "internal-error"))
    return APIError(status, code)
