"""Log message templates shared by the whole application.

Each constant is a ``%s`` template or an event name. ``log_event`` passes the
JSON payload to ``LoggingMessages.STRUCTURED_EVENT``, so the message is only
formatted when the record is actually emitted. Ruff rule G004 rejects f-strings
in logging calls.
"""


class LoggingMessages:
    """Reusable log messages, grouped by the area that emits them."""

    # Template for every structured event: the argument is the JSON payload.
    STRUCTURED_EVENT = "%s"

    # HTTP requests
    REQUEST_COMPLETED = "request_completed"
    REQUEST_FAILED = "request_failed"

    # Lifecycle
    STORAGE_CLEANUP_FAILED = "storage_cleanup_failed"
