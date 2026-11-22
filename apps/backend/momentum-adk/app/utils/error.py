"""Error handling with structured exceptions and job exit-code mapping.

Momentum runs as a Cloud Run job, not an HTTP service: each ``ErrorCode`` maps to
the process exit code the job returns, which plays the role of an HTTP status.
Failures are still classified as in Google AIP-193: each ``ErrorCode`` has a
canonical ``google.rpc.Code`` and its name is the ``ErrorInfo.reason`` of the
``ERROR_DOMAIN`` domain, logged with the failure event. ``AppError.kind`` derives
from the canonical code (technical vs domain).
``details`` carry internal, value-free context for logs and are never built from
prompts, URLs or upstream response bodies.
"""

from enum import Enum

from pydantic import JsonValue

ERROR_DOMAIN = "momentum.deepcopy.fr"


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

    INTERNAL_ERROR = 1000
    INVALID_REQUEST = 1001
    MOMENTUM_BUSY = 2001
    LITELLM_ERROR = 3001
    MARKET_DATA_RATE_LIMITED = 3002


# 75 (EX_TEMPFAIL) tells the scheduler the run was deferred, not failed.
EXIT_CODES: dict[ErrorCode, int] = {
    ErrorCode.INTERNAL_ERROR: 1,
    ErrorCode.INVALID_REQUEST: 1,
    ErrorCode.MOMENTUM_BUSY: 75,
    ErrorCode.LITELLM_ERROR: 1,
    ErrorCode.MARKET_DATA_RATE_LIMITED: 1,
}

CANONICAL_CODES: dict[ErrorCode, CanonicalCode] = {
    ErrorCode.INTERNAL_ERROR: CanonicalCode.INTERNAL,
    ErrorCode.INVALID_REQUEST: CanonicalCode.INVALID_ARGUMENT,
    ErrorCode.MOMENTUM_BUSY: CanonicalCode.UNAVAILABLE,
    ErrorCode.LITELLM_ERROR: CanonicalCode.UNAVAILABLE,
    ErrorCode.MARKET_DATA_RATE_LIMITED: CanonicalCode.UNAVAILABLE,
}

ERROR_MESSAGES: dict[ErrorCode, str] = {
    ErrorCode.INTERNAL_ERROR: "Momentum execution failed",
    ErrorCode.INVALID_REQUEST: "Invalid analysis request",
    ErrorCode.MOMENTUM_BUSY: "Momentum execution capacity is busy",
    ErrorCode.LITELLM_ERROR: "LiteLLM gateway failed",
    ErrorCode.MARKET_DATA_RATE_LIMITED: "Market data provider rate limit exceeded",
}


class AppError(Exception):
    """
    Base application error with automatic exit-code mapping.

    Attributes:
        error_code: ErrorCode enum value
        message: Sanitized message
        details: Optional value-free context for logs
        exit_code: Job process exit code (automatically mapped)
    """

    def __init__(
        self,
        error_code: ErrorCode,
        message: str | None = None,
        details: dict[str, JsonValue] | None = None,
    ) -> None:
        self.error_code = error_code
        self.exit_code = EXIT_CODES.get(error_code, 1)
        self.message = message or ERROR_MESSAGES.get(error_code, "An error occurred")
        self.details = details or {}
        super().__init__(self.message)

    @property
    def canonical(self) -> CanonicalCode:
        return CANONICAL_CODES[self.error_code]

    @property
    def kind(self) -> ErrorKind:
        technical = self.canonical in TECHNICAL_CODES
        return ErrorKind.TECHNICAL if technical else ErrorKind.DOMAIN

    def log_fields(self) -> dict[str, JsonValue]:
        """AIP-193 classification for the failure event, without details."""
        return {
            "status": self.canonical.name,
            "reason": self.error_code.name,
            "domain": ERROR_DOMAIN,
            "kind": self.kind.value,
        }

    def __str__(self) -> str:
        """String representation with error code and details."""
        detail_str = f", details={self.details}" if self.details else ""
        return f"[{self.error_code.name}] {self.message}{detail_str}"


class MomentumBusyError(AppError):
    """Another worker owns the Momentum execution slot."""

    def __init__(self, message: str | None = None) -> None:
        super().__init__(ErrorCode.MOMENTUM_BUSY, message)


class LiteLLMError(AppError):
    """Sanitized gateway failure; details hold the error type and status only."""

    def __init__(self, details: dict[str, JsonValue] | None = None) -> None:
        super().__init__(ErrorCode.LITELLM_ERROR, details=details)


class AlphaVantageRateLimitError(AppError):
    """Alpha Vantage API rate limit is exceeded."""

    def __init__(self, message: str | None = None) -> None:
        super().__init__(ErrorCode.MARKET_DATA_RATE_LIMITED, message)
