"""Pydantic models for the operator API contract."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = "ok"
    service: str = "perpfut-api"
    version: str
    time_utc: datetime


class RunSummaryResponse(BaseModel):
    run_id: str
    created_at: str | None = None
    mode: str | None = None
    product_id: str | None = None
    resumed_from_run_id: str | None = None


class RunsListResponse(BaseModel):
    items: list[RunSummaryResponse]
    count: int


class ArtifactDocumentResponse(BaseModel):
    run_id: str
    data: dict[str, Any]


class ArtifactListResponse(BaseModel):
    run_id: str
    items: list[dict[str, Any]]
    count: int


class DashboardOverviewResponse(BaseModel):
    mode: str
    generated_at: datetime
    latest_run: RunSummaryResponse | None = None
    latest_state: dict[str, Any] | None = None
    recent_events: list[dict[str, Any]] = Field(default_factory=list)
    recent_fills: list[dict[str, Any]] = Field(default_factory=list)
    recent_positions: list[dict[str, Any]] = Field(default_factory=list)


class PaperRunRequest(BaseModel):
    product_id: str = Field(alias="productId")
    iterations: int
    interval_seconds: int = Field(alias="intervalSeconds")
    starting_collateral_usdc: float = Field(alias="startingCollateralUsdc")

    model_config = {
        "populate_by_name": True,
    }


class PaperRunStatusResponse(BaseModel):
    active: bool
    pid: int | None = None
    started_at: str | None = None
    run_id: str | None = None
    product_id: str | None = None
    iterations: int | None = None
    interval_seconds: int | None = None
    starting_collateral_usdc: float | None = None
    log_path: str | None = None
