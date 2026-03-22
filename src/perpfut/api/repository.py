"""Read-only artifact access for the operator API."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..analysis import RunAnalysis, analyze_run
from ..backtest_history import (
    compare_backtest_suite,
    list_backtest_runs,
    list_backtest_suites,
    load_backtest_run,
)
from pydantic import ValidationError
from .schemas import (
    AnalysisSeriesPointResponse,
    BacktestRunDetailResponse,
    BacktestRunSummaryResponse,
    BacktestSuiteComparisonItemResponse,
    BacktestSuiteDetailResponse,
    BacktestSuiteSummaryResponse,
    DashboardOverviewResponse,
    ExecutionSummaryResponse,
    LatestDecisionResponse,
    NoTradeReasonResponse,
    RiskDecisionResponse,
    RunAnalysisResponse,
    RunSummaryResponse,
    RunsListResponse,
    SignalDecisionResponse,
)
from ..config import AppConfig
from ..run_history import list_runs, load_run_manifest, load_run_state


class ArtifactError(RuntimeError):
    """Raised when an artifact exists but cannot be read safely."""


def get_runs_dir() -> Path:
    return AppConfig.from_env().runtime.runs_dir


def list_run_summaries(*, mode: str | None = None, limit: int = 10) -> RunsListResponse:
    items = _collect_run_summaries(get_runs_dir(), mode=mode, limit=limit)
    return RunsListResponse(items=items, count=len(items))


def build_dashboard_overview(*, mode: str, limit: int = 10) -> DashboardOverviewResponse:
    items = _collect_run_summaries(get_runs_dir(), mode=mode, limit=1)
    latest_run = items[0] if items else None
    latest_state = None
    latest_analysis = None
    recent_events: list[dict[str, Any]] = []
    recent_fills: list[dict[str, Any]] = []
    recent_positions: list[dict[str, Any]] = []

    if latest_run is not None:
        run_dir = get_runs_dir() / latest_run.run_id
        latest_state = load_artifact_document(run_dir.name, "state.json", required=False)
        latest_analysis = load_run_analysis(run_dir.name, required=False)
        recent_events = load_artifact_list(run_dir.name, "events.ndjson", limit=limit, required=False)
        recent_fills = load_artifact_list(run_dir.name, "fills.ndjson", limit=limit, required=False)
        recent_positions = load_artifact_list(run_dir.name, "positions.ndjson", limit=limit, required=False)

    return DashboardOverviewResponse(
        mode=mode,
        generated_at=datetime.now(timezone.utc),
        latest_run=latest_run,
        latest_state=latest_state,
        latest_decision=_build_latest_decision(latest_state),
        latest_analysis=latest_analysis,
        recent_events=recent_events,
        recent_fills=recent_fills,
        recent_positions=recent_positions,
    )


def list_backtest_run_summaries(*, limit: int = 10) -> list[BacktestRunSummaryResponse]:
    return [
        BacktestRunSummaryResponse(
            run_id=item.run_id,
            created_at=item.created_at,
            suite_id=item.suite_id,
            dataset_id=item.dataset_id,
            date_range_start=item.date_range_start,
            date_range_end=item.date_range_end,
            product_id=item.product_id,
            strategy_id=item.strategy_id,
            sharpe_ratio=item.sharpe_ratio,
            total_pnl_usdc=item.total_pnl_usdc,
            total_return_pct=item.total_return_pct,
            max_drawdown_usdc=item.max_drawdown_usdc,
            max_drawdown_pct=item.max_drawdown_pct,
            turnover_usdc=item.turnover_usdc,
            fill_count=item.fill_count,
            avg_abs_exposure_pct=item.avg_abs_exposure_pct,
            max_abs_exposure_pct=item.max_abs_exposure_pct,
        )
        for item in list_backtest_runs(get_runs_dir(), limit=limit)
    ]


def load_backtest_run_detail(run_id: str) -> BacktestRunDetailResponse:
    payload = load_backtest_run(get_runs_dir(), run_id=run_id)
    analysis_payload = payload.get("analysis")
    if not isinstance(analysis_payload, dict):
        raise ArtifactError(f"invalid backtest analysis payload for: {run_id}")
    try:
        analysis = RunAnalysisResponse.model_validate(analysis_payload)
    except ValidationError as exc:
        raise ArtifactError(f"invalid backtest analysis payload for: {run_id}") from exc
    manifest = payload.get("manifest")
    state = payload.get("state")
    if not isinstance(manifest, dict) or not isinstance(state, dict):
        raise ArtifactError(f"invalid backtest artifacts for: {run_id}")
    return BacktestRunDetailResponse(
        run_id=run_id,
        manifest=manifest,
        state=state,
        analysis=analysis,
    )


def list_backtest_suite_summaries(*, limit: int = 10) -> list[BacktestSuiteSummaryResponse]:
    return [
        BacktestSuiteSummaryResponse(
            suite_id=item.suite_id,
            created_at=item.created_at,
            dataset_id=item.dataset_id,
            date_range_start=item.date_range_start,
            date_range_end=item.date_range_end,
            sharpe_ratio=item.sharpe_ratio,
            products=list(item.products),
            strategies=list(item.strategies),
            run_ids=list(item.run_ids),
        )
        for item in list_backtest_suites(get_runs_dir(), limit=limit)
    ]


def load_backtest_suite_detail(suite_id: str) -> BacktestSuiteDetailResponse:
    base_dir = get_runs_dir()
    summary = _load_backtest_suite_summary(base_dir, suite_id)
    comparison = compare_backtest_suite(base_dir, suite_id=suite_id)
    return BacktestSuiteDetailResponse(
        suite_id=summary.suite_id,
        created_at=summary.created_at,
        dataset_id=summary.dataset_id,
        products=list(summary.products),
        strategies=list(summary.strategies),
        run_ids=list(summary.run_ids),
        ranking_policy=comparison.ranking_policy,
        items=[
            BacktestSuiteComparisonItemResponse(
                rank=item.rank,
                run_id=item.run_id,
                strategy_id=item.strategy_id,
                date_range_start=item.date_range_start,
                date_range_end=item.date_range_end,
                sharpe_ratio=item.sharpe_ratio,
                total_pnl_usdc=item.total_pnl_usdc,
                total_return_pct=item.total_return_pct,
                max_drawdown_usdc=item.max_drawdown_usdc,
                max_drawdown_pct=item.max_drawdown_pct,
                turnover_usdc=item.turnover_usdc,
                fill_count=item.fill_count,
                avg_abs_exposure_pct=item.avg_abs_exposure_pct,
                max_abs_exposure_pct=item.max_abs_exposure_pct,
                decision_counts=item.decision_counts,
            )
            for item in comparison.items
        ],
    )


def _load_backtest_suite_summary(base_dir: Path, suite_id: str) -> BacktestSuiteSummaryResponse:
    manifest_path = base_dir / "backtests" / "suites" / suite_id / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"backtest suite not found: {suite_id}")
    try:
        manifest = _require_document_dict(json.loads(manifest_path.read_text(encoding="utf-8")), manifest_path)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        raise ArtifactError(f"invalid backtest suite artifacts for: {suite_id}") from exc
    return BacktestSuiteSummaryResponse(
        suite_id=suite_id,
        created_at=_coerce_str(manifest.get("created_at")),
        dataset_id=_coerce_str(manifest.get("dataset_id")),
        products=[
            item
            for item in manifest.get("products", [])
            if isinstance(item, str)
        ],
        strategies=[
            item
            for item in manifest.get("strategies", [])
            if isinstance(item, str)
        ],
        run_ids=[
            item
            for item in manifest.get("run_ids", [])
            if isinstance(item, str)
        ],
    )


def load_run_analysis(run_id: str, *, required: bool = True) -> RunAnalysisResponse | None:
    run_dir = _resolve_run_dir(run_id)
    try:
        return _build_run_analysis_response(analyze_run(run_dir))
    except FileNotFoundError as exc:
        if required:
            raise exc
        return None
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        if required:
            raise ArtifactError(f"invalid analysis inputs: {run_dir}") from exc
        return None


def load_artifact_document(run_id: str, filename: str, *, required: bool = True) -> dict[str, Any] | None:
    run_dir = _resolve_run_dir(run_id)
    path = run_dir / filename
    if not path.exists():
        if required:
            raise FileNotFoundError(path)
        return None
    try:
        if filename == "state.json":
            return _require_document_dict(load_run_state(run_dir), path)
        if filename == "manifest.json":
            return _require_document_dict(load_run_manifest(run_dir), path)
        return _require_document_dict(json.loads(path.read_text(encoding="utf-8")), path)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        if required:
            raise ArtifactError(f"invalid artifact: {path}") from exc
        return None


def load_artifact_list(
    run_id: str,
    filename: str,
    *,
    limit: int = 50,
    required: bool = True,
) -> list[dict[str, Any]]:
    run_dir = _resolve_run_dir(run_id)
    path = run_dir / filename
    if not path.exists():
        if required:
            raise FileNotFoundError(path)
        return []
    try:
        lines: list[dict[str, Any]] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            payload = json.loads(line)
            if not isinstance(payload, dict):
                raise ValueError(f"invalid ndjson row in {path}")
            lines.append(payload)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        if required:
            raise ArtifactError(f"invalid artifact: {path}") from exc
        return []
    return list(reversed(lines))[:limit]


def _collect_run_summaries(base_dir: Path, *, mode: str | None, limit: int) -> list[RunSummaryResponse]:
    summaries: list[RunSummaryResponse] = []
    for run_dir in list_runs(base_dir):
        manifest_path = run_dir / "manifest.json"
        if not manifest_path.exists():
            continue
        try:
            manifest = _require_document_dict(load_run_manifest(run_dir), manifest_path)
        except (OSError, json.JSONDecodeError, ValueError):
            continue
        if mode is not None and manifest.get("mode") != mode:
            continue
        summaries.append(RunSummaryResponse(**_run_summary_dict(run_dir.name, manifest)))
        if len(summaries) >= limit:
            break
    return summaries


def _resolve_run_dir(run_id: str) -> Path:
    run_dir = get_runs_dir() / run_id
    if not run_dir.exists() or not run_dir.is_dir():
        raise FileNotFoundError(run_dir)
    return run_dir


def _run_summary_dict(run_id: str, manifest: dict[str, Any]) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "created_at": manifest.get("created_at"),
        "mode": manifest.get("mode"),
        "product_id": manifest.get("product_id"),
        "resumed_from_run_id": manifest.get("resumed_from_run_id"),
    }


def _build_latest_decision(latest_state: dict[str, Any] | None) -> LatestDecisionResponse | None:
    if not latest_state:
        return None
    signal = _validate_optional_model(SignalDecisionResponse, latest_state.get("signal"))
    risk_decision = _validate_optional_model(RiskDecisionResponse, latest_state.get("risk_decision"))
    execution_summary = _validate_optional_model(
        ExecutionSummaryResponse,
        latest_state.get("execution_summary"),
    )
    no_trade_reason = _validate_optional_model(NoTradeReasonResponse, latest_state.get("no_trade_reason"))
    if not any((signal, risk_decision, execution_summary, no_trade_reason)):
        return None
    return LatestDecisionResponse(
        cycle_id=_coerce_str(latest_state.get("cycle_id")),
        mode=_coerce_str(latest_state.get("mode")),
        product_id=_coerce_str(latest_state.get("product_id")),
        signal=signal,
        risk_decision=risk_decision,
        execution_summary=execution_summary,
        no_trade_reason=no_trade_reason,
        order_intent=_coerce_dict(latest_state.get("order_intent")),
        fill=_coerce_dict(latest_state.get("fill")),
    )


def _build_run_analysis_response(analysis: RunAnalysis) -> RunAnalysisResponse:
    return RunAnalysisResponse(
        run_id=analysis.run_id,
        mode=analysis.mode,
        product_id=analysis.product_id,
        strategy_id=analysis.strategy_id,
        started_at=analysis.started_at,
        ended_at=analysis.ended_at,
        date_range_start=analysis.date_range_start,
        date_range_end=analysis.date_range_end,
        sharpe_ratio=analysis.sharpe_ratio,
        cycle_count=analysis.cycle_count,
        starting_equity_usdc=analysis.starting_equity_usdc,
        ending_equity_usdc=analysis.ending_equity_usdc,
        realized_pnl_usdc=analysis.realized_pnl_usdc,
        unrealized_pnl_usdc=analysis.unrealized_pnl_usdc,
        total_pnl_usdc=analysis.total_pnl_usdc,
        total_return_pct=analysis.total_return_pct,
        max_drawdown_usdc=analysis.max_drawdown_usdc,
        max_drawdown_pct=analysis.max_drawdown_pct,
        turnover_usdc=analysis.turnover_usdc,
        fill_count=analysis.fill_count,
        trade_count=analysis.trade_count,
        avg_abs_exposure_pct=analysis.avg_abs_exposure_pct,
        max_abs_exposure_pct=analysis.max_abs_exposure_pct,
        decision_counts=analysis.decision_counts,
        equity_series=_build_series_points(analysis.equity_series),
        drawdown_series=_build_series_points(analysis.drawdown_series),
        exposure_series=_build_series_points(analysis.exposure_series),
    )


def _build_series_points(points: tuple[Any, ...]) -> list[AnalysisSeriesPointResponse]:
    return [AnalysisSeriesPointResponse(label=point.label, value=point.value) for point in points]


def _coerce_dict(value: Any) -> dict[str, Any] | None:
    return value if isinstance(value, dict) else None


def _coerce_str(value: Any) -> str | None:
    return value if isinstance(value, str) else None


def _require_document_dict(value: Any, path: Path) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"invalid json object in {path}")
    return value


def _validate_optional_model(model: Any, payload: Any) -> Any | None:
    if not isinstance(payload, dict):
        return None
    try:
        return model.model_validate(payload)
    except ValidationError:
        return None
