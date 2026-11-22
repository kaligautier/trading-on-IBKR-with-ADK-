"""HTTP read semantics shared by the reader's JSON resources."""

import logging
from copy import deepcopy
from time import monotonic
from typing import Any

from fastapi import FastAPI
from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.negotiation import accepts
from app.observability import log_event
from app.utils.logging_messages import LoggingMessages


class ReadHTTPPolicy:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        start = monotonic()
        head = scope["method"] == "HEAD"
        routed_scope = {**scope, "method": "GET"} if head else scope
        request_headers = Headers(scope=scope)
        accept_values = request_headers.getlist("accept")
        acceptable = accepts(
            ",".join(accept_values) if accept_values else None, "application/json"
        )
        suppress = head

        async def respond(message: Message) -> None:
            nonlocal suppress
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                allowed = headers.get("allow", "").split(", ")
                if "GET" in allowed and "HEAD" not in allowed:
                    headers["allow"] = ", ".join([*allowed, "HEAD"])
                if headers.get("content-type", "").startswith("application/json"):
                    headers.add_vary_header("Accept")
                    if not acceptable:
                        if message["status"] < 400:
                            message["status"] = 406
                        headers["content-length"] = "0"
                        del headers["content-type"]
                        suppress = True
                log_event(
                    logging.INFO,
                    request_headers.get("traceparent"),
                    {
                        "event": LoggingMessages.HTTP_COMPLETED,
                        "request_id": headers.get("X-Request-ID", ""),
                        "method": scope["method"],
                        "route": getattr(
                            routed_scope.get("route"), "path", "unmatched"
                        ),
                        "status": message["status"],
                        "duration_ms": round((monotonic() - start) * 1000, 2),
                    },
                )
            elif message["type"] == "http.response.body" and suppress:
                message = {**message, "body": b""}
            await send(message)

        await self.app(routed_scope, receive, respond)


def install_head_schema(app: FastAPI) -> None:
    original = app.openapi

    def schema() -> dict[str, Any]:
        document = original()
        for operations in document["paths"].values():
            for operation in operations.values():
                # Validation errors are served as AIP-193 400 INVALID_ARGUMENT.
                operation["responses"].pop("422", None)
            if "get" not in operations or "head" in operations:
                continue
            operation = deepcopy(operations["get"])
            operation["operationId"] = "head_" + operation["operationId"]
            for response in operation["responses"].values():
                response.pop("content", None)
            operations["head"] = operation
        return document

    app.openapi = schema  # type: ignore[method-assign]
