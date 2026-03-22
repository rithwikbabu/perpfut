"""Uvicorn launcher for the operator API."""

from __future__ import annotations

import uvicorn


def run_api_server(*, host: str, port: int) -> None:
    uvicorn.run("perpfut.api:create_app", host=host, port=port, factory=True)
