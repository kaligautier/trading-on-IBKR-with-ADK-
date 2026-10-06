"""Pure ASGI middleware emitting one canonical event per HTTP request."""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from app.config.settings import settings
from app.utils.wide_event import wide_event

Scope = dict[str, Any]
Message = dict[str, Any]
Receive = Callable[[], Awaitable[Message]]
Send = Callable[[Message], Awaitable[None]]
ASGIApp = Callable[[Scope, Receive, Send], Awaitable[None]]

logger = logging.getLogger("app.request")


class CorrelatedResponseSender:
    """Capture the response status and expose the request identifier."""

    def __init__(self, send: Send, request_id: str) -> None:
        self._send = send
        self._request_id = request_id
        self.status_code: int | None = None
        self.completed = False

    async def __call__(self, message: Message) -> None:
        if message["type"] == "http.response.start":
            self.status_code = message["status"]
            headers = message.setdefault("headers", [])
            headers.append((b"x-request-id", self._request_id.encode("latin-1")))
        await self._send(message)
        if message["type"] == "http.response.body" and not message.get(
            "more_body", False
        ):
            self.completed = True


class WideEventMiddleware:
    """Own the lifecycle and single emission of a request wide event."""

    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope.get("type") != "http":
            await self._app(scope, receive, send)
            return
        await self._handle_http(scope, receive, send)

    async def _handle_http(self, scope: Scope, receive: Receive, send: Send) -> None:
        request_id = self._header(scope, b"x-request-id") or uuid.uuid4().hex
        event_scope = wide_event.start(
            self._initial_fields(scope), request_id=request_id
        )
        response_sender = CorrelatedResponseSender(send, request_id)
        started = time.perf_counter()
        disconnected = False

        async def observe_receive() -> Message:
            nonlocal disconnected
            message = await receive()
            if message["type"] == "http.disconnect":
                disconnected = True
            return message

        try:
            await self._app(scope, observe_receive, response_sender)
        except asyncio.CancelledError as error:
            self._finish_request(response_sender, error=error, cancelled=True)
            self._emit(started, logging.WARNING)
            raise
        except Exception as error:
            self._finish_request(response_sender, error=error)
            self._emit(started, logging.ERROR)
            raise
        else:
            self._finish_request(
                response_sender,
                cancelled=disconnected and not response_sender.completed,
            )
            outcome = (wide_event.current() or {}).get("outcome")
            level = self._level(response_sender.status_code or 500)
            if outcome == "failed":
                level = logging.ERROR
            elif outcome == "cancelled":
                level = logging.WARNING
            self._emit(started, level)
        finally:
            wide_event.reset(event_scope)

    @staticmethod
    def _initial_fields(scope: Scope) -> dict[str, Any]:
        fields = {
            "event": "http.request",
            "http.method": scope.get("method"),
            "http.path": scope.get("path"),
            "service": settings.PROJECT_NAME,
            "app.name": settings.APP_NAME,
            "app.version": settings.APP_VERSION,
        }
        return fields

    @staticmethod
    def _finish_request(
        response: CorrelatedResponseSender,
        *,
        error: BaseException | None = None,
        cancelled: bool = False,
    ) -> None:
        event = wide_event.current() or {}

        status_code = response.status_code
        if status_code is None and not cancelled:
            status_code = 500
        outcome = WideEventMiddleware._outcome(status_code or 500)
        if cancelled:
            outcome = "cancelled"
        elif error is not None:
            outcome = "server_error"
        elif event.get("persistence.status") == "error":
            outcome = "failed"
        wide_event.add(
            **{
                "http.status": status_code,
                "http.response_started": response.status_code is not None,
                "http.response_completed": response.completed,
                "outcome": outcome,
            }
        )
        if error is not None:
            wide_event.add(**{"error.kind": type(error).__name__})

    @staticmethod
    def _emit(started: float, level: int) -> None:
        event = wide_event.current()
        if event is None:
            return
        event["http.duration_ms"] = round(
            (time.perf_counter() - started) * 1000,
            2,
        )
        message = (
            f"{event.get('http.method', '-')} {event.get('http.path', '-')} "
            f"-> {event.get('http.status', '-')}"
        )
        logger.log(level, message, extra=event)

    @staticmethod
    def _header(scope: Scope, name: bytes) -> str | None:
        for key, value in scope.get("headers") or ():
            if key == name:
                return value.decode("latin-1")
        return None

    @staticmethod
    def _outcome(status_code: int) -> str:
        if status_code >= 500:
            return "server_error"
        if status_code >= 400:
            return "client_error"
        return "success"

    @staticmethod
    def _level(status_code: int) -> int:
        if status_code >= 500:
            return logging.ERROR
        if status_code >= 400:
            return logging.WARNING
        return logging.INFO
