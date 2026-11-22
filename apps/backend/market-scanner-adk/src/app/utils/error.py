"""Error handling with structured exceptions and HTTP status mapping.

HTTP errors are Google AIP-193 ``google.rpc.Status`` bodies: ``{"error":
{"code", "message", "status", "details"}}`` where ``code`` is the HTTP status,
``status`` the canonical ``google.rpc.Code`` and ``details`` an ``ErrorInfo``
(``reason`` = ``ErrorCode`` name, ``domain`` = ``ERROR_DOMAIN``), then the
``RequestInfo`` and, for retryable failures, a ``RetryInfo``. Every HTTP status
is the one of its canonical code, so 502 is not used. ``details`` of the
exception carry internal, value-free context for logs and wide events and are
never returned to HTTP clients.
"""

from enum import Enum

from pydantic import JsonValue

ERROR_DOMAIN = "market-scanner.deepcopy.fr"
ERROR_INFO_TYPE = "type.googleapis.com/google.rpc.ErrorInfo"
REQUEST_INFO_TYPE = "type.googleapis.com/google.rpc.RequestInfo"
RETRY_INFO_TYPE = "type.googleapis.com/google.rpc.RetryInfo"


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


class ErrorCode(Enum):
    """Error codes for application exceptions."""

    GENERIC_ERROR = 1000
    INVALID_INPUT = 1001
    CONFIGURATION_ERROR = 1002
    INSTRUCTION_ERROR = 1003
    TOOL_EXECUTION_ERROR = 3001
    MARKET_DATA_COLLECTION_ERROR = 3002
    MARKET_DATA_UNAVAILABLE = 3003
    LITELLM_ERROR = 3004
    UNAUTHENTICATED = 4001
    SCANNER_BUSY = 4002
    SCAN_JOB_NOT_CONFIGURED = 4003
    SCAN_DISPATCH_FAILED = 4004


HTTP_STATUS_CODES: dict[ErrorCode, int] = {
    ErrorCode.GENERIC_ERROR: 500,
    ErrorCode.INVALID_INPUT: 400,
    ErrorCode.CONFIGURATION_ERROR: 500,
    ErrorCode.INSTRUCTION_ERROR: 500,
    ErrorCode.TOOL_EXECUTION_ERROR: 503,
    ErrorCode.MARKET_DATA_COLLECTION_ERROR: 503,
    ErrorCode.MARKET_DATA_UNAVAILABLE: 503,
    ErrorCode.LITELLM_ERROR: 503,
    ErrorCode.UNAUTHENTICATED: 401,
    ErrorCode.SCANNER_BUSY: 503,
    ErrorCode.SCAN_JOB_NOT_CONFIGURED: 503,
    ErrorCode.SCAN_DISPATCH_FAILED: 503,
}


CANONICAL_CODES: dict[ErrorCode, CanonicalCode] = {
    ErrorCode.GENERIC_ERROR: CanonicalCode.INTERNAL,
    ErrorCode.INVALID_INPUT: CanonicalCode.INVALID_ARGUMENT,
    ErrorCode.CONFIGURATION_ERROR: CanonicalCode.INTERNAL,
    ErrorCode.INSTRUCTION_ERROR: CanonicalCode.INTERNAL,
    ErrorCode.TOOL_EXECUTION_ERROR: CanonicalCode.UNAVAILABLE,
    ErrorCode.MARKET_DATA_COLLECTION_ERROR: CanonicalCode.UNAVAILABLE,
    ErrorCode.MARKET_DATA_UNAVAILABLE: CanonicalCode.UNAVAILABLE,
    ErrorCode.LITELLM_ERROR: CanonicalCode.UNAVAILABLE,
    ErrorCode.UNAUTHENTICATED: CanonicalCode.UNAUTHENTICATED,
    ErrorCode.SCANNER_BUSY: CanonicalCode.UNAVAILABLE,
    ErrorCode.SCAN_JOB_NOT_CONFIGURED: CanonicalCode.UNAVAILABLE,
    ErrorCode.SCAN_DISPATCH_FAILED: CanonicalCode.UNAVAILABLE,
}


ERROR_MESSAGES: dict[ErrorCode, str] = {
    ErrorCode.GENERIC_ERROR: "An unexpected error occurred",
    ErrorCode.INVALID_INPUT: "Invalid input provided",
    ErrorCode.CONFIGURATION_ERROR: "Configuration error",
    ErrorCode.INSTRUCTION_ERROR: "Instruction loading or rendering failed",
    ErrorCode.TOOL_EXECUTION_ERROR: "Tool execution failed",
    ErrorCode.MARKET_DATA_COLLECTION_ERROR: "Market data collection failed",
    ErrorCode.MARKET_DATA_UNAVAILABLE: "No available market data for analysis",
    ErrorCode.LITELLM_ERROR: "LiteLLM gateway request failed",
    ErrorCode.UNAUTHENTICATED: "Unauthorized",
    ErrorCode.SCANNER_BUSY: "Scanner execution capacity is busy",
    ErrorCode.SCAN_JOB_NOT_CONFIGURED: "Scheduled scan job is not configured",
    ErrorCode.SCAN_DISPATCH_FAILED: "Scheduled scan dispatch failed",
}


