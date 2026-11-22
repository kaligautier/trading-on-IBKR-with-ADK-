"""Reject concurrent database-backed HTTP work before model/session execution."""

from app.dto.response.error_response import error_response
from app.services.admission import ScannerBusyError, admit_scan
from app.utils.error import ScannerBusyHTTPError


class ScannerAdmissionMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] not in {"http", "websocket"} or scope["path"] in {
            "/health",
            "/internal/v1/scan-jobs",
        }:
            await self.app(scope, receive, send)
            return
        try:
            async with admit_scan():
                await self.app(scope, receive, send)
        except ScannerBusyError:
            if scope["type"] == "websocket":
                await send({"type": "websocket.close", "code": 1013})
            else:
                await error_response(ScannerBusyHTTPError())(scope, receive, send)
