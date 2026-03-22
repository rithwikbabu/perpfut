"""Backtest API endpoints."""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, status

from ..backtest_manager import (
    BacktestJobConflictError,
    BacktestJobStartError,
    BacktestJobStateError,
    get_backtest_job_manager,
)
from ..repository import (
    ArtifactError,
    list_dataset_summary_responses,
    list_backtest_run_summaries,
    list_backtest_suite_summaries,
    list_portfolio_run_summaries,
    list_strategy_sleeve_summaries,
    load_artifact_list,
    load_backtest_run_detail,
    load_backtest_suite_detail,
    load_dataset_summary_response,
    load_portfolio_run_analysis,
    load_portfolio_run_comparison,
    load_portfolio_run_detail,
    load_run_analysis,
    load_strategy_sleeve_comparison,
    load_strategy_sleeve_detail,
)
from ..strategy_catalog import build_strategy_catalog
from ...backtest_data import HistoricalDatasetBuilder
from ...exchange_coinbase import CoinbasePublicClient
from ...portfolio_optimizer import PortfolioOptimizationConfig
from ...portfolio_runs import (
    load_or_run_strategy_sleeve_research,
    run_portfolio_research,
    run_portfolio_research_from_sleeves,
)
from ...strategy_instances import parse_strategy_instance_specs
from ..schemas import (
    ArtifactListResponse,
    BacktestJobStatusResponse,
    BacktestRunDetailResponse,
    BacktestRunRequest,
    BacktestsListResponse,
    BacktestSuiteDetailResponse,
    BacktestSuitesListResponse,
    DatasetBuildRequest,
    DatasetSummaryResponse,
    DatasetsListResponse,
    PortfolioRunAnalysisResponse,
    PortfolioRunComparisonResponse,
    PortfolioRunDetailResponse,
    PortfolioRunRequest,
    PortfolioRunsListResponse,
    RunAnalysisResponse,
    SleeveLaunchRequest,
    StrategySleeveComparisonResponse,
    StrategyCatalogResponse,
    StrategySleeveDetailResponse,
    StrategySleeveSummaryResponse,
    StrategySleevesListResponse,
)
from ...config import AppConfig


router = APIRouter(tags=["backtests"])


@router.get("/strategy-catalog", response_model=StrategyCatalogResponse)
def read_strategy_catalog() -> StrategyCatalogResponse:
    return build_strategy_catalog(AppConfig.from_env())


@router.get("/datasets", response_model=DatasetsListResponse)
def read_datasets(limit: int = Query(default=10, ge=1, le=200)) -> DatasetsListResponse:
    try:
        return list_dataset_summary_responses(limit=limit)
    except (OSError, ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=500, detail="invalid dataset artifacts") from exc


@router.post("/datasets", response_model=DatasetSummaryResponse, status_code=status.HTTP_201_CREATED)
def build_dataset(request: DatasetBuildRequest) -> DatasetSummaryResponse:
    config = AppConfig.from_env()
    start = _parse_dataset_datetime(request.start, field_name="start")
    end = _parse_dataset_datetime(request.end, field_name="end")
    try:
        with CoinbasePublicClient() as client:
            builder = HistoricalDatasetBuilder(client=client, base_runs_dir=config.runtime.runs_dir)
            dataset = builder.build_dataset(
                products=request.product_ids,
                start=start,
                end=end,
                granularity=request.granularity,
            )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return load_dataset_summary_response(dataset.dataset_id)


@router.get("/datasets/{dataset_id}", response_model=DatasetSummaryResponse)
def read_dataset(dataset_id: str) -> DatasetSummaryResponse:
    try:
        return load_dataset_summary_response(dataset_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=500, detail="invalid dataset artifacts") from exc


@router.get("/backtests", response_model=BacktestsListResponse)
def read_backtests(limit: int = Query(default=10, ge=1, le=200)) -> BacktestsListResponse:
    manager = get_backtest_job_manager()
    try:
        active_job, latest_job = _load_job_statuses(manager)
    except BacktestJobStateError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    try:
        items = list_backtest_run_summaries(limit=limit)
    except (OSError, ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=500, detail="invalid backtest artifacts") from exc
    return BacktestsListResponse(items=items, count=len(items), active_job=active_job, latest_job=latest_job)


