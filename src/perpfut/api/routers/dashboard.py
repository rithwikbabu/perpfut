"""Overview endpoints for the operator dashboard."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Query

from ..repository import build_dashboard_overview
from ..schemas import DashboardOverviewResponse


router = APIRouter(tags=["dashboard"])


@router.get("/dashboard/overview", response_model=DashboardOverviewResponse)
def read_dashboard_overview(
    mode: Literal["paper", "live"] = Query(default="paper"),
    limit: int = Query(default=10, ge=1, le=200),
) -> DashboardOverviewResponse:
    return build_dashboard_overview(mode=mode, limit=limit)
