"""Main FastAPI application for ExitLens backend.

Handles application startup, CORS configuration, request tracking middleware,
custom exception handling, and API routing.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from app.api.v1.routes import (
    analyses_router,
    capsules_router,
    dependencies_router,
    health_router,
    recommendations_router,
    verification_router,
)
from app.core.config import get_settings
from app.core.errors import (
    ExitLensError,
    exitlens_error_handler,
    get_current_request_id,
    http_exception_handler,
    path_safety_error_handler,
    request_id_ctx,
    unhandled_exception_handler,
    validation_error_handler,
)
from app.core.ids import generate_request_id
from app.core.logging import get_logger, setup_logging
from app.core.paths import PathSafetyError

settings = get_settings()
setup_logging(settings.LOG_LEVEL)
logger = get_logger("exitlens.main")


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Middleware that assigns a unique request_id to each incoming request."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Honor client-supplied X-Request-ID if present and safe, otherwise generate one
        incoming_id = request.headers.get("X-Request-ID")
        req_id = incoming_id if incoming_id and len(incoming_id) <= 64 else generate_request_id()

        request.state.request_id = req_id
        token = request_id_ctx.set(req_id)

        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = req_id
            return response
        finally:
            request_id_ctx.reset(token)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager for startup and shutdown events."""
    logger.info(
        "Starting ExitLens backend [env=%s, host=%s, port=%d, provider=%s, model=%s]",
        settings.APP_ENV,
        settings.APP_HOST,
        settings.APP_PORT,
        settings.GEMMA_PROVIDER,
        settings.GEMMA_MODEL,
    )
    # Ensure storage data directory is accessible on startup
    try:
        data_dir = settings.get_canonical_data_dir()
        data_dir.mkdir(parents=True, exist_ok=True)
        logger.info("Storage directory verified: %s", data_dir)
    except Exception as exc:
        logger.error("Failed to initialize storage directory: %s", exc)

    yield

    logger.info("Stopping ExitLens backend.")


def create_app() -> FastAPI:
    """Build and configure the FastAPI application instance."""
    app = FastAPI(
        title="ExitLens Backend",
        description="Local-first dependency migration analysis and capsule export platform.",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # 1. Request ID Tracking Middleware
    app.add_middleware(RequestIdMiddleware)

    # 2. CORS Middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )

    # 3. Exception Handlers
    app.add_exception_handler(ExitLensError, exitlens_error_handler)
    app.add_exception_handler(PathSafetyError, path_safety_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)

    # 4. Route Registration
    app.include_router(health_router, prefix=settings.API_PREFIX)
    app.include_router(analyses_router, prefix=settings.API_PREFIX)
    app.include_router(dependencies_router, prefix=settings.API_PREFIX)
    app.include_router(recommendations_router, prefix=settings.API_PREFIX)
    app.include_router(verification_router, prefix=settings.API_PREFIX)
    app.include_router(capsules_router, prefix=settings.API_PREFIX)

    @app.get("/", summary="Root status", include_in_schema=False)
    async def root() -> dict:
        return {
            "name": "ExitLens Backend",
            "version": "0.1.0",
            "docs": "/docs",
            "health": f"{settings.API_PREFIX}/health",
        }

    return app


app = create_app()
