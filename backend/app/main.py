"""QS Intelligence USA - API application entry point."""

from __future__ import annotations

import logging
import uuid
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.core.config import get_settings
from app.core.db import get_engine
from app.core.errors import install_error_handlers
from app.domains.audit.router import router as audit_router
from app.domains.budgets.router import router as budgets_router
from app.domains.change_orders.router import router as change_orders_router
from app.domains.companies.router import router as companies_router
from app.domains.contracts.router import router as contracts_router
from app.domains.cost_codes.router import router as cost_codes_router
from app.domains.cost_management.router import router as cost_management_router
from app.domains.dashboard.router import router as dashboard_router
from app.domains.documents.router import router as documents_router
from app.domains.estimating.router import router as estimating_router
from app.domains.identity.router import router as auth_router
from app.domains.projects.router import router as projects_router
from app.domains.projects.router import vocab_router
from app.domains.tenancy.router import router as tenancy_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

API_PREFIX = "/api/v1"


def create_app() -> FastAPI:
    settings = get_settings()
    docs_enabled = settings.environment in ("development", "test")
    app = FastAPI(
        title="QS Intelligence USA API",
        version="0.1.0",
        description="The AI Commercial Operating System for Construction.",
        docs_url=f"{API_PREFIX}/docs" if docs_enabled else None,
        redoc_url=None,
        openapi_url=f"{API_PREFIX}/openapi.json" if docs_enabled else None,
    )
    install_error_handlers(app)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Content-Type", "Authorization", "X-Tenant-ID", "X-CSRF-Token", "X-Request-ID"],
    )

    @app.middleware("http")
    async def security_headers(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
        response = await call_next(request)
        response.headers.setdefault("X-Request-ID", request_id)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        if request.url.path.startswith(API_PREFIX) and "Cache-Control" not in response.headers:
            response.headers["Cache-Control"] = "no-store"
        if settings.cookie_secure:
            response.headers.setdefault("Strict-Transport-Security", "max-age=63072000; includeSubDomains")
        return response

    for router in (auth_router, tenancy_router, projects_router, vocab_router, companies_router,
                   documents_router, audit_router, dashboard_router, cost_codes_router, estimating_router,
                   budgets_router, contracts_router, change_orders_router, cost_management_router):
        app.include_router(router, prefix=API_PREFIX)

    @app.get(f"{API_PREFIX}/health", tags=["system"])
    def health() -> dict[str, str]:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "ok", "database": "ok"}

    return app


app = create_app()
