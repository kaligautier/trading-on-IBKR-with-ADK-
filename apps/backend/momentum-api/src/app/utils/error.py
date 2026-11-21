"""Error handling with structured exceptions and HTTP status mapping.

Every public failure is declared once here: its HTTP status, stable wire
``code`` and ``message``. The HTTP boundary serializes an ``AppError`` as the
``{"error": {"code": ..., "message": ...}}`` envelope; ``details`` carry
internal, value-free context and are never returned. Domain failures stay
independent of HTTP and are mapped through ``DOMAIN_ERRORS``.

Each enum value is the README anchor of the failure and the OAuth ``error``
parameter of Bearer challenges. Append new members instead of reordering them.
"""

from enum import Enum

from pydantic import JsonValue

from app.domain.analyses.errors import (
    AnalysisNotFoundError,
    InvalidStoredAnalysisError,
    StoreConfigurationError,
    StoreUnavailableError,
)
from app.domain.suggestions import CurrentAnalysisExistsError, SuggestionRateLimitError


class ErrorCode(Enum):
    """Public failures; each value is the README anchor slug."""

    FORBIDDEN = "forbidden"
    CURRENT_ANALYSIS_EXISTS = "current-analysis"
    SUGGESTION_RATE_LIMIT = "suggestion-quota"
    PAYLOAD_TOO_LARGE = "payload-too-large"
    UNSUPPORTED_MEDIA_TYPE = "unsupported-media-type"
    INVALID_ARGUMENT = "invalid-argument"
    INVALID_REQUEST = "invalid-request"
    UNAUTHENTICATED = "invalid-token"
    ANALYSIS_NOT_FOUND = "analysis-not-found"
    NOT_FOUND = "not-found"
    METHOD_NOT_ALLOWED = "method-not-allowed"
    NOT_ACCEPTABLE = "not-acceptable"
    PRECONDITION_FAILED = "precondition-failed"
    INVALID_STORED_ANALYSIS = "invalid-stored-data"
    STORE_CONFIGURATION_ERROR = "configuration-error"
    STORE_UNAVAILABLE = "store-unavailable"
    INTERNAL_ERROR = "internal-error"
    NOT_IMPLEMENTED = "not-implemented"


HTTP_STATUS_CODES: dict[ErrorCode, int] = {
    ErrorCode.FORBIDDEN: 403,
    ErrorCode.CURRENT_ANALYSIS_EXISTS: 409,
    ErrorCode.SUGGESTION_RATE_LIMIT: 429,
    ErrorCode.PAYLOAD_TOO_LARGE: 413,
    ErrorCode.UNSUPPORTED_MEDIA_TYPE: 415,
    ErrorCode.INVALID_ARGUMENT: 400,
    ErrorCode.INVALID_REQUEST: 400,
    ErrorCode.UNAUTHENTICATED: 401,
    ErrorCode.ANALYSIS_NOT_FOUND: 404,
    ErrorCode.NOT_FOUND: 404,
    ErrorCode.METHOD_NOT_ALLOWED: 405,
    ErrorCode.NOT_ACCEPTABLE: 406,
    ErrorCode.PRECONDITION_FAILED: 412,
    ErrorCode.INVALID_STORED_ANALYSIS: 500,
    ErrorCode.STORE_CONFIGURATION_ERROR: 500,
    ErrorCode.STORE_UNAVAILABLE: 503,
    ErrorCode.INTERNAL_ERROR: 500,
    ErrorCode.NOT_IMPLEMENTED: 501,
}

