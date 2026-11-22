"""Error handling with structured exceptions and HTTP status mapping.

Every public failure is declared once here: its HTTP status, ``message`` and
canonical ``google.rpc.Code``. The HTTP boundary serializes an ``AppError`` as a
Google AIP-193 ``google.rpc.Status``: ``{"error": {"code", "message", "status",
"details"}}`` where ``code`` is the HTTP status, ``status`` the canonical code
name and ``details`` an ``ErrorInfo`` (``reason`` = enum name, ``domain`` =
``ERROR_DOMAIN``), the ``RequestInfo`` and a ``Help`` link. RFC 9110 decides the
HTTP status; where it has no canonical equivalent (405, 406, 412, 413, 415) the
closest canonical code is reported. ``details`` of the exception carry internal,
value-free context and are never returned. Domain failures stay independent of
HTTP and are mapped through ``DOMAIN_ERRORS``.

Each enum value is the README anchor of the failure (the ``Help`` link) and the
OAuth ``error`` parameter of Bearer challenges. Append new members instead of
reordering them.
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

ERROR_DOMAIN = "momentum-api.deepcopy.fr"
ERROR_INFO_TYPE = "type.googleapis.com/google.rpc.ErrorInfo"
REQUEST_INFO_TYPE = "type.googleapis.com/google.rpc.RequestInfo"
HELP_TYPE = "type.googleapis.com/google.rpc.Help"
HELP_URL = (
    "https://github.com/kaligautier/trading-on-IBKR-with-ADK-/blob/main/"
    "apps/backend/momentum-api/README.md#"
)


class CanonicalCode(Enum):
    """``google.rpc.Code``: the canonical status of every AIP-193 error."""

    CANCELLED = 1
    UNKNOWN = 2
    INVALID_ARGUMENT = 3
    DEADLINE_EXCEEDED = 4
    NOT_FOUND = 5
    ALREADY_EXISTS = 6
    PERMISSION_DENIED = 7
    RESOURCE_EXHAUSTED = 8
    FAILED_PRECONDITION = 9
    ABORTED = 10
    OUT_OF_RANGE = 11
    UNIMPLEMENTED = 12
    INTERNAL = 13
    UNAVAILABLE = 14
    DATA_LOSS = 15
    UNAUTHENTICATED = 16


# HTTP status of each canonical code (google/rpc/code.proto).
CANONICAL_HTTP_STATUS: dict[CanonicalCode, int] = {
    CanonicalCode.CANCELLED: 499,
    CanonicalCode.UNKNOWN: 500,
    CanonicalCode.INVALID_ARGUMENT: 400,
    CanonicalCode.DEADLINE_EXCEEDED: 504,
    CanonicalCode.NOT_FOUND: 404,
    CanonicalCode.ALREADY_EXISTS: 409,
    CanonicalCode.PERMISSION_DENIED: 403,
    CanonicalCode.RESOURCE_EXHAUSTED: 429,
    CanonicalCode.FAILED_PRECONDITION: 400,
    CanonicalCode.ABORTED: 409,
    CanonicalCode.OUT_OF_RANGE: 400,
    CanonicalCode.UNIMPLEMENTED: 501,
    CanonicalCode.INTERNAL: 500,
    CanonicalCode.UNAVAILABLE: 503,
    CanonicalCode.DATA_LOSS: 500,
    CanonicalCode.UNAUTHENTICATED: 401,
}

# RFC 9110 statuses kept although google.rpc.Code has no HTTP mapping for them.
RFC9110_STATUSES = frozenset({405, 406, 412, 413, 415})


class ErrorKind(Enum):
    """Who can resolve the failure: the caller (domain) or the operator."""

    DOMAIN = "domain"
    TECHNICAL = "technical"


TECHNICAL_CODES = frozenset(
    {
        CanonicalCode.UNKNOWN,
        CanonicalCode.DEADLINE_EXCEEDED,
        CanonicalCode.INTERNAL,
        CanonicalCode.UNAVAILABLE,
        CanonicalCode.DATA_LOSS,
    }
)


# Canonical code of an HTTP status no ``ErrorCode`` declares (Google's mapping).
HTTP_CANONICAL_CODES: dict[int, CanonicalCode] = {
    400: CanonicalCode.INVALID_ARGUMENT,
    401: CanonicalCode.UNAUTHENTICATED,
    403: CanonicalCode.PERMISSION_DENIED,
    404: CanonicalCode.NOT_FOUND,
    409: CanonicalCode.ABORTED,
    416: CanonicalCode.OUT_OF_RANGE,
    429: CanonicalCode.RESOURCE_EXHAUSTED,
    499: CanonicalCode.CANCELLED,
    501: CanonicalCode.UNIMPLEMENTED,
    503: CanonicalCode.UNAVAILABLE,
    504: CanonicalCode.DEADLINE_EXCEEDED,
}


def canonical_for_http(status_code: int) -> CanonicalCode:
    """Canonical code of an undeclared HTTP status: other 4xx/5xx are generic."""
    fallback = (
        CanonicalCode.INTERNAL
        if status_code >= 500
        else CanonicalCode.FAILED_PRECONDITION
    )
    return HTTP_CANONICAL_CODES.get(status_code, fallback)


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

CANONICAL_CODES: dict[ErrorCode, CanonicalCode] = {
    ErrorCode.FORBIDDEN: CanonicalCode.PERMISSION_DENIED,
    ErrorCode.CURRENT_ANALYSIS_EXISTS: CanonicalCode.ALREADY_EXISTS,
    ErrorCode.SUGGESTION_RATE_LIMIT: CanonicalCode.RESOURCE_EXHAUSTED,
    ErrorCode.PAYLOAD_TOO_LARGE: CanonicalCode.INVALID_ARGUMENT,
    ErrorCode.UNSUPPORTED_MEDIA_TYPE: CanonicalCode.INVALID_ARGUMENT,
    ErrorCode.INVALID_ARGUMENT: CanonicalCode.INVALID_ARGUMENT,
    ErrorCode.INVALID_REQUEST: CanonicalCode.INVALID_ARGUMENT,
    ErrorCode.UNAUTHENTICATED: CanonicalCode.UNAUTHENTICATED,
    ErrorCode.ANALYSIS_NOT_FOUND: CanonicalCode.NOT_FOUND,
    ErrorCode.NOT_FOUND: CanonicalCode.NOT_FOUND,
    ErrorCode.METHOD_NOT_ALLOWED: CanonicalCode.UNIMPLEMENTED,
    ErrorCode.NOT_ACCEPTABLE: CanonicalCode.INVALID_ARGUMENT,
    ErrorCode.PRECONDITION_FAILED: CanonicalCode.FAILED_PRECONDITION,
    ErrorCode.INVALID_STORED_ANALYSIS: CanonicalCode.INTERNAL,
    ErrorCode.STORE_CONFIGURATION_ERROR: CanonicalCode.INTERNAL,
    ErrorCode.STORE_UNAVAILABLE: CanonicalCode.UNAVAILABLE,
    ErrorCode.INTERNAL_ERROR: CanonicalCode.INTERNAL,
    ErrorCode.NOT_IMPLEMENTED: CanonicalCode.UNIMPLEMENTED,
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
    def canonical(self) -> CanonicalCode:
        """Canonical code; an overridden HTTP status brings its own."""
        if self.status_code == HTTP_STATUS_CODES.get(self.error_code):
            return CANONICAL_CODES[self.error_code]
        return canonical_for_http(self.status_code)

    @property
    def kind(self) -> ErrorKind:
        technical = self.canonical in TECHNICAL_CODES
        return ErrorKind.TECHNICAL if technical else ErrorKind.DOMAIN

    def to_status(self, request_id: str | None = None) -> dict[str, JsonValue]:
        """Public AIP-193 ``google.rpc.Status`` body, without internal details."""
        reason = self.error_code.name
        details: list[JsonValue] = [
            {
                "@type": ERROR_INFO_TYPE,
                "reason": reason,
                "domain": ERROR_DOMAIN,
                "metadata": {},
            }
        ]
        if request_id:
            details.append({"@type": REQUEST_INFO_TYPE, "requestId": request_id})
        details.append(
            {
                "@type": HELP_TYPE,
                "links": [
                    {
                        "description": f"Troubleshooting documentation for {reason}",
                        "url": HELP_URL + self.error_code.value,
                    }
                ],
            }
        )
        return {
            "error": {
                "code": self.status_code,
                "message": self.message,
                "status": self.canonical.name,
                "details": details,
            }
        }

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
