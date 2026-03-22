"""Backtest suite execution and artifact persistence."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

from .analysis import RunAnalysis, analyze_run
from .backtest_data import HistoricalDataset
from .backtest_runner import BacktestAssetCycle, BacktestCycleResult, SharedCapitalBacktestRunner
from .config import AppConfig
from .domain import ExecutionSummary, Mode
from .strategy_registry import validate_strategy_id
from .telemetry import ArtifactStore


@dataclass(frozen=True, slots=True)
class BacktestRunSummary:
    run_id: str
    strategy_id: str
    analysis: RunAnalysis


@dataclass(frozen=True, slots=True)
class BacktestSuiteResult:
    suite_id: str
    dataset_id: str
    run_ids: tuple[str, ...]
    items: tuple[BacktestRunSummary, ...]


@dataclass(frozen=True, slots=True)
class BacktestSuiteProgress:
    phase: str
    phase_message: str
    total_runs: int
    completed_runs: int


class BacktestSuiteRunner:
    def __init__(
        self,
        *,
        base_runs_dir: Path,
        dataset: HistoricalDataset,
        config: AppConfig,
        products: Iterable[str] | None = None,
    ):
        self.base_runs_dir = base_runs_dir
        self.dataset = dataset
        self.config = config
        self.products = tuple(products or dataset.products)

    def run_suite(
        self,
        *,
        strategy_ids: Iterable[str],
        progress_callback: Callable[[BacktestSuiteProgress], None] | None = None,
    ) -> BacktestSuiteResult:
        suite_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        strategy_id_list = tuple(strategy_ids)
        if not strategy_id_list:
            raise ValueError("backtest suite requires at least one strategy")
        for strategy_id in strategy_id_list:
            validate_strategy_id(strategy_id)

        items: list[BacktestRunSummary] = []
        total_runs = len(strategy_id_list)
        for index, strategy_id in enumerate(strategy_id_list, start=1):
            if progress_callback is not None:
                progress_callback(
                    BacktestSuiteProgress(
                        phase="running_suite",
                        phase_message=f"Running strategy {index} of {total_runs}: {strategy_id}",
                        total_runs=total_runs,
                        completed_runs=index - 1,
                    )
                )
            strategy_config = replace(self.config.strategy, strategy_id=strategy_id)
            runtime_config = replace(
                self.config.runtime,
                mode=Mode.BACKTEST,
                product_id="MULTI_ASSET",
                interval_seconds=0,
                runs_dir=self.base_runs_dir / "backtests" / "runs",
            )
            run_config = replace(
                self.config,
                runtime=runtime_config,
                strategy=strategy_config,
            )
            runner = SharedCapitalBacktestRunner(
                config=run_config,
                dataset=self.dataset,
                products=self.products,
            )
            results = runner.run()
            if not results:
                raise ValueError(
                    "backtest suite produced no executable cycles for the selected dataset, "
                    "products, and lookback configuration"
                )
            run_config = replace(
                run_config,
                runtime=replace(run_config.runtime, iterations=len(results)),
            )
            artifact_store = ArtifactStore.create(run_config.runtime.runs_dir)
            artifact_store.write_metadata(
                run_config,
                extra_manifest={
                    "analysis_path": "analysis.json",
                    "dataset_id": self.dataset.dataset_id,
                    "suite_id": suite_id,
                    "products": list(self.products),
                    "date_range_start": self.dataset.start.isoformat(),
                    "date_range_end": self.dataset.end.isoformat(),
                    "granularity": self.dataset.granularity,
                },
            )
            for cycle in results:
                _record_backtest_cycle(artifact_store, cycle)
            analysis = analyze_run(artifact_store.run_dir)
            (artifact_store.run_dir / "analysis.json").write_text(
                json.dumps(asdict(analysis), indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            items.append(
                BacktestRunSummary(
                    run_id=artifact_store.run_id,
                    strategy_id=strategy_id,
                    analysis=analysis,
                )
            )
            if progress_callback is not None:
                progress_callback(
                    BacktestSuiteProgress(
                        phase="running_suite",
                        phase_message=f"Completed strategy {index} of {total_runs}: {strategy_id}",
                        total_runs=total_runs,
                        completed_runs=index,
                    )
                )

        suite_dir = self.base_runs_dir / "backtests" / "suites" / suite_id
        suite_dir.mkdir(parents=True, exist_ok=False)
        suite_manifest = {
            "suite_id": suite_id,
            "dataset_id": self.dataset.dataset_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "products": list(self.products),
            "run_ids": [item.run_id for item in items],
            "strategies": [item.strategy_id for item in items],
            "date_range_start": self.dataset.start.isoformat(),
            "date_range_end": self.dataset.end.isoformat(),
            "granularity": self.dataset.granularity,
        }
        (suite_dir / "manifest.json").write_text(
            json.dumps(suite_manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return BacktestSuiteResult(
            suite_id=suite_id,
            dataset_id=self.dataset.dataset_id,
            run_ids=tuple(item.run_id for item in items),
            items=tuple(items),
        )


def _record_backtest_cycle(artifact_store: ArtifactStore, cycle: BacktestCycleResult) -> None:
    aggregate_summary = _aggregate_execution_summary(cycle.assets.values())
    aggregate_reason = _aggregate_no_trade_reason(cycle.assets.values())
    event = {
        "run_id": artifact_store.run_id,
        "cycle_id": cycle.cycle_id,
        "mode": cycle.mode,
        "timestamp": cycle.timestamp,
        "execution_summary": aggregate_summary,
        "no_trade_reason": aggregate_reason,
        "position": asdict(cycle.portfolio),
        "portfolio": asdict(cycle.portfolio),
        "asset_decisions": {
            product_id: {
                "signal": asdict(asset.signal),
                "risk_decision": asdict(asset.risk_decision),
                "execution_summary": asdict(asset.execution_summary),
                "no_trade_reason": asdict(asset.no_trade_reason) if asset.no_trade_reason else None,
                "order_intent": asdict(asset.order_intent) if asset.order_intent else None,
                "state": asdict(asset.state),
            }
            for product_id, asset in cycle.assets.items()
        },
        "fills": [asdict(asset.fill) for asset in cycle.assets.values() if asset.fill is not None],
    }
    artifact_store.append_event("cycle", event)
    for product_id, asset in cycle.assets.items():
        if asset.fill is not None:
            artifact_store.append_fill_row(
                {
                    "run_id": artifact_store.run_id,
                    "cycle_id": cycle.cycle_id,
                    "product_id": product_id,
                    "fill": asset.fill,
                }
            )
    artifact_store.append_position_row(
        {
            "run_id": artifact_store.run_id,
            "cycle_id": cycle.cycle_id,
            "position": asdict(cycle.portfolio),
            "portfolio": asdict(cycle.portfolio),
            "asset_positions": {
                product_id: asdict(asset.state)
                for product_id, asset in cycle.assets.items()
            },
        }
    )
    artifact_store.write_state(
        {
            "run_id": artifact_store.run_id,
            "cycle_id": cycle.cycle_id,
            "mode": cycle.mode,
            "execution_summary": aggregate_summary,
            "no_trade_reason": aggregate_reason,
            "position": asdict(cycle.portfolio),
            "portfolio": asdict(cycle.portfolio),
            "asset_positions": {
                product_id: asdict(asset.state)
                for product_id, asset in cycle.assets.items()
            },
        }
    )


def _aggregate_execution_summary(assets: Iterable[BacktestAssetCycle]) -> ExecutionSummary:
    asset_list = list(assets)
    fills = [asset for asset in asset_list if asset.fill is not None]
    if fills:
        count = len(fills)
        noun = "asset" if count == 1 else "assets"
        return ExecutionSummary(
            action="filled",
            reason_code="filled",
            reason_message=f"Filled {count} {noun} during the cycle.",
            summary=f"Filled {count} {noun} toward portfolio targets.",
        )
    if any(asset.execution_summary.action == "halted" for asset in asset_list):
        return ExecutionSummary(
            action="halted",
            reason_code="drawdown_halt",
            reason_message="Trading halted for the cycle because the drawdown guard triggered.",
            summary="Trading halted for the cycle because the drawdown guard triggered.",
        )
    codes = {
        asset.no_trade_reason.code
        for asset in asset_list
        if asset.no_trade_reason is not None
    }
    if len(codes) == 1:
        reason = next(asset.no_trade_reason for asset in asset_list if asset.no_trade_reason is not None)
        return ExecutionSummary(
            action="skipped",
            reason_code=reason.code,
            reason_message=reason.message,
            summary=f"Skipped rebalancing: {reason.message}",
        )
    return ExecutionSummary(
        action="skipped",
        reason_code="mixed_decisions",
        reason_message="Assets produced mixed no-trade reasons for the cycle.",
        summary="Skipped rebalancing because assets produced mixed no-trade reasons.",
    )


def _aggregate_no_trade_reason(assets: Iterable[BacktestAssetCycle]) -> dict[str, Any] | None:
    reasons = [
        asset.no_trade_reason
        for asset in assets
        if asset.no_trade_reason is not None
    ]
    if not reasons:
        return None
    unique_codes = {reason.code for reason in reasons}
    if len(unique_codes) == 1:
        reason = reasons[0]
        return {"code": reason.code, "message": reason.message}
    return {
        "code": "mixed_decisions",
        "message": "Assets produced mixed no-trade reasons for the cycle.",
    }