@router.post("/backtests", response_model=BacktestJobStatusResponse, status_code=status.HTTP_202_ACCEPTED)
def start_backtest_job(request: BacktestRunRequest) -> BacktestJobStatusResponse:
    manager = get_backtest_job_manager()
    try:
        return manager.start(request)
    except BacktestJobConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (BacktestJobStartError, BacktestJobStateError) as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/backtests/{run_id}", response_model=BacktestRunDetailResponse)
def read_backtest_run(run_id: str) -> BacktestRunDetailResponse:
    try:
        return load_backtest_run_detail(run_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ArtifactError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/backtests/{run_id}/analysis", response_model=RunAnalysisResponse)
def read_backtest_analysis(run_id: str) -> RunAnalysisResponse:
    try:
        analysis = load_run_analysis(f"backtests/runs/{run_id}")
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="analysis inputs not found") from exc
    except ArtifactError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    assert analysis is not None
    return analysis


@router.get("/backtests/{run_id}/events", response_model=ArtifactListResponse)
def read_backtest_events(run_id: str, limit: int = Query(default=50, ge=1, le=500)) -> ArtifactListResponse:
    return _build_backtest_list_response(run_id, "events.ndjson", limit=limit)


@router.get("/backtests/{run_id}/positions", response_model=ArtifactListResponse)
def read_backtest_positions(run_id: str, limit: int = Query(default=50, ge=1, le=500)) -> ArtifactListResponse:
    return _build_backtest_list_response(run_id, "positions.ndjson", limit=limit)


@router.get("/backtests/{run_id}/fills", response_model=ArtifactListResponse)
def read_backtest_fills(run_id: str, limit: int = Query(default=50, ge=1, le=500)) -> ArtifactListResponse:
    return _build_backtest_list_response(run_id, "fills.ndjson", limit=limit)


@router.get("/backtest-suites", response_model=BacktestSuitesListResponse)
def read_backtest_suites(limit: int = Query(default=10, ge=1, le=200)) -> BacktestSuitesListResponse:
    manager = get_backtest_job_manager()
    try:
        active_job, latest_job = _load_job_statuses(manager)
    except BacktestJobStateError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    try:
        items = list_backtest_suite_summaries(limit=limit)
    except (OSError, ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=500, detail="invalid backtest suite artifacts") from exc
    return BacktestSuitesListResponse(items=items, count=len(items), active_job=active_job, latest_job=latest_job)


