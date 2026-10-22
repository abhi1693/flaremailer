from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from importlib.metadata import version

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import RequestResponseEndpoint
from starlette.responses import Response

from app.config import Settings, get_settings
from app.database import create_engine, create_schema, create_session_factory
from app.routers import (
    api_keys,
    auth,
    credentials,
    domains,
    emails,
    projects,
    suppressions,
    templates,
)
from app.schemas import HealthResponse

logger = logging.getLogger("flaremailer.api")


def create_app(settings: Settings | None = None) -> FastAPI:
    app_settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        engine = create_engine(app_settings)
        app.state.engine = engine
        app.state.session_factory = create_session_factory(engine)
        if app_settings.database_auto_create:
            await create_schema(engine)
        try:
            yield
        finally:
            await engine.dispose()

    app = FastAPI(
        title="Flaremailer API",
        summary="Transactional email control plane for Cloudflare Email Service",
        description=(
            "Manage projects, senders, templates, suppressions, and a durable email outbox. "
            "A successful provider send means accepted by Cloudflare, not inbox delivery."
        ),
        version=version("flaremailer-backend"),
        lifespan=lifespan,
        openapi_url="/openapi.json",
        docs_url="/docs",
        redoc_url="/redoc",
    )
    app.state.settings = app_settings
    app.add_middleware(
        CORSMiddleware,
        allow_origins=app_settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Idempotency-Key", "X-API-Key"],
    )

    @app.middleware("http")
    async def enforce_request_size(
        request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                too_large = int(content_length) > app_settings.max_request_bytes
            except ValueError:
                too_large = True
            if too_large:
                return _error_response(
                    status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    "request_too_large",
                    "Request body exceeds the configured size limit",
                )
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_exception(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        if isinstance(exc.detail, dict) and "code" in exc.detail:
            payload = exc.detail
        else:
            payload = {"code": "http_error", "message": str(exc.detail)}
        return JSONResponse(
            status_code=exc.status_code, content={"error": payload}, headers=exc.headers
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        logger.exception(
            "Unhandled API error",
            extra={"method": request.method, "path": request.url.path},
            exc_info=exc,
        )
        return _error_response(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "internal_error",
            "An unexpected error occurred",
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        errors = []
        for item in exc.errors():
            normalized = dict(item)
            # Validation errors can otherwise echo passwords and provider tokens.
            normalized.pop("input", None)
            context = normalized.get("ctx")
            if isinstance(context, dict):
                normalized["ctx"] = {key: str(value) for key, value in context.items()}
            errors.append(normalized)
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": {
                    "code": "validation_error",
                    "message": "Request validation failed",
                    "details": errors,
                }
            },
        )

    @app.get(
        "/healthz",
        response_model=HealthResponse,
        tags=["health"],
        operation_id="healthGet",
    )
    async def health() -> HealthResponse:
        return HealthResponse(status="ok")

    @app.get(
        "/readyz",
        response_model=HealthResponse,
        tags=["health"],
        operation_id="readinessGet",
    )
    async def readiness(request: Request) -> HealthResponse:
        try:
            async with request.app.state.session_factory() as session:
                await session.execute(text("SELECT 1"))
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={"code": "database_unavailable", "message": "Database is unavailable"},
            ) from exc
        return HealthResponse(status="ok")

    prefix = "/api/v1"
    app.include_router(auth.router, prefix=prefix)
    app.include_router(projects.router, prefix=prefix)
    app.include_router(credentials.router, prefix=prefix)
    app.include_router(api_keys.router, prefix=prefix)
    app.include_router(domains.router, prefix=prefix)
    app.include_router(templates.router, prefix=prefix)
    app.include_router(suppressions.router, prefix=prefix)
    app.include_router(emails.router, prefix=prefix)
    app.include_router(emails.metrics_router, prefix=prefix)
    return app


def _error_response(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message}},
    )


app = create_app()
