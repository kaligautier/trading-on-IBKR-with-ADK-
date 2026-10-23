"""Bounded JSON response policy at the ASGI boundary, shared by every route."""

import hmac
import json
import logging
import re
from collections.abc import Callable
from time import monotonic
from urllib.parse import parse_qsl
from uuid import uuid4

from starlette.datastructures import Headers
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.config import Settings
from app.http.conditional import precondition, representation_tag
from app.http.negotiation import HTTP_WORD, accepts, accepts_identity
from app.http.problems import CODES, APIError, problem_bytes

LOGGER = logging.getLogger("momentum_api")
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
        headers, method = Headers(scope=scope), scope["method"]

        def combined(name: str) -> str | None:
            values = headers.getlist(name)
            return ",".join(values) if values else None

        route = self.route_name(scope)
        status, response_headers, body = 500, [], b""
        try:
            self.authorize(scope, headers)
            if method not in METHODS:
                raise APIError(501, "not-implemented")
            if route is None:
                raise APIError(404, "not-found")
            if method not in {"GET", "HEAD", "OPTIONS"}:
                raise APIError(405, "method-not-allowed")
            if method == "OPTIONS":
                status = 204
            else:
                # Read no more than one chunk when a body is present. Bodyless
                # reads are not replayed, buffered or passed on to dependencies.
                while True:
                    message = await receive()
                    if message["type"] == "http.disconnect":
                        return
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
        except APIError as error:
            status, body = error.status, problem_bytes(error) if error.code else b""
            response_headers = [(b"content-type", b"application/problem+json")]
            if status == 401 or error.code == "invalid-request":
                challenge = 'Bearer realm="momentum-api"'
                if error.code:
                    challenge += f', error="{error.code.replace("-", "_")}"'
                response_headers.append((b"www-authenticate", challenge.encode()))
        except Exception:
            # Categories only: driver/framework exception text can contain secrets.
            status, body = 500, problem_bytes(APIError(500, "internal-error"))
            response_headers = [(b"content-type", b"application/problem+json")]
        request_id = str(uuid4())
        category = "SUCCESS"
        if status >= 400:
            category = "UNAUTHENTICATED" if status == 401 else "INTERNAL_ERROR"
            if body:
                candidate = json.loads(body).get("code")
                if candidate in CODES.values():
                    category = candidate
        if status >= 400 and (
            not accepts(combined("accept"), "application/problem+json")
            or not accepts_identity(combined("accept-encoding"))
        ):
            body = b""
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
        LOGGER.info(
            "request_id=%s route=%s status=%d category=%s duration_ms=%.1f",
            request_id,
            route or "unknown",
            status,
            category,
            (monotonic() - started) * 1000,
        )
