"""Application failures with stable codes and separate diagnostic context."""

from enum import StrEnum
from typing import Any


class ErrorCode(StrEnum):
    MOMENTUM_API_ERROR = "MOMENTUM_API_ERROR"
    MARKET_SCANNER_API_ERROR = "MARKET_SCANNER_API_ERROR"
    SERVICE_IDENTITY_ERROR = "SERVICE_IDENTITY_ERROR"
    INSTRUCTION_ERROR = "INSTRUCTION_ERROR"


class AppError(Exception):
    """Only the code and public message may be exposed to MCP clients."""

    def __init__(
        self,
        error_code: ErrorCode,
        message: str,
        *,
        details: dict[str, Any] | None = None,
    ):
        self.error_code = error_code
        self.message = message
        self.details = dict(details or {})
        super().__init__(message)

    def __str__(self) -> str:
        return f"[{self.error_code.value}] {self.message}"

    def to_dict(self) -> dict[str, str]:
        """Return public fields only; diagnostic context remains internal."""
        return {"error_code": self.error_code.value, "message": self.message}


class InstructionError(AppError):
    def __init__(self, *, details: dict[str, Any] | None = None):
        super().__init__(
            ErrorCode.INSTRUCTION_ERROR,
            "Prompt instructions could not be loaded.",
            details=details,
        )
