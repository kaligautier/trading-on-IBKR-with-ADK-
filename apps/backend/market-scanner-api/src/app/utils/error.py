"""Error handling with structured exceptions and HTTP status mapping.

Each ``ErrorCode`` name is the public wire code of the error envelope. ``details``
carry internal, value-free context for logs and are never returned to clients.
"""

from enum import Enum

from pydantic import JsonValue


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
    ErrorCode.INVALID_ARGUMENT: 422,
    ErrorCode.UNAUTHENTICATED: 401,
    ErrorCode.NOT_FOUND: 404,
    ErrorCode.METHOD_NOT_ALLOWED: 405,
    ErrorCode.REQUEST_FAILED: 400,
    ErrorCode.SCAN_NOT_FOUND: 404,
    ErrorCode.INVALID_STORED_REPORT: 500,
    ErrorCode.INVALID_RESPONSE: 500,
    ErrorCode.STORE_UNAVAILABLE: 503,
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
    ) -> None:
        self.error_code = error_code
        self.status_code = HTTP_STATUS_CODES.get(error_code, 500)
        self.message = message or ERROR_MESSAGES.get(error_code, "An error occurred")
        self.details = details or {}

        super().__init__(self.message)

    def __str__(self) -> str:
        """String representation with error code and details."""
        detail_str = f", details={self.details}" if self.details else ""
        return f"[{self.error_code.name}] {self.message}{detail_str}"

    def to_dict(self) -> dict[str, dict[str, str]]:
        """Convert exception to the public API error envelope (without details)."""
        return {"error": {"code": self.error_code.name, "message": self.message}}


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
