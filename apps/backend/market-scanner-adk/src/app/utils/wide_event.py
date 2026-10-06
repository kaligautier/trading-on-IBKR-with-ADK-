"""Request-scoped structured event enriched throughout one HTTP request."""

from __future__ import annotations

import contextvars
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class WideEventScope:
    """Tokens required to restore the previous request context."""

    event_token: contextvars.Token[dict[str, Any] | None]
    request_id_token: contextvars.Token[str | None]


class WideEvent:
    """Collect one canonical event without coupling callers to its lifecycle."""

    def __init__(self) -> None:
        self._event: contextvars.ContextVar[dict[str, Any] | None] = (
            contextvars.ContextVar("wide_event", default=None)
        )
        self._request_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
            "wide_event_request_id", default=None
        )

    def start(
        self,
        fields: dict[str, Any] | None = None,
        *,
        request_id: str | None = None,
    ) -> WideEventScope:
        event = dict(fields or {})
        if request_id is not None:
            event["request_id"] = request_id
        return WideEventScope(
            event_token=self._event.set(event),
            request_id_token=self._request_id.set(request_id),
        )

    def reset(self, scope: WideEventScope) -> None:
        self._event.reset(scope.event_token)
        self._request_id.reset(scope.request_id_token)

    def current(self) -> dict[str, Any] | None:
        return self._event.get()

    def request_id(self) -> str | None:
        return self._request_id.get()

    def add(self, **fields: Any) -> None:
        event = self._event.get()
        if event is None:
            return
        event.update({key: value for key, value in fields.items() if value is not None})

    def append(self, key: str, value: Any) -> None:
        event = self._event.get()
        if event is None:
            return
        items = event.setdefault(key, [])
        if len(items) < 100:
            items.append(value)
        else:
            self.increment(f"{key}.dropped")

    def increment(self, key: str, amount: int = 1) -> None:
        event = self._event.get()
        if event is None:
            return
        event[key] = event.get(key, 0) + amount


wide_event = WideEvent()
