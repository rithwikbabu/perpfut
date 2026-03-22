"""Reusable strategy-sleeve backtests for optimizer research."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import Any

from .analysis import RunAnalysis, SeriesPoint, analyze_run
from .backtest_artifacts import record_backtest_cycle
from .backtest_data import HistoricalDataset
from .backtest_runner import BacktestCycleResult, SharedCapitalBacktestRunner
from .config import AppConfig
from .domain import Mode
from .strategy_instances import StrategyInstanceSpec
from .telemetry import ArtifactStore


@dataclass(frozen=True, slots=True)
class AssetContributionSeries:
    product_id: str
    total_pnl_usdc: float
    daily_pnl_series: tuple[SeriesPoint, ...]


@dataclass(frozen=True, slots=True)
class StrategySleeveAnalysis:
    run_id: str
    dataset_id: str
    strategy_instance_id: str
    strategy_id: str
    config_fingerprint: str
    date_range_start: str
    date_range_end: str
    total_pnl_usdc: float
    total_return_pct: float
    max_drawdown_usdc: float
    max_drawdown_pct: float
    daily_returns: tuple[SeriesPoint, ...]
    daily_turnover_usdc: tuple[SeriesPoint, ...]
    daily_avg_abs_exposure_pct: tuple[SeriesPoint, ...]
    daily_drawdown_usdc: tuple[SeriesPoint, ...]
    asset_contributions: tuple[AssetContributionSeries, ...]


@dataclass(frozen=True, slots=True)
class StrategySleeveResult:
    run_id: str
    dataset_id: str
    strategy_instance_id: str
    strategy_id: str
    config_fingerprint: str
    run_dir: Path
    analysis: RunAnalysis
    sleeve_analysis: StrategySleeveAnalysis


def run_strategy_sleeve(
    *,
    base_runs_dir: Path,
    dataset: HistoricalDataset,
    config: AppConfig,
    strategy_instance: StrategyInstanceSpec,
) -> StrategySleeveResult:
    sleeves_dir = base_runs_dir / "backtests" / "sleeves"
    run_config = build_sleeve_config(
        config=config,
        strategy_instance=strategy_instance,
        runs_dir=sleeves_dir,
    )
    config_fingerprint = compute_strategy_instance_fingerprint(
        config=config,
        strategy_instance=strategy_instance,
    )
    runner = SharedCapitalBacktestRunner(
        config=run_config,
        dataset=dataset,
        products=strategy_instance.universe,
    )
    results = runner.run()
    if not results:
        raise ValueError(
            "strategy sleeve produced no executable cycles for the selected dataset, "
            "universe, and lookback configuration"
        )

    artifact_store = ArtifactStore.create(sleeves_dir)
    artifact_store.write_metadata(
        replace(
            run_config,
            runtime=replace(run_config.runtime, iterations=len(results)),
        ),
        extra_manifest={
            "analysis_path": "analysis.json",
            "sleeve_analysis_path": "sleeve_analysis.json",
            "dataset_id": dataset.dataset_id,
            "strategy_instance": strategy_instance.to_payload(),
            "strategy_instance_id": strategy_instance.strategy_instance_id,
            "products": list(strategy_instance.universe),
            "date_range_start": dataset.start.isoformat(),
            "date_range_end": dataset.end.isoformat(),
            "granularity": dataset.granularity,
            "config_fingerprint": config_fingerprint,
        },
    )
    for cycle in results:
        record_backtest_cycle(artifact_store, cycle)

    analysis = analyze_run(artifact_store.run_dir)
    (artifact_store.run_dir / "analysis.json").write_text(
        json.dumps(asdict(analysis), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    sleeve_analysis = build_strategy_sleeve_analysis(
        run_id=artifact_store.run_id,
        dataset=dataset,
        strategy_instance=strategy_instance,
        config_fingerprint=config_fingerprint,
        config=run_config,
        results=results,
        analysis=analysis,
    )
    (artifact_store.run_dir / "sleeve_analysis.json").write_text(
        json.dumps(asdict(sleeve_analysis), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return StrategySleeveResult(
        run_id=artifact_store.run_id,
        dataset_id=dataset.dataset_id,
        strategy_instance_id=strategy_instance.strategy_instance_id,
        strategy_id=strategy_instance.strategy_id,
        config_fingerprint=config_fingerprint,
        run_dir=artifact_store.run_dir,
        analysis=analysis,
        sleeve_analysis=sleeve_analysis,
    )


def build_sleeve_config(
    *,
    config: AppConfig,
    strategy_instance: StrategyInstanceSpec,
    runs_dir: Path,
) -> AppConfig:
    strategy = strategy_instance.to_strategy_config(base=config.strategy)
    risk = strategy_instance.to_risk_config(base=config.risk)
    runtime = replace(
        config.runtime,
        mode=Mode.BACKTEST,
        product_id="MULTI_ASSET",
        interval_seconds=0,
        runs_dir=runs_dir,
    )
    return replace(config, runtime=runtime, strategy=strategy, risk=risk)


def compute_strategy_instance_fingerprint(
    *,
    config: AppConfig,
    strategy_instance: StrategyInstanceSpec,
) -> str:
    payload = {
        "strategy_instance": strategy_instance.to_payload(),
        "strategy": asdict(strategy_instance.to_strategy_config(base=config.strategy)),
        "risk": asdict(strategy_instance.to_risk_config(base=config.risk)),
        "simulation": asdict(config.simulation),
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True).encode("utf-8")
    ).hexdigest()


def build_strategy_sleeve_analysis(
    *,
    run_id: str,
    dataset: HistoricalDataset,
    strategy_instance: StrategyInstanceSpec,
    config_fingerprint: str,
    config: AppConfig,
    results: list[BacktestCycleResult],
    analysis: RunAnalysis,
) -> StrategySleeveAnalysis:
    max_abs_notional = config.simulation.starting_collateral_usdc * config.simulation.max_leverage
    daily = _aggregate_daily_metrics(
        results=results,
        starting_equity_usdc=config.simulation.starting_collateral_usdc,
        max_abs_notional_usdc=max_abs_notional,
        universe=strategy_instance.universe,
    )
    return StrategySleeveAnalysis(
        run_id=run_id,
        dataset_id=dataset.dataset_id,
        strategy_instance_id=strategy_instance.strategy_instance_id,
        strategy_id=strategy_instance.strategy_id,
        config_fingerprint=config_fingerprint,
        date_range_start=dataset.start.isoformat(),
        date_range_end=dataset.end.isoformat(),
        total_pnl_usdc=analysis.total_pnl_usdc,
        total_return_pct=analysis.total_return_pct,
        max_drawdown_usdc=analysis.max_drawdown_usdc,
        max_drawdown_pct=analysis.max_drawdown_pct,
        daily_returns=tuple(daily["returns"]),
        daily_turnover_usdc=tuple(daily["turnover"]),
        daily_avg_abs_exposure_pct=tuple(daily["exposure"]),
        daily_drawdown_usdc=tuple(daily["drawdown"]),
        asset_contributions=tuple(daily["asset_contributions"]),
    )


def load_strategy_sleeve_analysis(run_dir: Path) -> dict[str, Any]:
    analysis_path = run_dir / "sleeve_analysis.json"
    payload = json.loads(analysis_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"invalid json object in {analysis_path}")
    return payload


def _aggregate_daily_metrics(
    *,
    results: list[BacktestCycleResult],
    starting_equity_usdc: float,
    max_abs_notional_usdc: float,
    universe: tuple[str, ...],
) -> dict[str, Any]:
    daily_rows: dict[str, dict[str, Any]] = {}
    previous_asset_pnl = {product_id: 0.0 for product_id in universe}
    for cycle in results:
        day = _day_key(cycle.timestamp)
        row = daily_rows.setdefault(
            day,
            {
                "end_equity": starting_equity_usdc,
                "turnover_usdc": 0.0,
                "exposure_points": [],
                "asset_pnl": {product_id: 0.0 for product_id in universe},
            },
        )
        row["end_equity"] = cycle.portfolio.equity_usdc
        exposure = (
            abs(cycle.portfolio.gross_notional_usdc / max_abs_notional_usdc)
            if abs(max_abs_notional_usdc) > 1e-12
            else 0.0
        )
        row["exposure_points"].append(exposure)
        for product_id, asset in cycle.assets.items():
            if asset.fill is not None:
                row["turnover_usdc"] += abs(asset.fill.quantity * asset.fill.price)
            asset_pnl = asset.state.realized_pnl_usdc + asset.state.unrealized_pnl_usdc
            row["asset_pnl"][product_id] += asset_pnl - previous_asset_pnl[product_id]
            previous_asset_pnl[product_id] = asset_pnl

    ordered_days = sorted(daily_rows)
    previous_end_equity = starting_equity_usdc
    peak_equity = starting_equity_usdc
    daily_returns: list[SeriesPoint] = []
    daily_turnover: list[SeriesPoint] = []
    daily_exposure: list[SeriesPoint] = []
    daily_drawdown: list[SeriesPoint] = []
    asset_contribution_points = {
        product_id: []
        for product_id in universe
    }
    for day in ordered_days:
        row = daily_rows[day]
        end_equity = float(row["end_equity"])
        daily_return = (
            (end_equity / previous_end_equity) - 1.0
            if abs(previous_end_equity) > 1e-12
            else 0.0
        )
        previous_end_equity = end_equity
        peak_equity = max(peak_equity, end_equity)
        avg_exposure = (
            sum(row["exposure_points"]) / len(row["exposure_points"])
            if row["exposure_points"]
            else 0.0
        )
        daily_returns.append(SeriesPoint(label=day, value=daily_return))
        daily_turnover.append(SeriesPoint(label=day, value=float(row["turnover_usdc"])))
        daily_exposure.append(SeriesPoint(label=day, value=avg_exposure))
        daily_drawdown.append(SeriesPoint(label=day, value=max(peak_equity - end_equity, 0.0)))
        for product_id in universe:
            asset_contribution_points[product_id].append(
                SeriesPoint(
                    label=day,
                    value=float(row["asset_pnl"][product_id]),
                )
            )

    asset_contributions = [
        AssetContributionSeries(
            product_id=product_id,
            total_pnl_usdc=sum(point.value for point in points),
            daily_pnl_series=tuple(points),
        )
        for product_id, points in asset_contribution_points.items()
    ]
    return {
        "returns": daily_returns,
        "turnover": daily_turnover,
        "exposure": daily_exposure,
        "drawdown": daily_drawdown,
        "asset_contributions": asset_contributions,
    }


def _day_key(timestamp: str) -> str:
    return datetime.fromisoformat(timestamp.replace("Z", "+00:00")).date().isoformat()
