"""Bounded JSON response policy at the ASGI boundary, shared by every route."""

import hmac
import json
import logging
import re
from collections.abc import Callable
from time import monotonic
from traceback import walk_tb
from urllib.parse import parse_qsl
from uuid import uuid4

from starlette.datastructures import Headers
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.config.settings import Settings
from app.observability import log_event, trace_fields
from app.presentation.http.conditional import precondition, representation_tag
from app.presentation.http.negotiation import HTTP_WORD, accepts, accepts_identity
from app.presentation.http.problems import CODES, APIError, problem_bytes

ALLOW = "GET, HEAD, OPTIONS"
METHODS = {
    "GET",
    "HEAD",
    "OPTIONS",
    "POST",
    "PUT",
    "PATCH",
    "DELETE",
    "TRACE",
    "CONNECT",
}


class HTTPPolicy:
    def __init__(
        self,
        app: ASGIApp,
        settings: Settings,
        route_name: Callable[[Scope], str | None],
    ) -> None:
        self.app, self.settings, self.route_name = app, settings, route_name

    def authorize(self, scope: Scope, headers: Headers) -> None:
        if scope["path"] == "/health":
            return
        credentials = headers.getlist("authorization")
        query = parse_qsl(
            scope.get("query_string", b"").decode("latin-1"), keep_blank_values=True
        )
        if len(credentials) > 1 or any(key == "access_token" for key, _ in query):
            raise APIError(400, "invalid-request")
        if self.settings.AUTH_MODE == "cloud_run":
            # Deployment requires enforced Cloud Run IAM and no anonymous invokers.
            # Google ingress, not this container, verifies its identity token.
            return
        if not credentials:
            raise APIError(401, "")
        scheme, _, credential = credentials[0].partition(" ")
        credential = credential.lstrip(" ")
        if not re.fullmatch(HTTP_WORD, scheme):
            raise APIError(400, "invalid-request")
        if scheme.lower() != "bearer":
            raise APIError(401, "")
        if not re.fullmatch(r"[A-Za-z0-9._~+/-]+=*", credential):
            raise APIError(400, "invalid-request")
        if not hmac.compare_digest(
            credential, self.settings.API_TOKEN.get_secret_value()
        ):
            raise APIError(401, "invalid-token")

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        started = monotonic()
        request_id = str(uuid4())
        headers, method = Headers(scope=scope), scope["method"]
        trace = trace_fields(headers.getlist("traceparent"))

        def combined(name: str) -> str | None:
            values = headers.getlist(name)
            return ",".join(values) if values else None

        route = self.route_name(scope)
        try:
            self.authorize(scope, headers)
            self._validate_method(method, route)
            response = await self._dispatch(scope, receive, headers)
            if response is None:
                return
            status, response_headers, body = response
        except APIError as error:
            status, response_headers, body = self._problem_response(error)
        except Exception as error:
            # Log code locations, never exception messages, source lines or locals.
            sources = [
                f"{frame.f_globals.get('__name__')}:{line}"
                for frame, line in walk_tb(error.__traceback__)
                if str(frame.f_globals.get("__name__", "")).startswith("app.")
            ]
            log_event(
                logging.ERROR,
                "request_failed",
                request_id=request_id,
                exception_type=type(error).__name__,
                source=sources[-1] if sources else "unknown",
                **trace,
            )
            status, body = 500, problem_bytes(APIError(500, "internal-error"))
            response_headers = [(b"content-type", b"application/problem+json")]
        category = self._category(status, body)
        if status >= 400 and (
            not accepts(combined("accept"), "application/problem+json")
            or not accepts_identity(combined("accept-encoding"))
        ):
            body = b""
        response_headers = self._headers(
            response_headers, body, status, route, request_id
        )
        await send(
            {
                "type": "http.response.start",
                "status": status,
                "headers": response_headers,
            }
        )
        await send(
            {"type": "http.response.body", "body": b"" if method == "HEAD" else body}
        )
        log_event(
            logging.INFO,
            "request_completed",
            request_id=request_id,
            route=route or "unknown",
            status=status,
            category=category,
            duration_ms=round((monotonic() - started) * 1000, 3),
            **trace,
        )

    @staticmethod
    def _validate_method(method: str, route: str | None) -> None:
        if method not in METHODS:
            raise APIError(501, "not-implemented")
        if route is None:
            raise APIError(404, "not-found")
        if method not in {"GET", "HEAD", "OPTIONS"}:
            raise APIError(405, "method-not-allowed")

    async def _dispatch(
        self, scope: Scope, receive: Receive, headers: Headers
    ) -> tuple[int, list[tuple[bytes, bytes]], bytes] | None:
        if scope["method"] == "OPTIONS":
            return 204, [], b""
        # Read no more than one chunk when a body is present. Bodyless
        # reads are not replayed, buffered or passed on to dependencies.
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return None
            if message.get("body"):
                raise APIError(400, "invalid-argument")
            if not message.get("more_body", False):
                break
        messages: list[Message] = []

        async def capture(message: Message) -> None:
            messages.append(message)

        async def empty_request() -> Message:
            return {"type": "http.request", "body": b"", "more_body": False}

        await self.app({**scope, "method": "GET"}, empty_request, capture)
        start = next(m for m in messages if m["type"] == "http.response.start")
        status = start["status"]
        response_headers = start.get("headers", [])
        body = b"".join(m.get("body", b"") for m in messages)
        return self._conditional_response(headers, status, response_headers, body)

    @staticmethod
    def _conditional_response(
        headers: Headers,
        status: int,
        response_headers: list[tuple[bytes, bytes]],
        body: bytes,
    ) -> tuple[int, list[tuple[bytes, bytes]], bytes]:
        def combined(name: str) -> str | None:
            values = headers.getlist(name)
            return ",".join(values) if values else None

        if status == 200:
            if not accepts(
                combined("accept"), "application/json"
            ) or not accepts_identity(combined("accept-encoding")):
                raise APIError(406, "not-acceptable")
            tag = representation_tag(body)
            response_headers.append((b"etag", tag.encode()))
            try:
                conditional = precondition(
                    tag, combined("if-match"), combined("if-none-match")
                )
            except ValueError:
                raise APIError(400, "invalid-argument") from None
            if conditional == 412:
                raise APIError(412, "precondition-failed")
            if conditional == 304:
                status, body = 304, b""
        return status, response_headers, body

    @staticmethod
    def _problem_response(
        error: APIError,
    ) -> tuple[int, list[tuple[bytes, bytes]], bytes]:
        status, body = error.status, problem_bytes(error) if error.code else b""
        response_headers = [(b"content-type", b"application/problem+json")]
        if status == 401 or error.code == "invalid-request":
            challenge = 'Bearer realm="momentum-api"'
            if error.code:
                challenge += f', error="{error.code.replace("-", "_")}"'
            response_headers.append((b"www-authenticate", challenge.encode()))
        return status, response_headers, body

    @staticmethod
    def _category(status: int, body: bytes) -> str:
        category = "SUCCESS"
        if status >= 400:
            category = "UNAUTHENTICATED" if status == 401 else "INTERNAL_ERROR"
            if body:
                candidate = json.loads(body).get("code")
                if candidate in CODES.values():
                    category = candidate
        return category

    @staticmethod
    def _headers(
        response_headers: list[tuple[bytes, bytes]],
        body: bytes,
        status: int,
        route: str | None,
        request_id: str,
    ) -> list[tuple[bytes, bytes]]:
        response_headers = [
            (key, value)
            for key, value in response_headers
            if key.lower() not in {b"content-length", b"cache-control", b"vary"}
            and not (key.lower() == b"content-type" and not body)
        ]
        response_headers.extend(
            [
                (b"cache-control", b"no-store"),
                (b"vary", b"Accept, Accept-Encoding"),
                (b"request-id", request_id.encode()),
            ]
        )
        if route is not None and status in {204, 405}:
            response_headers.append((b"allow", ALLOW.encode()))
        if status not in {204, 304}:
            response_headers.append((b"content-length", str(len(body)).encode()))
        return response_headers
