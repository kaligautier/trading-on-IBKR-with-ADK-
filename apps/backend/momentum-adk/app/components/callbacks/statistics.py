"""Execution-scoped ADK callback instrumentation."""

from __future__ import annotations

from threading import Lock
from typing import Any

from app.domain.contracts import RunStatistics


class MomentumStatistics:
    """Collect model, tool, and token counters across parallel ADK nodes."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._statistics = RunStatistics()

    def reset(self) -> None:
        with self._lock:
            self._statistics = RunStatistics()

    def before_model(self, callback_context: Any, llm_request: Any) -> None:
        del callback_context, llm_request
        with self._lock:
            self._statistics.llm_calls += 1

    def after_model(self, callback_context: Any, llm_response: Any) -> None:
        del callback_context
        usage = llm_response.usage_metadata
        if usage is None:
            return
        with self._lock:
            self._statistics.tokens_in += usage.prompt_token_count or 0
            self._statistics.tokens_out += usage.candidates_token_count or 0

    def before_tool(self, tool: Any, args: dict, tool_context: Any) -> None:
        del tool, args, tool_context
        with self._lock:
            self._statistics.tool_calls += 1

    def snapshot(self) -> RunStatistics:
        with self._lock:
            return self._statistics.model_copy(deep=True)
