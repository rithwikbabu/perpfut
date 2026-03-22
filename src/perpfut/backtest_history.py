"""Helpers for listing and comparing persisted backtest artifacts."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .analysis import analyze_run
from .run_history import load_run_manifest, load_run_state


@dataclass(frozen=True, slots=True)
class BacktestSuiteSummary:
    suite_id: str
    created_at: str | None
    dataset_id: str | None
    products: tuple[str, ...]
    strategies: tuple[str, ...]
    run_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class BacktestSuiteComparisonEntry:
    rank: int
    run_id: str
    strategy_id: str | None
    total_pnl_usdc: float
    total_return_pct: float
    max_drawdown_usdc: float
    max_drawdown_pct: float
    turnover_usdc: float
    fill_count: int
    avg_abs_exposure_pct: float
    max_abs_exposure_pct: float
    decision_counts: dict[str, int]


@dataclass(frozen=True, slots=True)
class BacktestSuiteComparison:
    suite_id: str
    dataset_id: str | None
    ranking_policy: str
    items: tuple[BacktestSuiteComparisonEntry, ...]


@dataclass(frozen=True, slots=True)
class BacktestRunSummary:
    run_id: str
    created_at: str | None
    suite_id: str | None
    dataset_id: str | None
    product_id: str | None
    strategy_id: str | None
    total_pnl_usdc: float
    total_return_pct: float
    max_drawdown_usdc: float
    max_drawdown_pct: float
    turnover_usdc: float
    fill_count: int
    avg_abs_exposure_pct: float
    max_abs_exposure_pct: float


def list_backtest_suites(base_runs_dir: Path, *, limit: int = 10) -> list[BacktestSuiteSummary]:
    suites_dir = base_runs_dir / "backtests" / "suites"
    if not suites_dir.exists():
        return []
    summaries: list[BacktestSuiteSummary] = []
    for suite_dir in sorted((path for path in suites_dir.iterdir() if path.is_dir()), reverse=True):
        manifest_path = suite_dir / "manifest.json"
        if not manifest_path.exists():
            continue
        try:
            manifest = _load_json(manifest_path)
        except (OSError, json.JSONDecodeError, ValueError):
            continue
        summaries.append(
            BacktestSuiteSummary(
                suite_id=suite_dir.name,
                created_at=_as_str(manifest.get("created_at")),
                dataset_id=_as_str(manifest.get("dataset_id")),
                products=tuple(_as_str_list(manifest.get("products"))),
                strategies=tuple(_as_str_list(manifest.get("strategies"))),
                run_ids=tuple(_as_str_list(manifest.get("run_ids"))),
            )
        )
        if len(summaries) >= limit:
            break
    return summaries


def list_backtest_runs(base_runs_dir: Path, *, limit: int = 10) -> list[BacktestRunSummary]:
    runs_dir = base_runs_dir / "backtests" / "runs"
    if not runs_dir.exists():
        return []
    summaries: list[BacktestRunSummary] = []
    for run_dir in sorted((path for path in runs_dir.iterdir() if path.is_dir()), reverse=True):
        manifest_path = run_dir / "manifest.json"
        if not manifest_path.exists():
            continue
        try:
            manifest = load_run_manifest(run_dir)
            analysis = analyze_run(run_dir)
        except (FileNotFoundError, OSError, json.JSONDecodeError, ValueError):
            continue
        summaries.append(
            BacktestRunSummary(
                run_id=run_dir.name,
                created_at=_as_str(manifest.get("created_at")),
                suite_id=_as_str(manifest.get("suite_id")),
                dataset_id=_as_str(manifest.get("dataset_id")),
                product_id=_as_str(manifest.get("product_id")),
                strategy_id=analysis.strategy_id,
                total_pnl_usdc=analysis.total_pnl_usdc,
                total_return_pct=analysis.total_return_pct,
                max_drawdown_usdc=analysis.max_drawdown_usdc,
                max_drawdown_pct=analysis.max_drawdown_pct,
                turnover_usdc=analysis.turnover_usdc,
                fill_count=analysis.fill_count,
                avg_abs_exposure_pct=analysis.avg_abs_exposure_pct,
                max_abs_exposure_pct=analysis.max_abs_exposure_pct,
            )
        )
        if len(summaries) >= limit:
            break
    return summaries


def load_backtest_run(base_runs_dir: Path, *, run_id: str) -> dict[str, Any]:
    run_dir = base_runs_dir / "backtests" / "runs" / run_id
    if not run_dir.exists():
        raise FileNotFoundError(f"backtest run not found: {run_id}")
    analysis_path = run_dir / "analysis.json"
    return {
        "manifest": load_run_manifest(run_dir),
        "state": load_run_state(run_dir),
        "analysis": _load_json(analysis_path) if analysis_path.exists() else asdict(analyze_run(run_dir)),
    }


def compare_backtest_suite(base_runs_dir: Path, *, suite_id: str) -> BacktestSuiteComparison:
    suite_dir = base_runs_dir / "backtests" / "suites" / suite_id
    if not suite_dir.exists():
        raise FileNotFoundError(f"backtest suite not found: {suite_id}")
    manifest = _load_json(suite_dir / "manifest.json")
    items: list[BacktestSuiteComparisonEntry] = []
    for run_id in _as_str_list(manifest.get("run_ids")):
        run_dir = base_runs_dir / "backtests" / "runs" / run_id
        analysis = asdict(analyze_run(run_dir))
        items.append(
            BacktestSuiteComparisonEntry(
                rank=0,
                run_id=run_id,
                strategy_id=_as_str(analysis.get("strategy_id")),
                total_pnl_usdc=float(analysis.get("total_pnl_usdc") or 0.0),
                total_return_pct=float(analysis.get("total_return_pct") or 0.0),
                max_drawdown_usdc=float(analysis.get("max_drawdown_usdc") or 0.0),
                max_drawdown_pct=float(analysis.get("max_drawdown_pct") or 0.0),
                turnover_usdc=float(analysis.get("turnover_usdc") or 0.0),
                fill_count=int(analysis.get("fill_count") or 0),
                avg_abs_exposure_pct=float(analysis.get("avg_abs_exposure_pct") or 0.0),
                max_abs_exposure_pct=float(analysis.get("max_abs_exposure_pct") or 0.0),
                decision_counts=_coerce_int_dict(analysis.get("decision_counts")),
            )
        )
    ranked = tuple(
        BacktestSuiteComparisonEntry(
            rank=index,
            **{
                key: value
                for key, value in asdict(item).items()
                if key != "rank"
            },
        )
        for index, item in enumerate(
            sorted(
                items,
                key=lambda item: (
                    -item.total_return_pct,
                    item.max_drawdown_pct,
                    item.turnover_usdc,
                    item.fill_count,
                    item.run_id,
                ),
            ),
            start=1,
        )
    )
    return BacktestSuiteComparison(
        suite_id=suite_id,
        dataset_id=_as_str(manifest.get("dataset_id")),
        ranking_policy=(
            "rank by total_return_pct desc, max_drawdown_pct asc, "
            "turnover_usdc asc, fill_count asc, run_id asc"
        ),
        items=ranked,
    )


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"invalid json object in {path}")
    return payload


def _as_str(value: Any) -> str | None:
    return value if isinstance(value, str) else None


def _as_str_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _coerce_int_dict(value: Any) -> dict[str, int]:
    if not isinstance(value, dict):
        return {}
    items: dict[str, int] = {}
    for key, item in value.items():
        if isinstance(key, str) and isinstance(item, int):
            items[key] = item
    return items