ERROR_MESSAGES: dict[ErrorCode, str] = {
    ErrorCode.FORBIDDEN: "The suggestion caller signature is invalid.",
    ErrorCode.CURRENT_ANALYSIS_EXISTS: (
        "This ticker already has a current Momentum analysis."
    ),
    ErrorCode.SUGGESTION_RATE_LIMIT: (
        "The suggestion cooldown or daily limit was reached."
    ),
    ErrorCode.PAYLOAD_TOO_LARGE: "The request body exceeds the allowed size.",
    ErrorCode.UNSUPPORTED_MEDIA_TYPE: "Use application/json for suggestion intake.",
    ErrorCode.INVALID_ARGUMENT: "The request parameters or headers are invalid.",
    ErrorCode.INVALID_REQUEST: "Use a single Authorization Bearer credential.",
    ErrorCode.UNAUTHENTICATED: "The supplied credential is invalid.",
    ErrorCode.ANALYSIS_NOT_FOUND: "The requested analysis does not exist.",
    ErrorCode.NOT_FOUND: "The requested resource does not exist.",
    ErrorCode.METHOD_NOT_ALLOWED: (
        "This resource does not support the requested method."
    ),
    ErrorCode.NOT_ACCEPTABLE: "The requested representation is unavailable.",
    ErrorCode.PRECONDITION_FAILED: (
        "The representation does not satisfy the precondition."
    ),
    ErrorCode.INVALID_STORED_ANALYSIS: "The stored analysis cannot be represented.",
    ErrorCode.STORE_CONFIGURATION_ERROR: (
        "The service configuration prevents this operation."
    ),
    ErrorCode.STORE_UNAVAILABLE: "The analysis store is temporarily unavailable.",
    ErrorCode.INTERNAL_ERROR: "The service could not complete the request.",
    ErrorCode.NOT_IMPLEMENTED: "The requested method is not implemented.",
}

# Stable public ``code``: the enum name, except where two failures share one.
WIRE_CODES: dict[ErrorCode, str] = {code: code.name for code in ErrorCode} | {
    ErrorCode.INVALID_REQUEST: "INVALID_ARGUMENT"
}

# Domain and port failures, translated at the HTTP boundary only.
DOMAIN_ERRORS: dict[type[Exception], ErrorCode] = {
    AnalysisNotFoundError: ErrorCode.ANALYSIS_NOT_FOUND,
    InvalidStoredAnalysisError: ErrorCode.INVALID_STORED_ANALYSIS,
    StoreConfigurationError: ErrorCode.STORE_CONFIGURATION_ERROR,
    StoreUnavailableError: ErrorCode.STORE_UNAVAILABLE,
    CurrentAnalysisExistsError: ErrorCode.CURRENT_ANALYSIS_EXISTS,
    SuggestionRateLimitError: ErrorCode.SUGGESTION_RATE_LIMIT,
}


class AppError(Exception):
    """
    Base application error with automatic HTTP status mapping.

    Attributes:
        error_code: ErrorCode enum value; its value is the README anchor slug
        message: Public message (always the declared message)
        details: Optional value-free context for logs, never returned to clients
        status_code: HTTP status code (mapped, or overridden for one use case)
        has_body: False for a bare authentication challenge (RFC 6750 3.1)
    """

    has_body = True

    def __init__(
        self,
        error_code: ErrorCode,
        details: dict[str, JsonValue] | None = None,
        *,
        status_code: int | None = None,
    ) -> None:
        self.error_code = error_code
        self.status_code = status_code or HTTP_STATUS_CODES.get(error_code, 500)
        self.message = ERROR_MESSAGES.get(error_code, "An error occurred")
        self.details = details or {}
        super().__init__(self.message)

    @property
    def wire_code(self) -> str:
        return WIRE_CODES[self.error_code]

    def to_response(self) -> dict[str, dict[str, str]]:
        """Public API error envelope, without details."""
        return {"error": {"code": self.wire_code, "message": self.message}}

    def __str__(self) -> str:
        """String representation with error code and details, for logs."""
        detail_str = f", details={self.details}" if self.details else ""
        return f"[{self.error_code.name}] {self.message}{detail_str}"

    @classmethod
    def from_domain(cls, error: Exception) -> "AppError":
        """Translate a domain failure; unknown failures become internal errors."""
        code = DOMAIN_ERRORS.get(type(error), ErrorCode.INTERNAL_ERROR)
        return cls(code, details={"error_type": type(error).__name__})


class InvalidArgumentError(AppError):
    """Request parameters, headers or body are invalid."""

    def __init__(self, details: dict[str, JsonValue] | None = None) -> None:
        super().__init__(ErrorCode.INVALID_ARGUMENT, details)


class MissingCredentialsError(AppError):
    """No usable Bearer credential: a bare 401 challenge without a body."""

    has_body = False

    def __init__(self) -> None:
        super().__init__(ErrorCode.UNAUTHENTICATED)
