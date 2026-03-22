"""Health endpoints."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter

from ... import __version__
from ..schemas import HealthResponse


router = APIRouter(tags=["system"])


@router.get("/health", response_model=HealthResponse)
def read_health() -> HealthResponse:
    return HealthResponse(
        version=__version__,
        time_utc=datetime.now(timezone.utc),
    )
