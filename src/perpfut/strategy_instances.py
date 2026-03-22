"""Research-only strategy instance specifications for multi-sleeve backtests."""

from __future__ import annotations

import json
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

from .config import RiskConfig, StrategyConfig
from .strategy_registry import validate_strategy_id

JSONScalar = str | int | float | bool | None

_ALLOWED_STRATEGY_PARAMS = frozenset({"lookback_candles", "signal_scale"})
_ALLOWED_RISK_OVERRIDES = frozenset(
    {
        "max_abs_position",
        "max_gross_position",
        "rebalance_threshold",
        "min_trade_notional_usdc",
        "max_daily_drawdown_usdc",
    }
)


@dataclass(frozen=True, slots=True)
class StrategyInstanceSpec:
    strategy_instance_id: str
    strategy_id: str
    universe: tuple[str, ...]
    strategy_params: dict[str, JSONScalar] = field(default_factory=dict)
    risk_overrides: dict[str, float] = field(default_factory=dict)

    def to_strategy_config(self, *, base: StrategyConfig) -> StrategyConfig:
        strategy = replace(base, strategy_id=self.strategy_id)
        if "lookback_candles" in self.strategy_params:
            strategy = replace(
                strategy,
                lookback_candles=int(self.strategy_params["lookback_candles"]),
            )
        if "signal_scale" in self.strategy_params:
            strategy = replace(
                strategy,
                signal_scale=float(self.strategy_params["signal_scale"]),
            )
        return strategy

    def to_risk_config(self, *, base: RiskConfig) -> RiskConfig:
        risk = base
        for key, value in self.risk_overrides.items():
            risk = replace(risk, **{key: value})
        return risk

    def to_payload(self) -> dict[str, Any]:
        return {
            "strategy_instance_id": self.strategy_instance_id,
            "strategy_id": self.strategy_id,
            "universe": list(self.universe),
            "strategy_params": dict(self.strategy_params),
            "risk_overrides": dict(self.risk_overrides),
        }


def load_strategy_instance_specs(path: Path) -> tuple[StrategyInstanceSpec, ...]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return parse_strategy_instance_specs(payload, source=str(path))


def parse_strategy_instance_specs(
    payload: Any,
    *,
    source: str = "payload",
) -> tuple[StrategyInstanceSpec, ...]:
    if not isinstance(payload, list):
        raise ValueError(f"strategy instance spec in {source} must be a list")

    specs: list[StrategyInstanceSpec] = []
    seen_instance_ids: set[str] = set()
    for index, item in enumerate(payload):
        if not isinstance(item, dict):
            raise ValueError(f"strategy instance at index {index} in {source} must be an object")
        spec = _parse_strategy_instance(item, index=index, source=source)
        if spec.strategy_instance_id in seen_instance_ids:
            raise ValueError(
                f"duplicate strategy_instance_id '{spec.strategy_instance_id}' in {source}"
            )
        seen_instance_ids.add(spec.strategy_instance_id)
        specs.append(spec)
    return tuple(specs)


def _parse_strategy_instance(
    payload: dict[str, Any],
    *,
    index: int,
    source: str,
) -> StrategyInstanceSpec:
    instance_id = _require_non_empty_string(
        payload.get("strategy_instance_id"),
        field_name="strategy_instance_id",
        index=index,
        source=source,
    )
    strategy_id = _require_non_empty_string(
        payload.get("strategy_id"),
        field_name="strategy_id",
        index=index,
        source=source,
    )
    validate_strategy_id(strategy_id)
    universe = _parse_universe(payload.get("universe"), index=index, source=source)
    strategy_params = _parse_strategy_params(
        payload.get("strategy_params"),
        index=index,
        source=source,
    )
    risk_overrides = _parse_risk_overrides(
        payload.get("risk_overrides"),
        index=index,
        source=source,
    )
    return StrategyInstanceSpec(
        strategy_instance_id=instance_id,
        strategy_id=strategy_id,
        universe=universe,
        strategy_params=strategy_params,
        risk_overrides=risk_overrides,
    )


def _parse_universe(value: Any, *, index: int, source: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"strategy instance at index {index} in {source} must have a non-empty universe")
    universe: list[str] = []
    seen_products: set[str] = set()
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise ValueError(
                f"strategy instance at index {index} in {source} has invalid universe product"
            )
        product_id = item.strip()
        if product_id in seen_products:
            raise ValueError(
                f"strategy instance at index {index} in {source} contains duplicate universe product '{product_id}'"
            )
        seen_products.add(product_id)
        universe.append(product_id)
    return tuple(universe)


def _parse_strategy_params(value: Any, *, index: int, source: str) -> dict[str, JSONScalar]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError(
            f"strategy_params for strategy instance at index {index} in {source} must be an object"
        )
    params: dict[str, JSONScalar] = {}
    for key, item in value.items():
        if key not in _ALLOWED_STRATEGY_PARAMS:
            allowed = ", ".join(sorted(_ALLOWED_STRATEGY_PARAMS))
            raise ValueError(
                f"strategy param '{key}' for strategy instance at index {index} in {source} "
                f"must be one of: {allowed}"
            )
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            raise ValueError(
                f"strategy param '{key}' for strategy instance at index {index} in {source} must be numeric"
            )
        numeric_value = float(item) if key == "signal_scale" else int(item)
        if key == "lookback_candles" and numeric_value <= 0:
            raise ValueError("lookback_candles must be positive")
        params[key] = numeric_value
    return params


def _parse_risk_overrides(value: Any, *, index: int, source: str) -> dict[str, float]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError(
            f"risk_overrides for strategy instance at index {index} in {source} must be an object"
        )
    overrides: dict[str, float] = {}
    for key, item in value.items():
        if key not in _ALLOWED_RISK_OVERRIDES:
            allowed = ", ".join(sorted(_ALLOWED_RISK_OVERRIDES))
            raise ValueError(
                f"risk override '{key}' in {source} must be one of: {allowed}"
            )
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            raise ValueError(
                f"risk override '{key}' for strategy instance at index {index} in {source} must be numeric"
            )
        numeric_value = float(item)
        if numeric_value < 0.0:
            raise ValueError(f"risk override '{key}' must be non-negative")
        overrides[key] = numeric_value
    return overrides


def _require_non_empty_string(
    value: Any,
    *,
    field_name: str,
    index: int,
    source: str,
) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(
            f"strategy instance at index {index} in {source} must define a non-empty {field_name}"
        )
    return value.strip()
