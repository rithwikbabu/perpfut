"""Daily mean-variance portfolio optimizer over cached sleeve returns."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import math
from typing import Any

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
    returns_matrix = [
        [point.value for point in sleeve.daily_returns]
        for sleeve in sleeves
    ]
    current_holdings = [0.0 for _ in sleeves]
    cumulative_value = 1.0
    daily_gross_returns: list[SeriesPoint] = []
    daily_net_returns: list[SeriesPoint] = []
    daily_turnover: list[SeriesPoint] = []
    cumulative_series: list[SeriesPoint] = []
    weight_history: list[PortfolioWeightSnapshot] = []
    diagnostics: list[PortfolioOptimizationDiagnostic] = []

    for day_index, date_label in enumerate(aligned_dates):
        history_start = max(0, day_index - optimizer_config.lookback_days)
        history = [
            [
                returns_matrix[strategy_index][history_index]
                for strategy_index in range(len(sleeves))
            ]
            for history_index in range(history_start, day_index)
        ]
        if not history:
            weights = [0.0 for _ in sleeves]
            mu = [0.0 for _ in sleeves]
            cov = [
                [0.0 for _ in sleeves]
                for _ in sleeves
            ]
            constraint_status = "insufficient_history"
        else:
            mu = _mean_vector(history)
            cov = _estimate_covariance(
                history,
                shrinkage=optimizer_config.covariance_shrinkage,
                ridge_penalty=optimizer_config.ridge_penalty,
            )
            raw_scores = _solve_linear_system(cov, mu)
            if raw_scores is None:
                raw_scores = list(mu)
                constraint_status = "fallback_mean_only"
            else:
                constraint_status = "optimized"
            weights = _project_long_only_weights(
                raw_scores,
                max_weight=optimizer_config.max_strategy_weight,
            )
        turnover = sum(
            abs(weight - holding)
            for weight, holding in zip(weights, current_holdings)
        )
        gross_return = sum(
            weight * returns_matrix[strategy_index][day_index]
            for strategy_index, weight in enumerate(weights)
        )
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
                cash_weight=float(max(1.0 - sum(weights), 0.0)),
                turnover=turnover,
                gross_weight=float(sum(weights)),
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
                        strategy_instance_ids[column]: float(cov[row][column])
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
        current_holdings = _drift_holdings(
            weights,
            day_returns=[
                returns_matrix[strategy_index][day_index]
                for strategy_index in range(len(sleeves))
            ],
        )

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
    _validate_ordered_utc_day_labels(base_dates)
    for sleeve in sleeves[1:]:
        dates = [point.label for point in sleeve.daily_returns]
        if dates != base_dates:
            raise ValueError("sleeve return streams must share the same ordered daily date labels")
    return tuple(base_dates)


def _validate_ordered_utc_day_labels(labels: list[str]) -> None:
    parsed_dates: list[date] = []
    for label in labels:
        try:
            parsed_dates.append(date.fromisoformat(label))
        except ValueError as exc:
            raise ValueError("sleeve return streams must use parseable YYYY-MM-DD daily labels") from exc
    for previous, current in zip(parsed_dates, parsed_dates[1:]):
        if current <= previous:
            raise ValueError("sleeve return streams must use strictly increasing UTC day labels")


def _estimate_covariance(
    history: list[list[float]],
    *,
    shrinkage: float,
    ridge_penalty: float,
) -> list[list[float]]:
    dimensions = len(history[0])
    if len(history) == 1:
        base = [
            [0.0 for _ in range(dimensions)]
            for _ in range(dimensions)
        ]
    else:
        means = _mean_vector(history)
        denominator = len(history) - 1
        base = []
        for row in range(dimensions):
            covariance_row = []
            for column in range(dimensions):
                covariance = sum(
                    (observation[row] - means[row]) * (observation[column] - means[column])
                    for observation in history
                ) / denominator
                covariance_row.append(covariance)
            base.append(covariance_row)
    diagonal = [
        [base[row][row] if row == column else 0.0 for column in range(dimensions)]
        for row in range(dimensions)
    ]
    shrunk = []
    for row in range(dimensions):
        shrunk_row = []
        for column in range(dimensions):
            shrunk_row.append(
                ((1.0 - shrinkage) * base[row][column]) + (shrinkage * diagonal[row][column])
            )
        shrunk.append(shrunk_row)
    for row in range(dimensions):
        shrunk[row][row] += ridge_penalty
    return shrunk


def _project_long_only_weights(raw_scores: list[float], *, max_weight: float) -> list[float]:
    positive = [max(score, 0.0) for score in raw_scores]
    if sum(positive) <= 1e-12:
        return [0.0 for _ in positive]

    weights = [0.0 for _ in positive]
    remaining_budget = 1.0
    active = [score > 0.0 for score in positive]
    while any(active) and remaining_budget > 1e-12:
        active_scores = [score for score, is_active in zip(positive, active) if is_active]
        total_score = float(sum(active_scores))
        if total_score <= 1e-12:
            break
        proposed = [(remaining_budget * score) / total_score for score in active_scores]
        if all(weight <= max_weight + 1e-12 for weight in proposed):
            active_indexes = [index for index, is_active in enumerate(active) if is_active]
            for offset, index in enumerate(active_indexes):
                weights[index] += proposed[offset]
            remaining_budget = 0.0
            break
        clipped_any = False
        active_indexes = [index for index, is_active in enumerate(active) if is_active]
        for local_index, proposed_weight in enumerate(proposed):
            if proposed_weight > max_weight + 1e-12:
                absolute_index = active_indexes[local_index]
                weights[absolute_index] = max_weight
                remaining_budget -= max_weight
                active[absolute_index] = False
                clipped_any = True
        if not clipped_any:
            for offset, index in enumerate(active_indexes):
                weights[index] += proposed[offset]
            remaining_budget = 0.0
            break
    return weights


def _mean_vector(history: list[list[float]]) -> list[float]:
    dimensions = len(history[0])
    return [
        sum(observation[index] for observation in history) / len(history)
        for index in range(dimensions)
    ]


def _solve_linear_system(matrix: list[list[float]], vector: list[float]) -> list[float] | None:
    size = len(vector)
    augmented = [
        [float(matrix[row][column]) for column in range(size)] + [float(vector[row])]
        for row in range(size)
    ]
    for pivot_index in range(size):
        pivot_row = max(
            range(pivot_index, size),
            key=lambda row_index: abs(augmented[row_index][pivot_index]),
        )
        if math.isclose(augmented[pivot_row][pivot_index], 0.0, abs_tol=1e-12):
            return None
        if pivot_row != pivot_index:
            augmented[pivot_index], augmented[pivot_row] = augmented[pivot_row], augmented[pivot_index]
        pivot_value = augmented[pivot_index][pivot_index]
        for column in range(pivot_index, size + 1):
            augmented[pivot_index][column] /= pivot_value
        for row in range(size):
            if row == pivot_index:
                continue
            factor = augmented[row][pivot_index]
            for column in range(pivot_index, size + 1):
                augmented[row][column] -= factor * augmented[pivot_index][column]
    return [augmented[row][size] for row in range(size)]


def _drift_holdings(target_weights: list[float], *, day_returns: list[float]) -> list[float]:
    gross_values = [
        weight * (1.0 + day_return)
        for weight, day_return in zip(target_weights, day_returns)
    ]
    cash_value = max(1.0 - sum(target_weights), 0.0)
    total_value = cash_value + sum(gross_values)
    if total_value <= 1e-12:
        return [0.0 for _ in target_weights]
    return [value / total_value for value in gross_values]


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
