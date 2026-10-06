"""After-agent wide-event enrichment."""

from google.adk.agents.callback_context import CallbackContext

from app.utils.wide_event import wide_event


def record_agent_end(callback_context: CallbackContext) -> None:
    """Record completion without copying agent output or session state."""
    wide_event.append("agents.completed", callback_context.agent_name)
