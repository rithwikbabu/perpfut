"""Listing, loading, and comparing persisted portfolio-research runs."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class PortfolioRunSummary:
    run_id: str
    created_at: str | None
    dataset_id: str | None
    date_range_start: str | None
    date_range_end: str | None
    sharpe_ratio: float | None
    total_pnl_usdc: float
    total_return_pct: float
    max_drawdown_usdc: float
    max_drawdown_pct: float
    total_turnover_usdc: float
    avg_gross_weight: float
    max_gross_weight: float
    strategy_instance_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PortfolioRunComparisonEntry:
    rank: int
    run_id: str
    created_at: str | None
    dataset_id: str | None
    date_range_start: str | None
    date_range_end: str | None
    sharpe_ratio: float | None
    total_pnl_usdc: float
    total_return_pct: float
    max_drawdown_usdc: float
    max_drawdown_pct: float
    total_turnover_usdc: float
    avg_gross_weight: float
    max_gross_weight: float
    strategy_instance_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PortfolioRunComparison:
    dataset_id: str | None
    ranking_policy: str
    items: tuple[PortfolioRunComparisonEntry, ...]


def list_portfolio_runs(
    base_runs_dir: Path,
    *,
    limit: int = 10,
    dataset_id: str | None = None,
) -> list[PortfolioRunSummary]:
    runs_dir = base_runs_dir / "backtests" / "portfolio-runs"
    if not runs_dir.exists():
        return []
    items: list[PortfolioRunSummary] = []
    for run_dir in sorted((path for path in runs_dir.iterdir() if path.is_dir()), reverse=True):
        try:
            manifest = _load_json(run_dir / "manifest.json")
            analysis = _load_json(run_dir / "analysis.json")
        except (FileNotFoundError, OSError, json.JSONDecodeError, ValueError):
            continue
        if dataset_id is not None and manifest.get("dataset_id") != dataset_id:
            continue
        items.append(
            PortfolioRunSummary(
                run_id=run_dir.name,
                created_at=_as_str(manifest.get("created_at")),
                dataset_id=_as_str(manifest.get("dataset_id")),
                date_range_start=_as_str(analysis.get("date_range_start")),
                date_range_end=_as_str(analysis.get("date_range_end")),
                sharpe_ratio=_as_float(analysis.get("sharpe_ratio")),
                total_pnl_usdc=float(analysis.get("total_pnl_usdc") or 0.0),
                total_return_pct=float(analysis.get("total_return_pct") or 0.0),
                max_drawdown_usdc=float(analysis.get("max_drawdown_usdc") or 0.0),
                max_drawdown_pct=float(analysis.get("max_drawdown_pct") or 0.0),
                total_turnover_usdc=float(analysis.get("total_turnover_usdc") or 0.0),
                avg_gross_weight=float(analysis.get("avg_gross_weight") or 0.0),
                max_gross_weight=float(analysis.get("max_gross_weight") or 0.0),
                strategy_instance_ids=tuple(_as_str_list(analysis.get("strategy_instance_ids"))),
            )
        )
        if len(items) >= limit:
            break
    return items


def load_portfolio_run(base_runs_dir: Path, *, run_id: str) -> dict[str, Any]:
    run_dir = base_runs_dir / "backtests" / "portfolio-runs" / run_id
    if not run_dir.exists():
        raise FileNotFoundError(f"portfolio run not found: {run_id}")
    return {
        "manifest": _load_json(run_dir / "manifest.json"),
        "config": _load_json(run_dir / "config.json"),
        "state": _load_json(run_dir / "state.json"),
        "analysis": _load_json(run_dir / "analysis.json"),
        "weights": _load_ndjson(run_dir / "weights.ndjson"),
        "diagnostics": _load_ndjson(run_dir / "diagnostics.ndjson"),
        "contributions": _load_json(run_dir / "contributions.json"),
    }


def compare_portfolio_runs(
    base_runs_dir: Path,
    *,
    limit: int = 10,
    dataset_id: str | None = None,
) -> PortfolioRunComparison:
    items = list_portfolio_runs(base_runs_dir, limit=limit * 5, dataset_id=dataset_id)
    ranked = tuple(
        PortfolioRunComparisonEntry(
            rank=index,
            run_id=item.run_id,
            created_at=item.created_at,
            dataset_id=item.dataset_id,
            date_range_start=item.date_range_start,
            date_range_end=item.date_range_end,
            sharpe_ratio=item.sharpe_ratio,
            total_pnl_usdc=item.total_pnl_usdc,
            total_return_pct=item.total_return_pct,
            max_drawdown_usdc=item.max_drawdown_usdc,
            max_drawdown_pct=item.max_drawdown_pct,
            total_turnover_usdc=item.total_turnover_usdc,
            avg_gross_weight=item.avg_gross_weight,
            max_gross_weight=item.max_gross_weight,
            strategy_instance_ids=item.strategy_instance_ids,
        )
        for index, item in enumerate(
            sorted(
                items,
                key=lambda item: (
                    item.sharpe_ratio is None,
                    0.0 if item.sharpe_ratio is None else -item.sharpe_ratio,
                    -item.total_return_pct,
                    item.max_drawdown_pct,
                    item.total_turnover_usdc,
                    item.run_id,
                ),
            )[:limit],
            start=1,
        )
    )
    return PortfolioRunComparison(
        dataset_id=dataset_id,
        ranking_policy=(
            "rank by sharpe_ratio desc, total_return_pct desc, "
            "max_drawdown_pct asc, total_turnover_usdc asc, run_id asc"
        ),
        items=ranked,
    )


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"invalid json object in {path}")
    return payload


def _load_ndjson(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        if not isinstance(payload, dict):
            raise ValueError(f"invalid ndjson row in {path}")
        rows.append(payload)
    return rows


def _as_str(value: Any) -> str | None:
    return value if isinstance(value, str) else None


def _as_float(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _as_str_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]
