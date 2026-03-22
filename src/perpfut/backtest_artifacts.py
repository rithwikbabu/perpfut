"""Shared artifact writers for multi-asset historical research runs."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Iterable

from .backtest_runner import BacktestAssetCycle, BacktestCycleResult
from .domain import ExecutionSummary
from .telemetry import ArtifactStore


def record_backtest_cycle(artifact_store: ArtifactStore, cycle: BacktestCycleResult) -> None:
    aggregate_summary = aggregate_execution_summary(cycle.assets.values())
    aggregate_reason = aggregate_no_trade_reason(cycle.assets.values())
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


def aggregate_execution_summary(assets: Iterable[BacktestAssetCycle]) -> ExecutionSummary:
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


def aggregate_no_trade_reason(assets: Iterable[BacktestAssetCycle]) -> dict[str, Any] | None:
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
