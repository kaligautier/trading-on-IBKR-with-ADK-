"""Typed upstream failures with public messages and diagnostic HTTP status."""

from typing import Any

from momentum_public_mcp.errors import AppError, ErrorCode


class ApiError(AppError):
    error_code: ErrorCode
    service_name: str

    def __init__(
        self,
        message: str | None = None,
        *,
        upstream_status_code: int | None = None,
        details: dict[str, Any] | None = None,
    ):
        self.upstream_status_code = upstream_status_code
        super().__init__(
            self.error_code,
            message or f"{self.service_name} public API request failed.",
            details=details,
        )


class MomentumApiError(ApiError):
    error_code = ErrorCode.MOMENTUM_API_ERROR
    service_name = "Momentum"


class MarketScannerApiError(ApiError):
    error_code = ErrorCode.MARKET_SCANNER_API_ERROR
    service_name = "Market Scanner"


class ServiceIdentityError(AppError):
    def __init__(self):
        super().__init__(
            ErrorCode.SERVICE_IDENTITY_ERROR,
            "Cloud Run service identity is unavailable.",
        )