@router.get("/backtest-suites/{suite_id}", response_model=BacktestSuiteDetailResponse)
def read_backtest_suite_detail(suite_id: str) -> BacktestSuiteDetailResponse:
    try:
        return load_backtest_suite_detail(suite_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ArtifactError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/portfolio-runs", response_model=PortfolioRunsListResponse)
def read_portfolio_runs(
    limit: int = Query(default=10, ge=1, le=200),
    dataset_id: str | None = Query(default=None, alias="datasetId"),
) -> PortfolioRunsListResponse:
    try:
        return list_portfolio_run_summaries(limit=limit, dataset_id=dataset_id)
    except (OSError, ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=500, detail="invalid portfolio run artifacts") from exc


@router.post("/sleeves", response_model=StrategySleevesListResponse, status_code=status.HTTP_201_CREATED)
def launch_strategy_sleeves(request: SleeveLaunchRequest) -> StrategySleevesListResponse:
    config = AppConfig.from_env()
    try:
        strategy_instances = parse_strategy_instance_specs(
            [
                {
                    "strategy_instance_id": item.strategy_instance_id,
                    "strategy_id": item.strategy_id,
                    "universe": item.universe,
                    "strategy_params": item.strategy_params,
                    "risk_overrides": item.risk_overrides,
                }
                for item in request.strategy_instances
            ],
            source="api sleeve request",
        )
        with CoinbasePublicClient() as client:
            dataset = HistoricalDatasetBuilder(client=client, base_runs_dir=config.runtime.runs_dir).load_dataset(
                request.dataset_id
            )
        sleeves = [
            load_or_run_strategy_sleeve_research(
                base_runs_dir=config.runtime.runs_dir,
                dataset=dataset,
                config=config,
                strategy_instance=strategy_instance,
            )
            for strategy_instance in strategy_instances
        ]
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except OSError as exc:
        raise HTTPException(status_code=500, detail="failed to write strategy sleeve artifacts") from exc
    return StrategySleevesListResponse(
        items=[
            StrategySleeveSummaryResponse(
                run_id=sleeve.run_id,
                created_at=_load_manifest_created_at(sleeve.run_dir),
                dataset_id=sleeve.analysis.dataset_id,
                strategy_instance_id=sleeve.analysis.strategy_instance_id,
                strategy_id=sleeve.analysis.strategy_id,
                date_range_start=sleeve.analysis.date_range_start,
                date_range_end=sleeve.analysis.date_range_end,
                total_pnl_usdc=sleeve.analysis.total_pnl_usdc,
                total_return_pct=sleeve.analysis.total_return_pct,
                max_drawdown_usdc=sleeve.analysis.max_drawdown_usdc,
                max_drawdown_pct=sleeve.analysis.max_drawdown_pct,
                avg_abs_exposure_pct=_average_series_value(sleeve.analysis.daily_avg_abs_exposure_pct),
                turnover_usdc=_sum_series_value(sleeve.analysis.daily_turnover_usdc),
            )
            for sleeve in sleeves
        ],
        count=len(sleeves),
    )


@router.get("/portfolio-run-comparisons", response_model=PortfolioRunComparisonResponse)
def read_portfolio_run_comparison(
    limit: int = Query(default=10, ge=1, le=200),
    dataset_id: str | None = Query(default=None, alias="datasetId"),
) -> PortfolioRunComparisonResponse:
    try:
        return load_portfolio_run_comparison(limit=limit, dataset_id=dataset_id)
    except (OSError, ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=500, detail="invalid portfolio run artifacts") from exc


@router.post("/portfolio-runs", response_model=PortfolioRunDetailResponse, status_code=status.HTTP_201_CREATED)
def start_portfolio_run(request: PortfolioRunRequest) -> PortfolioRunDetailResponse:
    config = AppConfig.from_env()
    try:
        with CoinbasePublicClient() as client:
            dataset = HistoricalDatasetBuilder(client=client, base_runs_dir=config.runtime.runs_dir).load_dataset(
                request.dataset_id
            )
        optimizer_config = PortfolioOptimizationConfig(
            lookback_days=request.lookback_days,
            max_strategy_weight=request.max_strategy_weight,
            covariance_shrinkage=request.covariance_shrinkage,
            ridge_penalty=request.ridge_penalty,
            turnover_cost_bps=request.turnover_cost_bps,
        )
        starting_capital_usdc = (
            request.starting_capital_usdc
            if request.starting_capital_usdc is not None
            else config.simulation.starting_collateral_usdc
        )
        if request.strategy_instances is not None:
            strategy_instances = parse_strategy_instance_specs(
                [
                    {
                        "strategy_instance_id": item.strategy_instance_id,
                        "strategy_id": item.strategy_id,
                        "universe": item.universe,
                        "strategy_params": item.strategy_params,
                        "risk_overrides": item.risk_overrides,
                    }
                    for item in request.strategy_instances
                ],
                source="api portfolio request",
            )
            result = run_portfolio_research(
                base_runs_dir=config.runtime.runs_dir,
                dataset=dataset,
                config=config,
                strategy_instances=strategy_instances,
                optimizer_config=optimizer_config,
                starting_capital_usdc=starting_capital_usdc,
            )
        else:
            assert request.sleeve_run_ids is not None
            result = run_portfolio_research_from_sleeves(
                base_runs_dir=config.runtime.runs_dir,
                dataset=dataset,
                optimizer_config=optimizer_config,
                starting_capital_usdc=starting_capital_usdc,
                sleeve_run_ids=tuple(request.sleeve_run_ids),
            )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except OSError as exc:
        raise HTTPException(status_code=500, detail="failed to write portfolio run artifacts") from exc
    return load_portfolio_run_detail(result.run_id)


@router.get("/portfolio-runs/{run_id}", response_model=PortfolioRunDetailResponse)
def read_portfolio_run(run_id: str) -> PortfolioRunDetailResponse:
    try:
        return load_portfolio_run_detail(run_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ArtifactError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/portfolio-runs/{run_id}/analysis", response_model=PortfolioRunAnalysisResponse)
def read_portfolio_run_analysis(run_id: str) -> PortfolioRunAnalysisResponse:
    try:
        return load_portfolio_run_analysis(run_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ArtifactError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/sleeves", response_model=StrategySleevesListResponse)
def read_strategy_sleeves(
    limit: int = Query(default=10, ge=1, le=200),
    dataset_id: str | None = Query(default=None, alias="datasetId"),
) -> StrategySleevesListResponse:
    try:
        return list_strategy_sleeve_summaries(limit=limit, dataset_id=dataset_id)
    except (OSError, ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=500, detail="invalid strategy sleeve artifacts") from exc


@router.get("/sleeve-comparisons", response_model=StrategySleeveComparisonResponse)
def read_strategy_sleeve_comparison(
    limit: int = Query(default=10, ge=1, le=200),
    dataset_id: str | None = Query(default=None, alias="datasetId"),
) -> StrategySleeveComparisonResponse:
    try:
        return load_strategy_sleeve_comparison(limit=limit, dataset_id=dataset_id)
    except (OSError, ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=500, detail="invalid strategy sleeve artifacts") from exc


@router.get("/sleeves/{run_id}", response_model=StrategySleeveDetailResponse)
def read_strategy_sleeve(run_id: str) -> StrategySleeveDetailResponse:
    try:
        return load_strategy_sleeve_detail(run_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ArtifactError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


def _build_backtest_list_response(run_id: str, filename: str, *, limit: int) -> ArtifactListResponse:
    try:
        items = load_artifact_list(f"backtests/runs/{run_id}", filename, limit=limit)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"artifact not found: {filename}") from exc
    except ArtifactError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return ArtifactListResponse(run_id=run_id, items=items, count=len(items))


def _load_job_statuses(manager) -> tuple[BacktestJobStatusResponse | None, BacktestJobStatusResponse | None]:
    active_job = manager.status()
    latest_job = next(iter(manager.list_jobs(limit=1)), None)
    if active_job is None or latest_job is None or active_job.job_id != latest_job.job_id:
        return active_job, latest_job
    canonical_job = _prefer_fresher_job_status(active_job, latest_job)
    if canonical_job.status == "running":
        return canonical_job, canonical_job
    return None, canonical_job


def _prefer_fresher_job_status(
    left: BacktestJobStatusResponse,
    right: BacktestJobStatusResponse,
) -> BacktestJobStatusResponse:
    return left if _job_status_sort_key(left) >= _job_status_sort_key(right) else right


def _job_status_sort_key(job: BacktestJobStatusResponse) -> tuple[int, datetime, int, float]:
    status_priority = {"running": 1, "succeeded": 2, "failed": 2}.get(job.status, 0)
    heartbeat = _parse_timestamp(job.last_heartbeat_at) or _parse_timestamp(job.started_at) or datetime.min
    completed_runs = job.completed_runs or 0
    progress_pct = job.progress_pct or 0.0
    return status_priority, heartbeat, completed_runs, progress_pct


def _parse_timestamp(value: str | None) -> datetime | None:
    if value is None:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _parse_dataset_datetime(value: str, *, field_name: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"invalid {field_name} datetime: {value}") from exc
    if parsed.tzinfo is None:
        raise HTTPException(status_code=422, detail=f"{field_name} datetime must include a timezone: {value}")
    return parsed


def _average_series_value(points: Sequence[object]) -> float | None:
    if not points:
        return None
    values = [float(getattr(point, "value")) for point in points]
    return sum(values) / len(values)


def _sum_series_value(points: Sequence[object]) -> float | None:
    if not points:
        return None
    return sum(float(getattr(point, "value")) for point in points)


def _load_manifest_created_at(run_dir: Path) -> str | None:
    try:
        path = run_dir / "manifest.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return None
    value = payload.get("created_at")
    return value if isinstance(value, str) else None
