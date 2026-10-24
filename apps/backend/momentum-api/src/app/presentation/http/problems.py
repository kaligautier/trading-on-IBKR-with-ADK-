"""Safe, stable application problems (RFC 9457); no exception text is exposed."""

import json
from dataclasses import dataclass
from http import HTTPStatus

PROBLEM_BASE = (
    "https://github.com/kaligautier/trading-on-IBKR-with-ADK-"
    "/blob/main/apps/backend/momentum-api/README.md#"
)
DETAILS = {
    "forbidden": "The suggestion caller signature is invalid.",
    "current-analysis": "This ticker already has a current Momentum analysis.",
    "suggestion-quota": "The suggestion cooldown or daily limit was reached.",
    "payload-too-large": "The request body exceeds the allowed size.",
    "unsupported-media-type": "Use application/json for suggestion intake.",
    "invalid-argument": "The request parameters or headers are invalid.",
    "invalid-request": "Use a single Authorization Bearer credential.",
    "invalid-token": "The supplied credential is invalid.",
    "analysis-not-found": "The requested analysis does not exist.",
    "not-found": "The requested resource does not exist.",
    "method-not-allowed": "This resource does not support the requested method.",
    "not-acceptable": "The requested representation is unavailable.",
    "precondition-failed": "The representation does not satisfy the precondition.",
    "invalid-stored-data": "The stored analysis cannot be represented.",
    "configuration-error": "The service configuration prevents this operation.",
    "store-unavailable": "The analysis store is temporarily unavailable.",
    "internal-error": "The service could not complete the request.",
    "not-implemented": "The requested method is not implemented.",
}


CODES = {
    "forbidden": "FORBIDDEN",
    "current-analysis": "CURRENT_ANALYSIS_EXISTS",
    "suggestion-quota": "SUGGESTION_RATE_LIMIT",
    "payload-too-large": "PAYLOAD_TOO_LARGE",
    "unsupported-media-type": "UNSUPPORTED_MEDIA_TYPE",
    "invalid-argument": "INVALID_ARGUMENT",
    "invalid-request": "INVALID_ARGUMENT",
    "invalid-token": "UNAUTHENTICATED",
    "analysis-not-found": "ANALYSIS_NOT_FOUND",
    "not-found": "NOT_FOUND",
    "method-not-allowed": "METHOD_NOT_ALLOWED",
    "not-acceptable": "NOT_ACCEPTABLE",
    "precondition-failed": "PRECONDITION_FAILED",
    "invalid-stored-data": "INVALID_STORED_ANALYSIS",
    "configuration-error": "STORE_CONFIGURATION_ERROR",
    "store-unavailable": "STORE_UNAVAILABLE",
    "internal-error": "INTERNAL_ERROR",
    "not-implemented": "NOT_IMPLEMENTED",
}


@dataclass
class APIError(Exception):
    status: int
    code: str


def problem_bytes(error: APIError) -> bytes:
    return json.dumps(
        {
            "type": PROBLEM_BASE + error.code,
            "title": status_phrase(error.status),
            "status": error.status,
            "detail": DETAILS[error.code],
            "code": CODES[error.code],
        },
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
    ).encode("utf-8")


def status_phrase(status: int) -> str:
    """Keep the public contract stable across Python 3.12 and newer runtimes."""
    return "Content Too Large" if status == 413 else HTTPStatus(status).phrase
