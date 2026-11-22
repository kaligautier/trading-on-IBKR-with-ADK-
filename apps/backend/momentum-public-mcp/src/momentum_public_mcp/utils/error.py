"""Error handling with structured exceptions and status mapping.

Three kinds of failures leave this server:

* HTTP errors outside MCP dispatch (unknown route, method) return a Google
  AIP-193 ``google.rpc.Status`` body: ``{"error": {"code", "message", "status",
  "details"}}``. ``code`` is the HTTP status, ``status`` the canonical
  ``google.rpc.Code`` name and ``details`` always holds an ``ErrorInfo`` whose
  ``reason`` is the ``ErrorCode`` name in the ``ERROR_DOMAIN`` domain. RFC 9110
  decides the HTTP status; where it has no canonical equivalent (405), the
  closest canonical code is reported;
* protocol errors reject an MCP request before dispatch. JSON-RPC requires its
  own envelope, ``{"jsonrpc", "id", "error": {"code", "message", "data"}}``, so
  the stable reason is carried in ``error.data.code``;
* upstream errors become MCP tool or resource errors, returned in-band (HTTP 200,
  ``isError``) with their sanitized message only.

``details`` carry internal, value-free context for logs and are never returned to
clients. Messages are part of the public contract checked by the Bruno suite.
"""

from enum import Enum

from pydantic import JsonValue

ERROR_DOMAIN = "mcp.deepcopy.fr"
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
    """Error codes for application exceptions; each name is the wire code."""

    # HTTP (envelope)
    NOT_FOUND = 1
    METHOD_NOT_ALLOWED = 2
    REQUEST_FAILED = 3

    # Protocol (HTTP 400, JSON-RPC error)
    PROTOCOL_VERSION_REQUIRED = 1001
    UNSUPPORTED_PROTOCOL_VERSION = 1002
    CLIENT_INFO_REQUIRED = 1003
    # Upstream API (MCP tool/resource error)
    SERVICE_IDENTITY_UNAVAILABLE = 2001
    UPSTREAM_UNAVAILABLE = 2002
    UPSTREAM_NOT_FOUND = 2003
    UPSTREAM_RATE_LIMITED = 2004
    CURRENT_ANALYSIS_EXISTS = 2005
    UPSTREAM_INPUT_REJECTED = 2006
    UPSTREAM_REQUEST_FAILED = 2007
    INVALID_UPSTREAM_DATA = 2008


PROTOCOL_ERRORS = frozenset(
    {
        ErrorCode.PROTOCOL_VERSION_REQUIRED,
        ErrorCode.UNSUPPORTED_PROTOCOL_VERSION,
        ErrorCode.CLIENT_INFO_REQUIRED,
    }
)

# Protocol errors are rejected over HTTP; upstream errors stay in-band (200).
HTTP_STATUS_CODES: dict[ErrorCode, int] = {
    code: 400 if code in PROTOCOL_ERRORS else 200 for code in ErrorCode
} | {
    ErrorCode.NOT_FOUND: 404,
    ErrorCode.METHOD_NOT_ALLOWED: 405,
    ErrorCode.REQUEST_FAILED: 400,
}

CANONICAL_CODES: dict[ErrorCode, CanonicalCode] = {
    ErrorCode.NOT_FOUND: CanonicalCode.NOT_FOUND,
    ErrorCode.METHOD_NOT_ALLOWED: CanonicalCode.UNIMPLEMENTED,
    ErrorCode.REQUEST_FAILED: CanonicalCode.INVALID_ARGUMENT,
    ErrorCode.PROTOCOL_VERSION_REQUIRED: CanonicalCode.INVALID_ARGUMENT,
    ErrorCode.UNSUPPORTED_PROTOCOL_VERSION: CanonicalCode.INVALID_ARGUMENT,
    ErrorCode.CLIENT_INFO_REQUIRED: CanonicalCode.INVALID_ARGUMENT,
    ErrorCode.SERVICE_IDENTITY_UNAVAILABLE: CanonicalCode.UNAVAILABLE,
    ErrorCode.UPSTREAM_UNAVAILABLE: CanonicalCode.UNAVAILABLE,
    ErrorCode.UPSTREAM_NOT_FOUND: CanonicalCode.NOT_FOUND,
    ErrorCode.UPSTREAM_RATE_LIMITED: CanonicalCode.RESOURCE_EXHAUSTED,
    ErrorCode.CURRENT_ANALYSIS_EXISTS: CanonicalCode.ALREADY_EXISTS,
    ErrorCode.UPSTREAM_INPUT_REJECTED: CanonicalCode.INVALID_ARGUMENT,
    ErrorCode.UPSTREAM_REQUEST_FAILED: CanonicalCode.INTERNAL,
    ErrorCode.INVALID_UPSTREAM_DATA: CanonicalCode.INTERNAL,
}

