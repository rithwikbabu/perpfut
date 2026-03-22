"""Listing and comparing persisted strategy-sleeve artifacts."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class StrategySleeveSummary:
    run_id: str
    created_at: str | None
    dataset_id: str | None
    strategy_instance_id: str | None
    strategy_id: str | None
    date_range_start: str | None
    date_range_end: str | None
    total_pnl_usdc: float
    total_return_pct: float
    max_drawdown_usdc: float
    max_drawdown_pct: float
    avg_abs_exposure_pct: float | None
    turnover_usdc: float | None


@dataclass(frozen=True, slots=True)
class StrategySleeveComparisonEntry:
    rank: int
    run_id: str
    dataset_id: str | None
    strategy_instance_id: str | None
    strategy_id: str | None
    date_range_start: str | None
    date_range_end: str | None
    total_pnl_usdc: float
    total_return_pct: float
    max_drawdown_usdc: float
    max_drawdown_pct: float
    avg_abs_exposure_pct: float | None
    turnover_usdc: float | None
    asset_contribution_totals: dict[str, float]


@dataclass(frozen=True, slots=True)
class StrategySleeveComparison:
    dataset_id: str | None
    ranking_policy: str
    items: tuple[StrategySleeveComparisonEntry, ...]


def list_strategy_sleeves(
    base_runs_dir: Path,
    *,
    limit: int = 10,
    dataset_id: str | None = None,
) -> list[StrategySleeveSummary]:
    sleeves_dir = base_runs_dir / "backtests" / "sleeves"
    if not sleeves_dir.exists():
        return []
    items: list[StrategySleeveSummary] = []
    for run_dir in sorted((path for path in sleeves_dir.iterdir() if path.is_dir()), reverse=True):
        try:
            manifest = _load_json(run_dir / "manifest.json")
            sleeve_analysis = _load_json(run_dir / "sleeve_analysis.json")
        except (FileNotFoundError, OSError, json.JSONDecodeError, ValueError):
            continue
        if dataset_id is not None and sleeve_analysis.get("dataset_id") != dataset_id:
            continue
        items.append(
            StrategySleeveSummary(
                run_id=run_dir.name,
                created_at=_as_str(manifest.get("created_at")),
                dataset_id=_as_str(sleeve_analysis.get("dataset_id")),
                strategy_instance_id=_as_str(sleeve_analysis.get("strategy_instance_id")),
                strategy_id=_as_str(sleeve_analysis.get("strategy_id")),
                date_range_start=_as_str(sleeve_analysis.get("date_range_start")),
                date_range_end=_as_str(sleeve_analysis.get("date_range_end")),
                total_pnl_usdc=float(sleeve_analysis.get("total_pnl_usdc") or 0.0),
                total_return_pct=float(sleeve_analysis.get("total_return_pct") or 0.0),
                max_drawdown_usdc=float(sleeve_analysis.get("max_drawdown_usdc") or 0.0),
                max_drawdown_pct=float(sleeve_analysis.get("max_drawdown_pct") or 0.0),
                avg_abs_exposure_pct=_average_series_value(sleeve_analysis.get("daily_avg_abs_exposure_pct")),
                turnover_usdc=_sum_series_values(sleeve_analysis.get("daily_turnover_usdc")),
            )
        )
        if len(items) >= limit:
            break
    return items


def load_strategy_sleeve(base_runs_dir: Path, *, run_id: str) -> dict[str, Any]:
    run_dir = base_runs_dir / "backtests" / "sleeves" / run_id
    if not run_dir.exists():
        raise FileNotFoundError(f"strategy sleeve not found: {run_id}")
    return {
        "manifest": _load_json(run_dir / "manifest.json"),
        "state": _load_json(run_dir / "state.json"),
        "analysis": _load_json(run_dir / "analysis.json"),
        "sleeve_analysis": _load_json(run_dir / "sleeve_analysis.json"),
    }


def compare_strategy_sleeves(
    base_runs_dir: Path,
    *,
    limit: int = 10,
    dataset_id: str | None = None,
) -> StrategySleeveComparison:
    sleeves_dir = base_runs_dir / "backtests" / "sleeves"
    if not sleeves_dir.exists():
        return StrategySleeveComparison(
            dataset_id=dataset_id,
            ranking_policy=(
                "rank by total_return_pct desc, max_drawdown_pct asc, turnover_usdc asc, run_id asc"
            ),
            items=(),
        )
    items: list[StrategySleeveComparisonEntry] = []
    for run_dir in sorted((path for path in sleeves_dir.iterdir() if path.is_dir()), reverse=True):
        try:
            sleeve_analysis = _load_json(run_dir / "sleeve_analysis.json")
        except (FileNotFoundError, OSError, json.JSONDecodeError, ValueError):
            continue
        if dataset_id is not None and sleeve_analysis.get("dataset_id") != dataset_id:
            continue
        items.append(
            StrategySleeveComparisonEntry(
                rank=0,
                run_id=run_dir.name,
                dataset_id=_as_str(sleeve_analysis.get("dataset_id")),
                strategy_instance_id=_as_str(sleeve_analysis.get("strategy_instance_id")),
                strategy_id=_as_str(sleeve_analysis.get("strategy_id")),
                date_range_start=_as_str(sleeve_analysis.get("date_range_start")),
                date_range_end=_as_str(sleeve_analysis.get("date_range_end")),
                total_pnl_usdc=float(sleeve_analysis.get("total_pnl_usdc") or 0.0),
                total_return_pct=float(sleeve_analysis.get("total_return_pct") or 0.0),
                max_drawdown_usdc=float(sleeve_analysis.get("max_drawdown_usdc") or 0.0),
                max_drawdown_pct=float(sleeve_analysis.get("max_drawdown_pct") or 0.0),
                avg_abs_exposure_pct=_average_series_value(sleeve_analysis.get("daily_avg_abs_exposure_pct")),
                turnover_usdc=_sum_series_values(sleeve_analysis.get("daily_turnover_usdc")),
                asset_contribution_totals=_asset_contribution_totals(sleeve_analysis.get("asset_contributions")),
            )
        )
    ranked = tuple(
        StrategySleeveComparisonEntry(
            rank=index,
            run_id=item.run_id,
            dataset_id=item.dataset_id,
            strategy_instance_id=item.strategy_instance_id,
            strategy_id=item.strategy_id,
            date_range_start=item.date_range_start,
            date_range_end=item.date_range_end,
            total_pnl_usdc=item.total_pnl_usdc,
            total_return_pct=item.total_return_pct,
            max_drawdown_usdc=item.max_drawdown_usdc,
            max_drawdown_pct=item.max_drawdown_pct,
            avg_abs_exposure_pct=item.avg_abs_exposure_pct,
            turnover_usdc=item.turnover_usdc,
            asset_contribution_totals=item.asset_contribution_totals,
        )
        for index, item in enumerate(
            sorted(
                items,
                key=lambda item: (
                    -item.total_return_pct,
                    item.max_drawdown_pct,
                    item.turnover_usdc if item.turnover_usdc is not None else float("inf"),
                    item.run_id,
                ),
            )[:limit],
            start=1,
        )
    )
    return StrategySleeveComparison(
        dataset_id=dataset_id,
        ranking_policy="rank by total_return_pct desc, max_drawdown_pct asc, turnover_usdc asc, run_id asc",
        items=ranked,
    )


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"invalid json object in {path}")
    return payload


def _as_str(value: Any) -> str | None:
    return value if isinstance(value, str) else None


def _sum_series_values(value: Any) -> float | None:
    if not isinstance(value, list):
        return None
    total = 0.0
    count = 0
    for item in value:
        if isinstance(item, dict) and isinstance(item.get("value"), (int, float)):
            total += float(item["value"])
            count += 1
    return total if count > 0 else None


def _average_series_value(value: Any) -> float | None:
    if not isinstance(value, list):
        return None
    points = [
        float(item["value"])
        for item in value
        if isinstance(item, dict) and isinstance(item.get("value"), (int, float))
    ]
    if not points:
        return None
    return sum(points) / len(points)


def _asset_contribution_totals(value: Any) -> dict[str, float]:
    if not isinstance(value, list):
        return {}
    totals: dict[str, float] = {}
    for item in value:
        if not isinstance(item, dict):
            continue
        product_id = item.get("product_id")
        total_pnl_usdc = item.get("total_pnl_usdc")
        if isinstance(product_id, str) and isinstance(total_pnl_usdc, (int, float)):
            totals[product_id] = float(total_pnl_usdc)
    return totals
