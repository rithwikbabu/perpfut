"""Daily mean-variance portfolio optimizer over cached sleeve returns."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from .analysis import SeriesPoint


@dataclass(frozen=True, slots=True)
class PortfolioOptimizationConfig:
    rebalance_frequency: str = "daily"
    lookback_days: int = 60
    max_strategy_weight: float = 0.40
    covariance_shrinkage: float = 0.20
    ridge_penalty: float = 1e-4
    turnover_cost_bps: float = 5.0


@dataclass(frozen=True, slots=True)
class StrategySleeveReturnStream:
    strategy_instance_id: str
    strategy_id: str
    dataset_id: str
    config_fingerprint: str
    daily_returns: tuple[SeriesPoint, ...]


@dataclass(frozen=True, slots=True)
class PortfolioWeightSnapshot:
    date: str
    weights: dict[str, float]
    cash_weight: float
    turnover: float
    gross_weight: float


@dataclass(frozen=True, slots=True)
class PortfolioOptimizationDiagnostic:
    date: str
    expected_returns: dict[str, float]
    covariance_matrix: dict[str, dict[str, float]]
    constraint_status: str


@dataclass(frozen=True, slots=True)
class PortfolioOptimizationResult:
    strategy_instance_ids: tuple[str, ...]
    daily_gross_returns: tuple[SeriesPoint, ...]
    daily_net_returns: tuple[SeriesPoint, ...]
    daily_turnover: tuple[SeriesPoint, ...]
    cumulative_net_value: tuple[SeriesPoint, ...]
    weight_history: tuple[PortfolioWeightSnapshot, ...]
    diagnostics: tuple[PortfolioOptimizationDiagnostic, ...]


def load_sleeve_return_stream(payload: dict[str, Any]) -> StrategySleeveReturnStream:
    strategy_instance_id = _require_str(payload, "strategy_instance_id")
    strategy_id = _require_str(payload, "strategy_id")
    dataset_id = _require_str(payload, "dataset_id")
    config_fingerprint = _require_str(payload, "config_fingerprint")
    daily_returns_payload = payload.get("daily_returns")
    if not isinstance(daily_returns_payload, list) or not daily_returns_payload:
        raise ValueError("sleeve analysis must include non-empty daily_returns")
    daily_returns = tuple(_parse_series_point(item) for item in daily_returns_payload)
    return StrategySleeveReturnStream(
        strategy_instance_id=strategy_instance_id,
        strategy_id=strategy_id,
        dataset_id=dataset_id,
        config_fingerprint=config_fingerprint,
        daily_returns=daily_returns,
    )


def optimize_strategy_portfolio(
    sleeves: list[StrategySleeveReturnStream],
    *,
    config: PortfolioOptimizationConfig | None = None,
) -> PortfolioOptimizationResult:
    if not sleeves:
        raise ValueError("portfolio optimizer requires at least one sleeve return stream")
    optimizer_config = config or PortfolioOptimizationConfig()
    if optimizer_config.rebalance_frequency != "daily":
        raise ValueError("only daily rebalancing is supported in v1")
    if optimizer_config.lookback_days <= 0:
        raise ValueError("lookback_days must be positive")
    if optimizer_config.max_strategy_weight <= 0.0:
        raise ValueError("max_strategy_weight must be positive")
    if optimizer_config.covariance_shrinkage < 0.0 or optimizer_config.covariance_shrinkage > 1.0:
        raise ValueError("covariance_shrinkage must be between 0 and 1")
    if optimizer_config.ridge_penalty < 0.0:
        raise ValueError("ridge_penalty must be non-negative")
    if optimizer_config.turnover_cost_bps < 0.0:
        raise ValueError("turnover_cost_bps must be non-negative")

    aligned_dates = _aligned_dates(sleeves)
    strategy_instance_ids = tuple(sleeve.strategy_instance_id for sleeve in sleeves)
    returns_matrix = np.array(
        [
            [point.value for point in sleeve.daily_returns]
            for sleeve in sleeves
        ],
        dtype=float,
    ).T
    previous_weights = np.zeros(len(sleeves), dtype=float)
    cumulative_value = 1.0
    daily_gross_returns: list[SeriesPoint] = []
    daily_net_returns: list[SeriesPoint] = []
    daily_turnover: list[SeriesPoint] = []
    cumulative_series: list[SeriesPoint] = []
    weight_history: list[PortfolioWeightSnapshot] = []
    diagnostics: list[PortfolioOptimizationDiagnostic] = []

    for day_index, date_label in enumerate(aligned_dates):
        history = returns_matrix[max(0, day_index - optimizer_config.lookback_days) : day_index]
        if history.size == 0:
            weights = np.zeros(len(sleeves), dtype=float)
            mu = np.zeros(len(sleeves), dtype=float)
            cov = np.zeros((len(sleeves), len(sleeves)), dtype=float)
            constraint_status = "insufficient_history"
        else:
            mu = np.mean(history, axis=0)
            cov = _estimate_covariance(
                history,
                shrinkage=optimizer_config.covariance_shrinkage,
                ridge_penalty=optimizer_config.ridge_penalty,
            )
            raw_scores = np.linalg.solve(
                cov + (optimizer_config.ridge_penalty * np.eye(len(sleeves))),
                mu,
            )
            weights = _project_long_only_weights(
                raw_scores,
                max_weight=optimizer_config.max_strategy_weight,
            )
            constraint_status = "optimized"
        turnover = float(np.sum(np.abs(weights - previous_weights)))
        gross_return = float(np.dot(weights, returns_matrix[day_index]))
        trading_cost = turnover * (optimizer_config.turnover_cost_bps / 10_000.0)
        net_return = gross_return - trading_cost
        cumulative_value *= 1.0 + net_return

        weight_history.append(
            PortfolioWeightSnapshot(
                date=date_label,
                weights={
                    strategy_instance_ids[index]: float(weight)
                    for index, weight in enumerate(weights)
                },
                cash_weight=float(max(1.0 - np.sum(weights), 0.0)),
                turnover=turnover,
                gross_weight=float(np.sum(weights)),
            )
        )
        diagnostics.append(
            PortfolioOptimizationDiagnostic(
                date=date_label,
                expected_returns={
                    strategy_instance_ids[index]: float(value)
                    for index, value in enumerate(mu)
                },
                covariance_matrix={
                    strategy_instance_ids[row]: {
                        strategy_instance_ids[column]: float(cov[row, column])
                        for column in range(len(sleeves))
                    }
                    for row in range(len(sleeves))
                },
                constraint_status=constraint_status,
            )
        )
        daily_gross_returns.append(SeriesPoint(label=date_label, value=gross_return))
        daily_net_returns.append(SeriesPoint(label=date_label, value=net_return))
        daily_turnover.append(SeriesPoint(label=date_label, value=turnover))
        cumulative_series.append(SeriesPoint(label=date_label, value=cumulative_value))
        previous_weights = weights

    return PortfolioOptimizationResult(
        strategy_instance_ids=strategy_instance_ids,
        daily_gross_returns=tuple(daily_gross_returns),
        daily_net_returns=tuple(daily_net_returns),
        daily_turnover=tuple(daily_turnover),
        cumulative_net_value=tuple(cumulative_series),
        weight_history=tuple(weight_history),
        diagnostics=tuple(diagnostics),
    )


def _aligned_dates(sleeves: list[StrategySleeveReturnStream]) -> tuple[str, ...]:
    base_dates = [point.label for point in sleeves[0].daily_returns]
    for sleeve in sleeves[1:]:
        dates = [point.label for point in sleeve.daily_returns]
        if dates != base_dates:
            raise ValueError("sleeve return streams must share the same ordered daily date labels")
    return tuple(base_dates)


def _estimate_covariance(
    history: np.ndarray,
    *,
    shrinkage: float,
    ridge_penalty: float,
) -> np.ndarray:
    if history.shape[0] == 1:
        base = np.zeros((history.shape[1], history.shape[1]), dtype=float)
    else:
        base = np.cov(history, rowvar=False, ddof=1)
        if np.isscalar(base):
            base = np.array([[float(base)]], dtype=float)
    diagonal = np.diag(np.diag(base))
    shrunk = ((1.0 - shrinkage) * base) + (shrinkage * diagonal)
    return shrunk + (ridge_penalty * np.eye(history.shape[1]))


def _project_long_only_weights(raw_scores: np.ndarray, *, max_weight: float) -> np.ndarray:
    positive = np.maximum(raw_scores, 0.0)
    if np.sum(positive) <= 1e-12:
        return np.zeros_like(positive)

    weights = np.zeros_like(positive)
    remaining_budget = 1.0
    active = positive > 0.0
    while np.any(active) and remaining_budget > 1e-12:
        active_scores = positive[active]
        total_score = float(np.sum(active_scores))
        if total_score <= 1e-12:
            break
        proposed = (remaining_budget * active_scores) / total_score
        if np.all(proposed <= max_weight + 1e-12):
            weights[active] += proposed
            remaining_budget = 0.0
            break
        active_indexes = np.flatnonzero(active)
        clipped_any = False
        for local_index, proposed_weight in enumerate(proposed):
            if proposed_weight > max_weight + 1e-12:
                absolute_index = active_indexes[local_index]
                weights[absolute_index] = max_weight
                remaining_budget -= max_weight
                active[absolute_index] = False
                clipped_any = True
        if not clipped_any:
            weights[active] += proposed
            remaining_budget = 0.0
            break
    return weights


def _parse_series_point(value: Any) -> SeriesPoint:
    if not isinstance(value, dict):
        raise ValueError("series point payload must be an object")
    label = _require_str(value, "label")
    raw_value = value.get("value")
    if not isinstance(raw_value, (int, float)):
        raise ValueError("series point value must be numeric")
    return SeriesPoint(label=label, value=float(raw_value))


def _require_str(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"missing string field '{key}' in sleeve analysis payload")
    return value
