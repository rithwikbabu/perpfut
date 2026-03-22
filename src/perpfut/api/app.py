"""FastAPI application factory."""

from __future__ import annotations

from fastapi import FastAPI

from .routers.dashboard import router as dashboard_router
from .routers.health import router as health_router
from .routers.paper_runs import router as paper_runs_router
from .routers.runs import router as runs_router


def create_app() -> FastAPI:
    app = FastAPI(
        title="perpfut operator api",
        version="0.1.0",
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
    )
    app.include_router(health_router, prefix="/api")
    app.include_router(dashboard_router, prefix="/api")
    app.include_router(paper_runs_router, prefix="/api")
    app.include_router(runs_router, prefix="/api")
    return app
