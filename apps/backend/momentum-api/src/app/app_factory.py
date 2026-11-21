"""Application factory; storage lifecycle is supplied by the standalone runtime."""

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.responses import Response
from starlette.routing import Match
from starlette.types import Scope

from app.config.settings import Settings
from app.domain.analyses.errors import ConsultationError
from app.presentation.http.middleware import HTTPPolicy
from app.presentation.http.problems import problem_bytes
from app.presentation.http.schema import install_schema
from app.presentation.routes.analyses import QUERY_PARAMETERS, router
from app.presentation.routes.suggestions import router as suggestions_router
from app.utils.error import AppError, InvalidArgumentError

Lifespan = Callable[[FastAPI], AbstractAsyncContextManager[None]]


def create_app(settings: Settings, lifespan: Lifespan | None = None) -> FastAPI:
    app = FastAPI(
        title="Momentum consultation API",
        version="0.1.0",
        docs_url=None,
        redoc_url=None,
        lifespan=lifespan,
    )

    @app.get("/health", operation_id="health", tags=["operations"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.exception_handler(AppError)
    async def application_error(_: Request, error: AppError) -> Response:
        return Response(
            problem_bytes(error),
            status_code=error.status_code,
            media_type="application/problem+json",
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, error: RequestValidationError) -> Response:
        return await application_error(_, InvalidArgumentError())

    @app.exception_handler(ConsultationError)
    async def consultation_error(_: Request, error: ConsultationError) -> Response:
        return await application_error(_, AppError.from_domain(error))

    def route_name(scope: Scope) -> str | None:
        for route in [*app.routes, *router.routes, *suggestions_router.routes]:
            path = getattr(route, "path", None)
            if path is None:
                continue
            match, _ = route.matches({**scope, "method": "GET"})
            if match in {Match.FULL, Match.PARTIAL}:
                return str(path)
        return None

    app.state.settings = settings
    app.include_router(router)
    app.include_router(suggestions_router)
    app.add_middleware(
        HTTPPolicy,
        settings=settings,
        route_name=route_name,
        query_parameters=QUERY_PARAMETERS,
    )
    install_schema(app)
    return app
