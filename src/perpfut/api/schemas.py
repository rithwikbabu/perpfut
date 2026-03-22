"""Pydantic models for the operator API contract."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, model_validator


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
    date_range_start: str | None = None
    date_range_end: str | None = None
    sharpe_ratio: float | None = None
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


class BacktestRunRequest(BaseModel):
    dataset_id: str | None = Field(alias="datasetId", default=None)
    product_ids: list[str] | None = Field(alias="productIds", default=None)
    strategy_ids: list[str] = Field(alias="strategyIds", min_length=1)
    start: str | None = None
    end: str | None = None
    granularity: str = "ONE_MINUTE"
    lookback_candles: int | None = Field(alias="lookbackCandles", default=None, ge=1)
    signal_scale: float | None = Field(alias="signalScale", default=None)
    starting_collateral_usdc: float | None = Field(alias="startingCollateralUsdc", default=None, gt=0)
    max_abs_position: float | None = Field(alias="maxAbsPosition", default=None, gt=0)
    max_gross_position: float | None = Field(alias="maxGrossPosition", default=None, gt=0)
    max_leverage: float | None = Field(alias="maxLeverage", default=None, gt=0)
    slippage_bps: float | None = Field(alias="slippageBps", default=None, ge=0)

    model_config = {
        "populate_by_name": True,
    }

    @model_validator(mode="after")
    def _validate_dataset_or_range(self) -> "BacktestRunRequest":
        if self.dataset_id:
            return self
        if not self.product_ids or self.start is None or self.end is None:
            raise ValueError(
                "backtest runs require either datasetId or productIds with start/end"
            )
        return self


class DatasetBuildRequest(BaseModel):
    product_ids: list[str] = Field(alias="productIds", min_length=1)
    start: str
    end: str
    granularity: str = "ONE_MINUTE"

    model_config = {
        "populate_by_name": True,
    }


class DatasetSummaryResponse(BaseModel):
    dataset_id: str = Field(alias="datasetId")
    created_at: str = Field(alias="createdAt")
    fingerprint: str
    source: str
    version: str
    products: list[str]
    start: str
    end: str
    granularity: str
    candle_counts: dict[str, int] = Field(alias="candleCounts")

    model_config = {
        "populate_by_name": True,
    }


class DatasetsListResponse(BaseModel):
    items: list[DatasetSummaryResponse]
    count: int


class BacktestJobStatusResponse(BaseModel):
    job_id: str
    status: str
    phase: str | None = None
    phase_message: str | None = None
    pid: int | None = None
    created_at: str
    started_at: str | None = None
    finished_at: str | None = None
    total_runs: int | None = None
    completed_runs: int | None = None
    progress_pct: float | None = None
    elapsed_seconds: float | None = None
    eta_seconds: float | None = None
    last_heartbeat_at: str | None = None
    suite_id: str | None = None
    dataset_id: str | None = None
    run_ids: list[str] = Field(default_factory=list)
    error: str | None = None
    log_path: str | None = None
    request: BacktestRunRequest


class BacktestRunSummaryResponse(BaseModel):
    run_id: str
    created_at: str | None = None
    suite_id: str | None = None
    dataset_id: str | None = None
    date_range_start: str | None = None
    date_range_end: str | None = None
    product_id: str | None = None
    strategy_id: str | None = None
    sharpe_ratio: float | None = None
    total_pnl_usdc: float
    total_return_pct: float
    max_drawdown_usdc: float
    max_drawdown_pct: float
    turnover_usdc: float
    fill_count: int
    avg_abs_exposure_pct: float
    max_abs_exposure_pct: float


class BacktestsListResponse(BaseModel):
    items: list[BacktestRunSummaryResponse]
    count: int
    active_job: BacktestJobStatusResponse | None = None
    latest_job: BacktestJobStatusResponse | None = None


class BacktestRunDetailResponse(BaseModel):
    run_id: str
    manifest: dict[str, Any]
    state: dict[str, Any]
    analysis: RunAnalysisResponse


class BacktestSuiteSummaryResponse(BaseModel):
    suite_id: str
    created_at: str | None = None
    dataset_id: str | None = None
    date_range_start: str | None = None
    date_range_end: str | None = None
    sharpe_ratio: float | None = None
    products: list[str] = Field(default_factory=list)
    strategies: list[str] = Field(default_factory=list)
    run_ids: list[str] = Field(default_factory=list)


class BacktestSuitesListResponse(BaseModel):
    items: list[BacktestSuiteSummaryResponse]
    count: int
    active_job: BacktestJobStatusResponse | None = None
    latest_job: BacktestJobStatusResponse | None = None


class BacktestSuiteComparisonItemResponse(BaseModel):
    rank: int
    run_id: str
    strategy_id: str | None = None
    date_range_start: str | None = None
    date_range_end: str | None = None
    sharpe_ratio: float | None = None
    total_pnl_usdc: float
    total_return_pct: float
    max_drawdown_usdc: float
    max_drawdown_pct: float
    turnover_usdc: float
    fill_count: int
    avg_abs_exposure_pct: float
    max_abs_exposure_pct: float
    decision_counts: dict[str, int]


class BacktestSuiteDetailResponse(BaseModel):
    suite_id: str
    created_at: str | None = None
    dataset_id: str | None = None
    date_range_start: str | None = None
    date_range_end: str | None = None
    sharpe_ratio: float | None = None
    products: list[str] = Field(default_factory=list)
    strategies: list[str] = Field(default_factory=list)
    run_ids: list[str] = Field(default_factory=list)
    ranking_policy: str
    items: list[BacktestSuiteComparisonItemResponse]
