"""Bounded JSON response policy at the ASGI boundary, shared by every route."""

import hmac
import json
import logging
import re
from collections.abc import Callable, Mapping
from time import monotonic
from traceback import walk_tb
from urllib.parse import parse_qsl
from uuid import uuid4

from starlette.datastructures import Headers, QueryParams
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.config.settings import Settings
from app.dto.response.error_response import ERROR_MEDIA_TYPE, error_bytes
from app.observability import log_event, trace_fields
from app.presentation.http.conditional import precondition, representation_tag
from app.presentation.http.negotiation import HTTP_WORD, accepts, accepts_identity
from app.utils.error import (
    WIRE_CODES,
    AppError,
    ErrorCode,
    InvalidArgumentError,
    MissingCredentialsError,
)
from app.utils.logging_messages import LoggingMessages

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
        query_parameters: Mapping[str, frozenset[str]],
    ) -> None:
        self.app, self.settings, self.route_name = app, settings, route_name
        self.query_parameters = query_parameters

    def authorize(self, scope: Scope, headers: Headers) -> None:
        if scope["path"] == "/health":
            return
        credentials = headers.getlist("authorization")
        query = parse_qsl(
            scope.get("query_string", b"").decode("latin-1"), keep_blank_values=True
        )
        if len(credentials) > 1 or any(key == "access_token" for key, _ in query):
            raise AppError(ErrorCode.INVALID_REQUEST)
        if self.settings.AUTH_MODE == "cloud_run":
            # Deployment requires enforced Cloud Run IAM and no anonymous invokers.
            # Google ingress, not this container, verifies its identity token.
            return
        if not credentials:
            raise MissingCredentialsError()
        scheme, _, credential = credentials[0].partition(" ")
        credential = credential.lstrip(" ")
        if not re.fullmatch(HTTP_WORD, scheme):
            raise AppError(ErrorCode.INVALID_REQUEST)
        if scheme.lower() != "bearer":
            raise MissingCredentialsError()
        if not re.fullmatch(r"[A-Za-z0-9._~+/-]+=*", credential):
            raise AppError(ErrorCode.INVALID_REQUEST)
        if not hmac.compare_digest(
            credential, self.settings.API_TOKEN.get_secret_value()
        ):
            raise AppError(ErrorCode.UNAUTHENTICATED)

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
            if method in {"GET", "HEAD"}:
                self._validate_query(scope, route)
            response = await self._dispatch(scope, receive, headers)
            if response is None:
                return
            status, response_headers, body = response
        except AppError as error:
            status, response_headers, body = self._error_response(error)
        except Exception as error:
            # Log code locations, never exception messages, source lines or locals.
            sources = [
                f"{frame.f_globals.get('__name__')}:{line}"
                for frame, line in walk_tb(error.__traceback__)
                if str(frame.f_globals.get("__name__", "")).startswith("app.")
            ]
            log_event(
                logging.ERROR,
                LoggingMessages.REQUEST_FAILED,
                request_id=request_id,
                exception_type=type(error).__name__,
                source=sources[-1] if sources else "unknown",
                **trace,
            )
            status, body = 500, error_bytes(AppError(ErrorCode.INTERNAL_ERROR))
            response_headers = [(b"content-type", ERROR_MEDIA_TYPE.encode())]
        category = self._category(status, body)
        if status >= 400 and (
            not accepts(combined("accept"), ERROR_MEDIA_TYPE)
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
            LoggingMessages.REQUEST_COMPLETED,
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
            raise AppError(ErrorCode.NOT_IMPLEMENTED)
        if route is None:
            raise AppError(ErrorCode.NOT_FOUND)
        allowed = (
            {"POST", "OPTIONS"}
            if route == "/v1/suggestions"
            else {"GET", "HEAD", "OPTIONS"}
        )
        if method not in allowed:
            raise AppError(ErrorCode.METHOD_NOT_ALLOWED)

    def _validate_query(self, scope: Scope, route: str | None) -> None:
        allowed = self.query_parameters.get(route or "", frozenset())
        query = QueryParams(scope.get("query_string", b""))
        if any(key not in allowed or len(query.getlist(key)) != 1 for key in query):
            raise InvalidArgumentError()

    async def _dispatch(
        self, scope: Scope, receive: Receive, headers: Headers
    ) -> tuple[int, list[tuple[bytes, bytes]], bytes] | None:
        if scope["method"] == "OPTIONS":
            return 204, [], b""
        if scope["method"] == "POST":
            return await self._post(scope, receive, headers)
        # Read no more than one chunk when a body is present. Bodyless
        # reads are not replayed, buffered or passed on to dependencies.
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return None
            if message.get("body"):
                raise InvalidArgumentError()
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

    async def _post(
        self, scope: Scope, receive: Receive, headers: Headers
    ) -> tuple[int, list[tuple[bytes, bytes]], bytes] | None:
        # Validate representation before any write, so an unacceptable response
        # cannot commit a suggestion and then misleadingly report HTTP 406.
        if not accepts(
            ",".join(headers.getlist("accept")) or None, "application/json"
        ) or not accepts_identity(",".join(headers.getlist("accept-encoding")) or None):
            raise AppError(ErrorCode.NOT_ACCEPTABLE)
        if (
            headers.get("content-type", "").split(";", 1)[0].strip().lower()
            != "application/json"
        ):
            raise AppError(ErrorCode.UNSUPPORTED_MEDIA_TYPE)
        if headers.get("if-match") or headers.get("if-none-match"):
            raise InvalidArgumentError()
        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return None
            body.extend(message.get("body", b""))
            if len(body) > 4096:
                raise AppError(ErrorCode.PAYLOAD_TOO_LARGE)
            if not message.get("more_body", False):
                break
        messages: list[Message] = []

        async def replay() -> Message:
            return {"type": "http.request", "body": bytes(body), "more_body": False}

        async def capture(message: Message) -> None:
            messages.append(message)

        await self.app(scope, replay, capture)
        start = next(m for m in messages if m["type"] == "http.response.start")
        return (
            start["status"],
            start.get("headers", []),
            b"".join(m.get("body", b"") for m in messages),
        )

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
                raise AppError(ErrorCode.NOT_ACCEPTABLE)
            tag = representation_tag(body)
            response_headers.append((b"etag", tag.encode()))
            try:
                conditional = precondition(
                    tag, combined("if-match"), combined("if-none-match")
                )
            except ValueError:
                raise InvalidArgumentError() from None
            if conditional == 412:
                raise AppError(ErrorCode.PRECONDITION_FAILED)
            if conditional == 304:
                status, body = 304, b""
        return status, response_headers, body

    @staticmethod
    def _error_response(
        error: AppError,
    ) -> tuple[int, list[tuple[bytes, bytes]], bytes]:
        status = error.status_code
        body = error_bytes(error) if error.has_body else b""
        response_headers = [(b"content-type", ERROR_MEDIA_TYPE.encode())]
        if status == 401 or error.error_code is ErrorCode.INVALID_REQUEST:
            challenge = 'Bearer realm="momentum-api"'
            if error.has_body:
                challenge += f', error="{error.error_code.value.replace("-", "_")}"'
            response_headers.append((b"www-authenticate", challenge.encode()))
        return status, response_headers, body

    @staticmethod
    def _category(status: int, body: bytes) -> str:
        category = "SUCCESS"
        if status >= 400:
            category = "UNAUTHENTICATED" if status == 401 else "INTERNAL_ERROR"
            if body:
                candidate = json.loads(body).get("error", {}).get("code")
                if candidate in WIRE_CODES.values():
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
            allowed = "POST, OPTIONS" if route == "/v1/suggestions" else ALLOW
            response_headers.append((b"allow", allowed.encode()))
        if status not in {204, 304}:
            response_headers.append((b"content-length", str(len(body)).encode()))
        return response_headers
