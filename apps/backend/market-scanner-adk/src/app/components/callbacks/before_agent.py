"""Before-agent wide-event enrichment."""

from google.adk.agents.callback_context import CallbackContext

from app.utils.wide_event import wide_event


def record_agent_start(callback_context: CallbackContext) -> None:
    """Log the start and enrich the request event."""
    wide_event.append("agents.started", callback_context.agent_name)
