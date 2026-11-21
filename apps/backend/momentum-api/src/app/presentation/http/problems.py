"""Safe, stable application problems (RFC 9457); no exception text is exposed.

Codes, statuses and details are declared in ``app.utils.error``.
"""

import json
from http import HTTPStatus

from app.utils.error import AppError

PROBLEM_BASE = (
    "https://github.com/kaligautier/trading-on-IBKR-with-ADK-"
    "/blob/main/apps/backend/momentum-api/README.md#"
)


def problem_bytes(error: AppError) -> bytes:
    return json.dumps(
        {
            "type": PROBLEM_BASE + error.error_code.value,
            "title": status_phrase(error.status_code),
            "status": error.status_code,
            "detail": error.message,
            "code": error.wire_code,
        },
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
    ).encode("utf-8")


def status_phrase(status: int) -> str:
    """Keep the public contract stable across Python 3.12 and newer runtimes."""
    return "Content Too Large" if status == 413 else HTTPStatus(status).phrase
