"""Error handling with structured exceptions and job exit-code mapping.

Momentum runs as a Cloud Run job, not an HTTP service: each ``ErrorCode`` maps to
the process exit code the job returns, which plays the role of an HTTP status.
``details`` carry internal, value-free context for logs and are never built from
prompts, URLs or upstream response bodies.
"""

from enum import Enum

from pydantic import JsonValue


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