JSONRPC_ERROR_CODES: dict[ErrorCode, int] = {
    ErrorCode.PROTOCOL_VERSION_REQUIRED: -32602,
    ErrorCode.UNSUPPORTED_PROTOCOL_VERSION: -32022,
    ErrorCode.CLIENT_INFO_REQUIRED: -32602,
}

ERROR_MESSAGES: dict[ErrorCode, str] = {
    ErrorCode.NOT_FOUND: "Route not found",
    ErrorCode.METHOD_NOT_ALLOWED: "Method not allowed",
    ErrorCode.REQUEST_FAILED: "Request failed",
    ErrorCode.PROTOCOL_VERSION_REQUIRED: "MCP-Protocol-Version is required.",
    ErrorCode.UNSUPPORTED_PROTOCOL_VERSION: "Unsupported protocol version.",
    ErrorCode.CLIENT_INFO_REQUIRED: (
        "SEP-2575 requires clientInfo.name and version on every request."
    ),
    ErrorCode.SERVICE_IDENTITY_UNAVAILABLE: (
        "Cloud Run service identity is unavailable."
    ),
    ErrorCode.UPSTREAM_UNAVAILABLE: "Momentum public API is unavailable.",
    ErrorCode.UPSTREAM_NOT_FOUND: "Momentum public resource not found.",
    ErrorCode.UPSTREAM_RATE_LIMITED: "Momentum public request limit reached.",
    ErrorCode.CURRENT_ANALYSIS_EXISTS: (
        "This ticker already has a current analysis in Momentum."
    ),
    ErrorCode.UPSTREAM_INPUT_REJECTED: "Momentum rejected the public input.",
    ErrorCode.UPSTREAM_REQUEST_FAILED: "Momentum public API request failed.",
    ErrorCode.INVALID_UPSTREAM_DATA: "Momentum public API returned invalid data.",
}

# Upstream HTTP statuses with a dedicated public message; other errors are generic.
UPSTREAM_STATUS_ERRORS: dict[int, ErrorCode] = {
    404: ErrorCode.UPSTREAM_NOT_FOUND,
    409: ErrorCode.CURRENT_ANALYSIS_EXISTS,
    422: ErrorCode.UPSTREAM_INPUT_REJECTED,
    429: ErrorCode.UPSTREAM_RATE_LIMITED,
}


class AppError(Exception):
    """
    Base application error with automatic status mapping.

    Attributes:
        error_code: ErrorCode enum value
        message: Sanitized message returned to clients
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

    def __str__(self) -> str:
        """String representation with error code and details, for logs."""
        detail_str = f", details={self.details}" if self.details else ""
        return f"[{self.error_code.name}] {self.message}{detail_str}"


class ProtocolError(AppError):
    """An HTTP request violates the stateless SEP-2575 profile."""

    def __init__(
        self, error_code: ErrorCode, data: dict[str, JsonValue] | None = None
    ) -> None:
        super().__init__(error_code)
        self.data = data

    def to_jsonrpc(self, request_id: JsonValue) -> dict[str, JsonValue]:
        """Public JSON-RPC error envelope for the rejected request."""
        data: dict[str, JsonValue] = {"code": self.error_code.name, **(self.data or {})}
        error: dict[str, JsonValue] = {
            "code": JSONRPC_ERROR_CODES[self.error_code],
            "message": self.message,
            "data": data,
        }
        return {"jsonrpc": "2.0", "id": request_id, "error": error}


class MomentumApiError(AppError):
    """Sanitized public API failure, exposed as an MCP tool or resource error."""

    def __init__(
        self, error_code: ErrorCode, details: dict[str, JsonValue] | None = None
    ) -> None:
        super().__init__(error_code, details=details)

    @classmethod
    def for_status(cls, status_code: int) -> "MomentumApiError":
        """Map an upstream error status to its public failure."""
        code = UPSTREAM_STATUS_ERRORS.get(
            status_code, ErrorCode.UPSTREAM_REQUEST_FAILED
        )
        return cls(code, details={"upstream_status": status_code})
