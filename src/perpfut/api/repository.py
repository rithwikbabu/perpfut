"""Read-only artifact access for the operator API."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..analysis import RunAnalysis, analyze_run
from .schemas import (
    AnalysisSeriesPointResponse,
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
    signal = _coerce_dict(latest_state.get("signal"))
    risk_decision = _coerce_dict(latest_state.get("risk_decision"))
    execution_summary = _coerce_dict(latest_state.get("execution_summary"))
    no_trade_reason = _coerce_dict(latest_state.get("no_trade_reason"))
    if not any((signal, risk_decision, execution_summary, no_trade_reason)):
        return None
    return LatestDecisionResponse(
        cycle_id=_coerce_str(latest_state.get("cycle_id")),
        mode=_coerce_str(latest_state.get("mode")),
        product_id=_coerce_str(latest_state.get("product_id")),
        signal=SignalDecisionResponse.model_validate(signal) if signal else None,
        risk_decision=RiskDecisionResponse.model_validate(risk_decision) if risk_decision else None,
        execution_summary=(
            ExecutionSummaryResponse.model_validate(execution_summary)
            if execution_summary
            else None
        ),
        no_trade_reason=NoTradeReasonResponse.model_validate(no_trade_reason) if no_trade_reason else None,
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
