"""Safe, stable application problems (RFC 9457); no exception text is exposed."""

import json
from dataclasses import dataclass
from http import HTTPStatus

PROBLEM_BASE = (
    "https://github.com/kaligautier/trading-on-IBKR-with-ADK-"
    "/blob/main/apps/backend/momentum-api/README.md#"
)
DETAILS = {
    "invalid-argument": "The request parameters or headers are invalid.",
    "invalid-request": "Use a single Authorization Bearer credential.",
    "invalid-token": "The supplied credential is invalid.",
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


@dataclass(frozen=True)
class APIError(Exception):
    status: int
    code: str


def problem_bytes(error: APIError) -> bytes:
    return json.dumps(
        {
            "type": PROBLEM_BASE + error.code,
            "title": HTTPStatus(error.status).phrase,
            "status": error.status,
            "detail": DETAILS[error.code],
            "code": error.code,
        },
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
    ).encode("utf-8")
