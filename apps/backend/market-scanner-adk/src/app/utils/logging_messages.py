"""Log message templates shared by the whole application.

Each constant is a ``%s`` template. Pass it to the logger with its arguments,
``logger.info(LoggingMessages.TEMPLATE_LOADING, template_path)``, so the message
is only formatted when the record is actually emitted. Structured fields stay in
``extra``; ruff rule G004 rejects f-strings in logging calls.
"""


class LoggingMessages:
    """Reusable log messages, grouped by the area that emits them."""

    # Application
    APP_CREATED = "application created"
    APP_ERROR = "%s"

    # Scheduled scan dispatch (HTTP)
    SCAN_DISPATCH_ACCEPTED = "scheduled scan accepted"
    SCAN_DISPATCH_FAILED = "scheduled scan dispatch failed"

    # Scheduled scan job
    SCAN_COMPLETED = "scheduled scan completed"
    SCAN_DEFERRED = "scheduled scan deferred"
    SCAN_FAILED = "scheduled scan failed"

    # Instructions
    TEMPLATE_LOADING = "Loading instructions template: %s"
    TEMPLATE_INFO_REQUESTED = "Getting template info for: %s"
    TEMPLATE_NOT_FOUND = "Template file not found: %s"
    TEMPLATE_LOAD_FAILED = "Failed to load template: %s: %s"
    TEMPLATE_RENDERED = "Successfully rendered instructions '%s' with %s variables"
    TEMPLATE_RENDER_FAILED = "Error rendering template '%s': %s"
    TEMPLATE_PARSE_FAILED = "Failed to parse template: %s: %s"
    TEMPLATE_VARIABLES = "Template '%s' has %s variables: %s"

    # Market data collection
    COLLECTION_FAILED = "Collection failed for %s: %s"
