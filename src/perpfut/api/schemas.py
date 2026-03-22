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


class NoTradeReasonResponse(BaseModel):
    code: str
    message: str


class RiskDecisionResponse(BaseModel):
    target_before_risk: float
    target_after_risk: float
    current_position: float
    target_notional_usdc: float
    current_notional_usdc: float
    delta_notional_usdc: float
    rebalance_threshold: float
    min_trade_notional_usdc: float
    halted: bool
    rebalance_eligible: bool


class ExecutionSummaryResponse(BaseModel):
    action: str
    reason_code: str
    reason_message: str
    summary: str


class SignalDecisionResponse(BaseModel):
    strategy: str | None = None
    raw_value: float | None = None
    target_position: float | None = None


class LatestDecisionResponse(BaseModel):
    cycle_id: str | None = None
    mode: str | None = None
    product_id: str | None = None
    signal: SignalDecisionResponse | None = None
    risk_decision: RiskDecisionResponse | None = None
    execution_summary: ExecutionSummaryResponse | None = None
    no_trade_reason: NoTradeReasonResponse | None = None
    order_intent: dict[str, Any] | None = None
    fill: dict[str, Any] | None = None


class AnalysisSeriesPointResponse(BaseModel):
    label: str
    value: float


class RunAnalysisResponse(BaseModel):
    run_id: str
    mode: str | None = None
    product_id: str | None = None
    strategy_id: str | None = None
    started_at: str | None = None
    ended_at: str | None = None
    cycle_count: int
    starting_equity_usdc: float
    ending_equity_usdc: float
    realized_pnl_usdc: float
    unrealized_pnl_usdc: float
    total_pnl_usdc: float
    total_return_pct: float
    max_drawdown_usdc: float
    max_drawdown_pct: float
    turnover_usdc: float
    fill_count: int
    trade_count: int
    avg_abs_exposure_pct: float
    max_abs_exposure_pct: float
    decision_counts: dict[str, int]
    equity_series: list[AnalysisSeriesPointResponse]
    drawdown_series: list[AnalysisSeriesPointResponse]
    exposure_series: list[AnalysisSeriesPointResponse]


class DashboardOverviewResponse(BaseModel):
    mode: str
    generated_at: datetime
    latest_run: RunSummaryResponse | None = None
    latest_state: dict[str, Any] | None = None
    latest_decision: LatestDecisionResponse | None = None
    latest_analysis: RunAnalysisResponse | None = None
    recent_events: list[dict[str, Any]] = Field(default_factory=list)
    recent_fills: list[dict[str, Any]] = Field(default_factory=list)
    recent_positions: list[dict[str, Any]] = Field(default_factory=list)


class PaperRunRequest(BaseModel):
    product_id: str = Field(alias="productId")
    strategy_id: str = Field(alias="strategyId", default="momentum")
    iterations: int = Field(ge=1)
    interval_seconds: int = Field(alias="intervalSeconds", ge=0)
    starting_collateral_usdc: float = Field(alias="startingCollateralUsdc", gt=0)

    model_config = {
        "populate_by_name": True,
    }


class PaperRunStatusResponse(BaseModel):
    active: bool
    pid: int | None = None
    started_at: str | None = None
    run_id: str | None = None
    product_id: str | None = None
    strategy_id: str | None = None
    iterations: int | None = None
    interval_seconds: int | None = None
    starting_collateral_usdc: float | None = None
    log_path: str | None = None
