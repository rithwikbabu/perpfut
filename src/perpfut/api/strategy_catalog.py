"""Static strategy-builder metadata for the research controls UI."""

from __future__ import annotations

from .schemas import (
    StrategyCatalogFieldResponse,
    StrategyCatalogItemResponse,
    StrategyCatalogResponse,
)
from ..config import AppConfig
from ..strategy_registry import STRATEGY_REGISTRY


_STRATEGY_LABELS = {
    "momentum": "Momentum",
    "mean_reversion": "Mean Reversion",
}


def build_strategy_catalog(config: AppConfig) -> StrategyCatalogResponse:
    strategy_fields = [
        StrategyCatalogFieldResponse(
            key="lookback_candles",
            label="Lookback Candles",
            inputKind="integer",
            required=True,
            defaultValue=config.strategy.lookback_candles,
            minValue=1,
            step=1,
        ),
        StrategyCatalogFieldResponse(
            key="signal_scale",
            label="Signal Scale",
            inputKind="number",
            required=True,
            defaultValue=config.strategy.signal_scale,
            minValue=0.0,
            step=0.1,
        ),
    ]
    risk_fields = [
        StrategyCatalogFieldResponse(
            key="max_abs_position",
            label="Max Abs Position",
            inputKind="number",
            required=False,
            defaultValue=config.risk.max_abs_position,
            minValue=0.0,
            step=0.01,
        ),
        StrategyCatalogFieldResponse(
            key="max_gross_position",
            label="Max Gross Position",
            inputKind="number",
            required=False,
            defaultValue=config.risk.max_gross_position,
            minValue=0.0,
            step=0.01,
        ),
        StrategyCatalogFieldResponse(
            key="rebalance_threshold",
            label="Rebalance Threshold",
            inputKind="number",
            required=False,
            defaultValue=config.risk.rebalance_threshold,
            minValue=0.0,
            step=0.01,
        ),
        StrategyCatalogFieldResponse(
            key="min_trade_notional_usdc",
            label="Min Trade Notional (USDC)",
            inputKind="number",
            required=False,
            defaultValue=config.risk.min_trade_notional_usdc,
            minValue=0.0,
            step=1.0,
        ),
        StrategyCatalogFieldResponse(
            key="max_daily_drawdown_usdc",
            label="Max Daily Drawdown (USDC)",
            inputKind="number",
            required=False,
            defaultValue=config.risk.max_daily_drawdown_usdc,
            minValue=0.0,
            step=1.0,
        ),
    ]
    items = [
        StrategyCatalogItemResponse(
            strategyId=strategy_id,
            label=_STRATEGY_LABELS.get(strategy_id, strategy_id.replace("_", " ").title()),
            strategyParams=strategy_fields,
            riskOverrides=risk_fields,
        )
        for strategy_id in sorted(STRATEGY_REGISTRY)
    ]
    return StrategyCatalogResponse(items=items, count=len(items))