class AppError(Exception):
    """
    Base application error with automatic HTTP status mapping.

    Attributes:
        error_code: ErrorCode enum value
        message: Human-readable error message
        details: Optional dictionary with error context
        status_code: HTTP status code (automatically mapped)
        retry_after: Seconds before a retry may succeed, published as RetryInfo
    """

    retry_after: int | None = None

    def __init__(
        self,
        error_code: ErrorCode,
        message: str = None,
        details: dict = None,
    ):
        self.error_code = error_code
        self.status_code = HTTP_STATUS_CODES.get(error_code, 500)
        self.message = message or ERROR_MESSAGES.get(error_code, "An error occurred")
        self.details = details or {}

        super().__init__(self.message)

    def __str__(self):
        """String representation with error code and details."""
        detail_str = f", details={self.details}" if self.details else ""
        return f"[{self.error_code.name}] {self.message}{detail_str}"

    @property
    def canonical(self) -> CanonicalCode:
        return CANONICAL_CODES[self.error_code]

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
        if self.retry_after is not None:
            details.append(
                {"@type": RETRY_INFO_TYPE, "retryDelay": f"{self.retry_after}s"}
            )
        return {
            "error": {
                "code": self.status_code,
                "message": self.message,
                "status": self.canonical.name,
                "details": details,
            }
        }

    def to_dict(self):
        """Internal representation for logs and report data-quality entries."""
        return {
            "error_code": self.error_code.name,
            "message": self.message,
            "status_code": self.status_code,
            "details": self.details,
        }


class InvalidInputError(AppError):
    """Raised when input validation fails."""

    def __init__(self, message: str = None, details: dict = None):
        super().__init__(
            error_code=ErrorCode.INVALID_INPUT,
            message=message,
            details=details,
        )


class MarketDataCollectionError(AppError):
    """A provider could not supply usable observations for an asset."""

    def __init__(self, message: str | None = None, details: dict | None = None):
        super().__init__(ErrorCode.MARKET_DATA_COLLECTION_ERROR, message, details)


class MarketDataUnavailableError(AppError):
    """The scan cannot continue because no market asset is available."""

    def __init__(self, message: str | None = None, details: dict | None = None):
        super().__init__(ErrorCode.MARKET_DATA_UNAVAILABLE, message, details)


class LiteLLMError(AppError):
    """Inference failed at the gateway; the scan must stop without fallback."""

    def __init__(self, message: str | None = None, details: dict | None = None):
        super().__init__(ErrorCode.LITELLM_ERROR, message, details)


class ConfigurationError(AppError):
    """Raised when configuration is invalid or missing."""

    def __init__(self, message: str = None, details: dict = None):
        super().__init__(
            error_code=ErrorCode.CONFIGURATION_ERROR,
            message=message,
            details=details,
        )


class InstructionError(AppError):
    """Raised when instruction loading or rendering fails."""

    def __init__(self, message: str = None, details: dict = None):
        super().__init__(
            error_code=ErrorCode.INSTRUCTION_ERROR,
            message=message,
            details=details,
        )


class ToolExecutionError(AppError):
    """Raised when tool execution fails."""

    def __init__(self, message: str = None, details: dict = None):
        super().__init__(
            error_code=ErrorCode.TOOL_EXECUTION_ERROR,
            message=message,
            details=details,
        )


class UnauthenticatedError(AppError):
    """The request lacks the scanner token."""

    def __init__(self) -> None:
        super().__init__(ErrorCode.UNAUTHENTICATED)


class ScannerBusyHTTPError(AppError):
    """Scanner execution capacity is taken by another database-backed run."""

    retry_after = 30

    def __init__(self) -> None:
        super().__init__(ErrorCode.SCANNER_BUSY)


class ScanJobNotConfiguredError(AppError):
    """The scheduled scan Cloud Run job is not configured."""

    def __init__(self) -> None:
        super().__init__(ErrorCode.SCAN_JOB_NOT_CONFIGURED)


class ScanDispatchError(AppError):
    """The scheduled scan job could not be dispatched."""

    def __init__(self, details: dict[str, JsonValue] | None = None) -> None:
        super().__init__(ErrorCode.SCAN_DISPATCH_FAILED, details=details)
