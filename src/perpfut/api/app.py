"""FastAPI application factory."""

from __future__ import annotations

from fastapi import FastAPI

from .routers.health import router as health_router


def create_app() -> FastAPI:
    app = FastAPI(
        title="perpfut operator api",
        version="0.1.0",
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
    )

    api = FastAPI(
        title="perpfut operator api",
        version="0.1.0",
    )
    api.include_router(health_router)
    app.mount("/api", api)
    return app
