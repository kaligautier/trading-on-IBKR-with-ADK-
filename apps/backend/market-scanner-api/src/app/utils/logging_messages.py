"""Log message templates shared by the whole application.

Each constant is a ``%s`` template or an event name. Pass templates to the logger
with their arguments, ``logger.info(LoggingMessages.STRUCTURED_EVENT, payload)``,
so the message is only formatted when the record is actually emitted. This
service logs one JSON object per event; ruff rule G004 rejects f-strings in
logging calls.
"""


class LoggingMessages:
    """Reusable log messages, grouped by the area that emits them."""

    # Template for every structured event: the argument is the JSON payload.
    STRUCTURED_EVENT = "%s"

    # HTTP events
    HTTP_COMPLETED = "http.completed"
    HTTP_UNEXPECTED_ERROR = "http.unexpected_error"
    HTTP_APPLICATION_ERROR = "http.application_error"
