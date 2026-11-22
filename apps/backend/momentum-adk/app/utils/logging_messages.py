"""Log message templates shared by the whole application.

Each constant is a ``%s`` template or an event name. Pass templates to the logger
with their arguments, ``logger.warning(LoggingMessages.YAHOO_RATE_LIMITED, ...)``,
so the message is only formatted when the record is actually emitted. Job events
are one JSON object per line on stdout. Ruff rule G004 rejects f-strings in
logging calls.
"""


class LoggingMessages:
    """Reusable log messages, grouped by the area that emits them."""

    # Job events (JSON lines on stdout)
    MOMENTUM_STARTED = "momentum_started"
    MOMENTUM_COMPLETED = "momentum_completed"
    MOMENTUM_BUSY = "momentum_busy"
    MOMENTUM_FAILED = "momentum_failed"

    # Market data
    YAHOO_RATE_LIMITED = "Yahoo Finance rate limited, retrying in %.0fs (attempt %s/%s)"
    BULK_STOCKSTATS_FAILED = "Error getting bulk stockstats data: %s"
    STOCKSTATS_INDICATOR_FAILED = (
        "Error getting stockstats indicator data for indicator %s on %s: %s"
    )
    ALPHA_VANTAGE_INDICATOR_FAILED = (
        "Error getting Alpha Vantage indicator data for %s: %s"
    )
    CSV_DATE_FILTER_FAILED = "Failed to filter CSV data by date range: %s"
    MARKET_DATA_SAVED = "%s saved to %s"

    # Trading memory
    DEFERRED_OUTCOME_UNAVAILABLE = "Deferred outcome unavailable for %s: %s"
