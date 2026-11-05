"""HTTP read semantics shared by the reader's JSON resources."""

from copy import deepcopy
from typing import Any

from fastapi import FastAPI
from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.negotiation import accepts


class ReadHTTPPolicy:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        head = scope["method"] == "HEAD"
        accept_values = Headers(scope=scope).getlist("accept")
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
            elif message["type"] == "http.response.body" and suppress:
                message = {**message, "body": b""}
            await send(message)

        await self.app({**scope, "method": "GET"} if head else scope, receive, respond)


def install_head_schema(app: FastAPI) -> None:
    original = app.openapi

    def schema() -> dict[str, Any]:
        document = original()
        for operations in document["paths"].values():
            if "get" not in operations or "head" in operations:
                continue
            operation = deepcopy(operations["get"])
            operation["operationId"] = "head_" + operation["operationId"]
            for response in operation["responses"].values():
                response.pop("content", None)
            operations["head"] = operation
        return document

    app.openapi = schema  # type: ignore[method-assign]
