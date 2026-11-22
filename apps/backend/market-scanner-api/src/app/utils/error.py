"""Error handling with structured exceptions and HTTP status mapping.

Errors are Google AIP-193 ``google.rpc.Status`` bodies: ``{"error": {"code",
"message", "status", "details"}}`` where ``code`` is the HTTP status, ``status``
the canonical ``google.rpc.Code`` and ``details`` an ``ErrorInfo`` (``reason`` =
``ErrorCode`` name, ``domain`` = ``ERROR_DOMAIN``) then the ``RequestInfo``.
RFC 9110 decides the HTTP status where it imposes one (405 + ``Allow``, reported
as ``UNIMPLEMENTED``); otherwise the status is the canonical code's, so invalid
arguments are 400. ``details`` of the exception carry internal, value-free
context for logs and are never returned to clients.
"""

from enum import Enum

from pydantic import JsonValue

ERROR_DOMAIN = "market-scanner-api.deepcopy.fr"
ERROR_INFO_TYPE = "type.googleapis.com/google.rpc.ErrorInfo"
REQUEST_INFO_TYPE = "type.googleapis.com/google.rpc.RequestInfo"


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
    """Error codes for application exceptions."""

    INTERNAL_ERROR = 1000
    INVALID_ARGUMENT = 1001
    UNAUTHENTICATED = 1002
    NOT_FOUND = 1003
    METHOD_NOT_ALLOWED = 1004
    REQUEST_FAILED = 1005
    SCAN_NOT_FOUND = 2001
    INVALID_STORED_REPORT = 2002
    INVALID_RESPONSE = 2003
    STORE_UNAVAILABLE = 3001


HTTP_STATUS_CODES: dict[ErrorCode, int] = {
    ErrorCode.INTERNAL_ERROR: 500,
    ErrorCode.INVALID_ARGUMENT: 400,
    ErrorCode.UNAUTHENTICATED: 401,
    ErrorCode.NOT_FOUND: 404,
    ErrorCode.METHOD_NOT_ALLOWED: 405,
    ErrorCode.REQUEST_FAILED: 400,
    ErrorCode.SCAN_NOT_FOUND: 404,
    ErrorCode.INVALID_STORED_REPORT: 500,
    ErrorCode.INVALID_RESPONSE: 500,
    ErrorCode.STORE_UNAVAILABLE: 503,
}


CANONICAL_CODES: dict[ErrorCode, CanonicalCode] = {
    ErrorCode.INTERNAL_ERROR: CanonicalCode.INTERNAL,
    ErrorCode.INVALID_ARGUMENT: CanonicalCode.INVALID_ARGUMENT,
    ErrorCode.UNAUTHENTICATED: CanonicalCode.UNAUTHENTICATED,
    ErrorCode.NOT_FOUND: CanonicalCode.NOT_FOUND,
    ErrorCode.METHOD_NOT_ALLOWED: CanonicalCode.UNIMPLEMENTED,
    ErrorCode.REQUEST_FAILED: CanonicalCode.INVALID_ARGUMENT,
    ErrorCode.SCAN_NOT_FOUND: CanonicalCode.NOT_FOUND,
    ErrorCode.INVALID_STORED_REPORT: CanonicalCode.INTERNAL,
    ErrorCode.INVALID_RESPONSE: CanonicalCode.INTERNAL,
    ErrorCode.STORE_UNAVAILABLE: CanonicalCode.UNAVAILABLE,
}


ERROR_MESSAGES: dict[ErrorCode, str] = {
    ErrorCode.INTERNAL_ERROR: "Internal server error",
    ErrorCode.INVALID_ARGUMENT: "Invalid request parameters",
    ErrorCode.UNAUTHENTICATED: "Authentication required",
    ErrorCode.NOT_FOUND: "Route not found",
    ErrorCode.METHOD_NOT_ALLOWED: "Method not allowed",
    ErrorCode.REQUEST_FAILED: "Request failed",
    ErrorCode.SCAN_NOT_FOUND: "No market scan available",
    ErrorCode.INVALID_STORED_REPORT: "Stored report is invalid",
    ErrorCode.INVALID_RESPONSE: "Stored scan does not satisfy the response contract",
    ErrorCode.STORE_UNAVAILABLE: "Scan storage is unavailable",
}


class AppError(Exception):
    """
    Base application error with automatic HTTP status mapping.

    Attributes:
        error_code: ErrorCode enum value; its name is the public error code
        message: Human-readable error message returned to clients
        details: Optional value-free context for logs, never returned to clients
        status_code: HTTP status code (automatically mapped)
    """

    def __init__(
        self,
        error_code: ErrorCode,
        message: str | None = None,
        details: dict[str, JsonValue] | None = None,
        *,
        status_code: int | None = None,
    ) -> None:
        self.error_code = error_code
        self.status_code = status_code or HTTP_STATUS_CODES.get(error_code, 500)
        self.message = message or ERROR_MESSAGES.get(error_code, "An error occurred")
        self.details = details or {}

        super().__init__(self.message)

    def __str__(self) -> str:
        """String representation with error code and details."""
        detail_str = f", details={self.details}" if self.details else ""
        return f"[{self.error_code.name}] {self.message}{detail_str}"

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
        details: list[JsonValue] = [
            {
                "@type": ERROR_INFO_TYPE,
                "reason": self.error_code.name,
                "domain": ERROR_DOMAIN,
                "metadata": {},
            }
        ]
        if request_id:
            details.append({"@type": REQUEST_INFO_TYPE, "requestId": request_id})
        return {
            "error": {
                "code": self.status_code,
                "message": self.message,
                "status": self.canonical.name,
                "details": details,
            }
        }


class InvalidArgumentError(AppError):
    """Raised when request parameters are invalid."""

    def __init__(
        self, message: str | None = None, details: dict[str, JsonValue] | None = None
    ) -> None:
        super().__init__(ErrorCode.INVALID_ARGUMENT, message, details)


class InvalidCursorError(InvalidArgumentError):
    """A pagination token is malformed or uses an unsupported version."""


class ScanNotFoundError(AppError):
    """No persisted run matches the request."""

    def __init__(
        self, message: str | None = None, details: dict[str, JsonValue] | None = None
    ) -> None:
        super().__init__(ErrorCode.SCAN_NOT_FOUND, message, details)


class InvalidStoredReportError(AppError):
    """A stored report violates the supported writer contract."""

    def __init__(
        self, message: str | None = None, details: dict[str, JsonValue] | None = None
    ) -> None:
        super().__init__(ErrorCode.INVALID_STORED_REPORT, message, details)


class InvalidResponseError(AppError):
    """A stored model cannot be mapped to a valid response DTO."""

    def __init__(
        self, message: str | None = None, details: dict[str, JsonValue] | None = None
    ) -> None:
        super().__init__(ErrorCode.INVALID_RESPONSE, message, details)


class StoreUnavailableError(AppError):
    """The reader cannot currently query its store."""

    def __init__(self, category: str = "unknown") -> None:
        super().__init__(ErrorCode.STORE_UNAVAILABLE, details={"category": category})
        self.category = category
