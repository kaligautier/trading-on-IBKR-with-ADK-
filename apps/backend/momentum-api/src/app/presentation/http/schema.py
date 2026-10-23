"""Document the ASGI HTTP policy in the executable OpenAPI contract."""

from copy import deepcopy
from http import HTTPStatus
from typing import Any

from fastapi import FastAPI

from app.presentation.http.problems import DETAILS, PROBLEM_BASE

ERRORS = {400, 401, 404, 405, 406, 412, 500, 503}


def install_schema(app: FastAPI) -> None:
    original = app.openapi

    def schema() -> dict[str, Any]:
        if app.openapi_schema is not None:
            return app.openapi_schema
        document = original()
        components = document.setdefault("components", {})
        components.setdefault("schemas", {}).pop("HTTPValidationError", None)
        components["schemas"].pop("ValidationError", None)
        components["schemas"]["Problem"] = {
            "type": "object",
            "required": ["type", "title", "status", "detail", "code"],
            "properties": {
                "type": {"type": "string", "format": "uri"},
                "title": {"type": "string"},
                "status": {"type": "integer", "minimum": 400, "maximum": 599},
                "detail": {"type": "string"},
                "code": {"type": "string"},
            },
            "description": "RFC 9457; absent when the error format is unacceptable. "
            "Missing credentials produce a bodyless Bearer challenge.",
        }
        components["securitySchemes"] = {
            "Bearer": {
                "type": "http",
                "scheme": "bearer",
                "description": "Opaque local token or Cloud Run identity token.",
            }
        }
        components["headers"] = {
            name: {"schema": {"type": "string"}, "description": desc}
            for name, desc in {
                "ETag": "Strong validator of exact successful JSON bytes.",
                "Request-ID": "Server-generated request correlation UUID.",
                "Cache-Control": "Always no-store.",
                "Vary": "Accept, Accept-Encoding.",
                "Allow": "GET, HEAD, OPTIONS for this resource.",
                "WWW-Authenticate": "Bearer challenge with optional OAuth error.",
            }.items()
        }
        common = {
            name: {"$ref": f"#/components/headers/{name}"}
            for name in ("Request-ID", "Cache-Control", "Vary")
        }
        components["responses"] = {}
        for status in sorted(ERRORS):
            headers = deepcopy(common)
            if status in {400, 401}:
                headers["WWW-Authenticate"] = {
                    "$ref": "#/components/headers/WWW-Authenticate"
                }
            if status == 405:
                headers["Allow"] = {"$ref": "#/components/headers/Allow"}
            components["responses"][str(status)] = {
                "description": HTTPStatus(status).phrase,
                "headers": headers,
                "content": {
                    "application/problem+json": {
                        "schema": {"$ref": "#/components/schemas/Problem"}
                    }
                },
            }
        document["paths"]["/openapi.json"] = {
            "get": {
                "operationId": "get_openapi",
                "summary": "Authenticated executable contract",
                "responses": {
                    "200": {
                        "description": "OpenAPI document",
                        "content": {"application/json": {"schema": {"type": "object"}}},
                    }
                },
            }
        }
        for path, operations in document["paths"].items():
            operation = operations["get"]
            operation["security"] = [] if path == "/health" else [{"Bearer": []}]
            responses = operation["responses"]
            responses.pop("422", None)
            for status in sorted(ERRORS - ({401} if path == "/health" else set())):
                responses[str(status)] = {"$ref": f"#/components/responses/{status}"}
            responses["200"]["headers"] = {
                **common,
                "ETag": {"$ref": "#/components/headers/ETag"},
            }
            responses["304"] = {
                "description": "Not Modified; no content.",
                "headers": deepcopy(responses["200"]["headers"]),
            }
            operation.setdefault("parameters", []).extend(
                [
                    {
                        "in": "header",
                        "name": name,
                        "required": False,
                        "schema": {"type": "string"},
                    }
                    for name in (
                        "Accept",
                        "Accept-Encoding",
                        "If-Match",
                        "If-None-Match",
                    )
                ]
            )
            head = deepcopy(operation)
            head["operationId"] = "head_" + operation["operationId"]
            head["summary"] = "Metadata only: " + operation.get("summary", "")
            head["responses"] = {
                status: {
                    "description": HTTPStatus(int(status)).phrase,
                    "headers": deepcopy(common),
                }
                for status in responses
            }
            head["responses"]["200"]["headers"]["ETag"] = {
                "$ref": "#/components/headers/ETag"
            }
            head["responses"]["304"]["headers"]["ETag"] = {
                "$ref": "#/components/headers/ETag"
            }
            for head_status in ("400", "401"):
                if head_status in head["responses"]:
                    head["responses"][head_status]["headers"]["WWW-Authenticate"] = {
                        "$ref": "#/components/headers/WWW-Authenticate"
                    }
            head["responses"]["405"]["headers"]["Allow"] = {
                "$ref": "#/components/headers/Allow"
            }
            operations["head"] = head
            operations["options"] = {
                "operationId": "options_" + operation["operationId"],
                "summary": "Allowed methods; does not configure browser CORS.",
                "security": deepcopy(operation["security"]),
                "parameters": [
                    deepcopy(parameter)
                    for parameter in operation.get("parameters", [])
                    if parameter["in"] == "path"
                ],
                "responses": {
                    "204": {
                        "description": "No content.",
                        "headers": {
                            **common,
                            "Allow": {"$ref": "#/components/headers/Allow"},
                        },
                    },
                    **(
                        {}
                        if path == "/health"
                        else {"401": {"$ref": "#/components/responses/401"}}
                    ),
                },
            }
        document["info"]["description"] = (
            "Private read-only Momentum catalogue. UTC dates/timestamps; finite JSON. "
            "Lists are ordered by created_at DESC, id DESC, with filter-bound keyset "
            "tokens and no snapshot guarantee under concurrent updates. "
            "Latest selects one winner per ticker before rating filters. "
            "Unknown ticker returns an empty page. GET/HEAD bodies and duplicate or "
            "unknown query parameters are rejected. Error types: "
            + PROBLEM_BASE
            + ", ".join(DETAILS)
        )
        app.openapi_schema = document
        return document

    app.openapi = schema  # type: ignore[method-assign]
