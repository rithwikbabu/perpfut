"""Portfolio-run artifacts and optimizer research execution."""

from __future__ import annotations

import json
import math
import statistics
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from .analysis import SeriesPoint
from .backtest_data import HistoricalDataset
from .config import AppConfig
from .portfolio_optimizer import (
    PortfolioOptimizationConfig,
    PortfolioOptimizationResult,
    load_sleeve_return_stream,
    optimize_strategy_portfolio,
)
from .sleeve_backtest import (
    AssetContributionSeries,
    StrategySleeveAnalysis,
    compute_strategy_instance_fingerprint,
    load_strategy_sleeve_analysis,
    run_strategy_sleeve,
)
from .strategy_instances import StrategyInstanceSpec

DAILY_PERIODS_PER_YEAR = 365.0


@dataclass(frozen=True, slots=True)
class StrategyContributionSeries:
    strategy_instance_id: str
    strategy_id: str
    sleeve_run_id: str
    total_gross_pnl_usdc: float
    daily_gross_pnl_series: tuple[SeriesPoint, ...]


@dataclass(frozen=True, slots=True)
class PortfolioRunAnalysis:
    run_id: str
    dataset_id: str
    dataset_fingerprint: str
    dataset_source: str
    dataset_version: str
    date_range_start: str
    date_range_end: str
    created_at: str
    starting_capital_usdc: float
    ending_equity_usdc: float
    total_pnl_usdc: float
    total_return_pct: float
    sharpe_ratio: float | None
    max_drawdown_usdc: float
    max_drawdown_pct: float
    total_turnover_usdc: float
    transaction_cost_total_usdc: float
    avg_gross_weight: float
    max_gross_weight: float
    strategy_instance_ids: tuple[str, ...]
    sleeve_run_ids: tuple[str, ...]
    equity_series: tuple[SeriesPoint, ...]
    drawdown_series: tuple[SeriesPoint, ...]
    gross_return_series: tuple[SeriesPoint, ...]
    net_return_series: tuple[SeriesPoint, ...]
    turnover_series_usdc: tuple[SeriesPoint, ...]
    transaction_cost_series_usdc: tuple[SeriesPoint, ...]
    gross_weight_series: tuple[SeriesPoint, ...]
    contribution_totals_usdc: dict[str, float]


@dataclass(frozen=True, slots=True)
class PortfolioRunResult:
    run_id: str
    run_dir: Path
    analysis: PortfolioRunAnalysis
    weight_history: tuple[dict[str, object], ...]
    diagnostics: tuple[dict[str, object], ...]
    contributions: tuple[StrategyContributionSeries, ...]
    sleeve_run_ids: tuple[str, ...]


def run_portfolio_research(
    *,
    base_runs_dir: Path,
    dataset: HistoricalDataset,
    config: AppConfig,
    strategy_instances: tuple[StrategyInstanceSpec, ...],
    optimizer_config: PortfolioOptimizationConfig,
    starting_capital_usdc: float,
) -> PortfolioRunResult:
    if not strategy_instances:
        raise ValueError("portfolio run requires at least one strategy instance")
    if starting_capital_usdc <= 0.0:
        raise ValueError("starting_capital_usdc must be positive")

    sleeve_payloads: list[dict[str, object]] = []
    sleeve_run_ids: list[str] = []
    sleeve_analyses: list[StrategySleeveAnalysis] = []
    for strategy_instance in strategy_instances:
        sleeve_run_id, sleeve_analysis = _load_or_run_sleeve(
            base_runs_dir=base_runs_dir,
            dataset=dataset,
            config=config,
            strategy_instance=strategy_instance,
        )
        sleeve_run_ids.append(sleeve_run_id)
        sleeve_analyses.append(sleeve_analysis)
        sleeve_payloads.append(
            {
                "strategy_instance_id": sleeve_analysis.strategy_instance_id,
                "strategy_id": sleeve_analysis.strategy_id,
                "dataset_id": sleeve_analysis.dataset_id,
                "config_fingerprint": sleeve_analysis.config_fingerprint,
                "daily_returns": [
                    {"label": point.label, "value": point.value}
                    for point in sleeve_analysis.daily_returns
                ],
            }
        )

    optimization = optimize_strategy_portfolio(
        [load_sleeve_return_stream(payload) for payload in sleeve_payloads],
        config=optimizer_config,
    )
    created_at = datetime.now(timezone.utc)
    run_id = created_at.strftime("%Y%m%dT%H%M%S%fZ")
    run_dir = base_runs_dir / "backtests" / "portfolio-runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=False)

    analysis, contributions, weight_rows, diagnostic_rows = build_portfolio_run_analysis(
        run_id=run_id,
        created_at=created_at,
        dataset=dataset,
        optimization=optimization,
        sleeves=sleeve_analyses,
        sleeve_run_ids=tuple(sleeve_run_ids),
        starting_capital_usdc=starting_capital_usdc,
        turnover_cost_bps=optimizer_config.turnover_cost_bps,
    )

    manifest = {
        "run_id": run_id,
        "created_at": created_at.isoformat(),
        "mode": "portfolio_research",
        "dataset_id": dataset.dataset_id,
        "dataset_fingerprint": dataset.fingerprint,
        "dataset_source": dataset.source,
        "dataset_version": dataset.version,
        "date_range_start": dataset.start.isoformat(),
        "date_range_end": dataset.end.isoformat(),
        "analysis_path": "analysis.json",
        "weights_path": "weights.ndjson",
        "diagnostics_path": "diagnostics.ndjson",
        "contributions_path": "contributions.json",
        "strategy_instances": [instance.to_payload() for instance in strategy_instances],
        "strategy_instance_ids": [instance.strategy_instance_id for instance in strategy_instances],
        "sleeve_run_ids": list(sleeve_run_ids),
    }
    config_payload = {
        "optimizer": asdict(optimizer_config),
        "starting_capital_usdc": starting_capital_usdc,
    }
    state_payload = {
        "run_id": run_id,
        "dataset_id": dataset.dataset_id,
        "latest_date": analysis.net_return_series[-1].label if analysis.net_return_series else None,
        "ending_equity_usdc": analysis.ending_equity_usdc,
        "total_pnl_usdc": analysis.total_pnl_usdc,
        "total_return_pct": analysis.total_return_pct,
        "sharpe_ratio": analysis.sharpe_ratio,
        "max_drawdown_usdc": analysis.max_drawdown_usdc,
        "total_turnover_usdc": analysis.total_turnover_usdc,
        "latest_weights": weight_rows[-1]["weights"] if weight_rows else {},
        "latest_cash_weight": weight_rows[-1]["cash_weight"] if weight_rows else 1.0,
        "latest_gross_weight": weight_rows[-1]["gross_weight"] if weight_rows else 0.0,
    }
    contributions_payload = {
        "items": [asdict(item) for item in contributions],
        "transaction_cost_total_usdc": analysis.transaction_cost_total_usdc,
        "transaction_cost_series_usdc": [asdict(point) for point in analysis.transaction_cost_series_usdc],
    }

    _write_json(run_dir / "manifest.json", manifest)
    _write_json(run_dir / "config.json", config_payload)
    _write_json(run_dir / "state.json", state_payload)
    _write_json(run_dir / "analysis.json", asdict(analysis))
    _write_json(run_dir / "contributions.json", contributions_payload)
    _write_ndjson(run_dir / "weights.ndjson", weight_rows)
    _write_ndjson(run_dir / "diagnostics.ndjson", diagnostic_rows)

    return PortfolioRunResult(
        run_id=run_id,
        run_dir=run_dir,
        analysis=analysis,
        weight_history=tuple(weight_rows),
        diagnostics=tuple(diagnostic_rows),
        contributions=contributions,
        sleeve_run_ids=tuple(sleeve_run_ids),
    )


def build_portfolio_run_analysis(
    *,
    run_id: str,
    created_at: datetime,
    dataset: HistoricalDataset,
    optimization: PortfolioOptimizationResult,
    sleeves: list[StrategySleeveAnalysis],
    sleeve_run_ids: tuple[str, ...],
    starting_capital_usdc: float,
    turnover_cost_bps: float,
) -> tuple[
    PortfolioRunAnalysis,
    tuple[StrategyContributionSeries, ...],
    list[dict[str, object]],
    list[dict[str, object]],
]:
    strategy_index = {
        sleeve.strategy_instance_id: index
        for index, sleeve in enumerate(sleeves)
    }
    strategy_id_by_instance = {
        sleeve.strategy_instance_id: sleeve.strategy_id
        for sleeve in sleeves
    }
    daily_returns_by_instance = {
        sleeve.strategy_instance_id: [point.value for point in sleeve.daily_returns]
        for sleeve in sleeves
    }

    previous_equity = starting_capital_usdc
    peak_equity = starting_capital_usdc
    equity_series: list[SeriesPoint] = []
    drawdown_series: list[SeriesPoint] = []
    turnover_series_usdc: list[SeriesPoint] = []
    transaction_cost_series_usdc: list[SeriesPoint] = []
    gross_weight_series: list[SeriesPoint] = []
    contribution_points: dict[str, list[SeriesPoint]] = {
        sleeve.strategy_instance_id: []
        for sleeve in sleeves
    }
    weight_rows: list[dict[str, object]] = []
    diagnostic_rows: list[dict[str, object]] = []

    for day_index, snapshot in enumerate(optimization.weight_history):
        date_label = snapshot.date
        turnover_usdc = snapshot.turnover * previous_equity
        transaction_cost_usdc = turnover_usdc * (turnover_cost_bps / 10_000.0)
        gross_weight_series.append(SeriesPoint(label=date_label, value=snapshot.gross_weight))
        turnover_series_usdc.append(SeriesPoint(label=date_label, value=turnover_usdc))
        transaction_cost_series_usdc.append(SeriesPoint(label=date_label, value=transaction_cost_usdc))

        for strategy_instance_id, weight in snapshot.weights.items():
            sleeve_return = daily_returns_by_instance[strategy_instance_id][day_index]
            contribution_points[strategy_instance_id].append(
                SeriesPoint(
                    label=date_label,
                    value=previous_equity * weight * sleeve_return,
                )
            )

        ending_equity = previous_equity * (1.0 + optimization.daily_net_returns[day_index].value)
        peak_equity = max(peak_equity, ending_equity)
        equity_series.append(SeriesPoint(label=date_label, value=ending_equity))
        drawdown_series.append(SeriesPoint(label=date_label, value=max(peak_equity - ending_equity, 0.0)))
        previous_equity = ending_equity

        weight_rows.append(
            {
                "date": snapshot.date,
                "weights": dict(snapshot.weights),
                "cash_weight": snapshot.cash_weight,
                "turnover": snapshot.turnover,
                "gross_weight": snapshot.gross_weight,
            }
        )

    for diagnostic in optimization.diagnostics:
        diagnostic_rows.append(
            {
                "date": diagnostic.date,
                "expected_returns": dict(diagnostic.expected_returns),
                "covariance_matrix": {
                    row_key: dict(row_values)
                    for row_key, row_values in diagnostic.covariance_matrix.items()
                },
                "constraint_status": diagnostic.constraint_status,
            }
        )

    sharpe_ratio = _compute_daily_sharpe([point.value for point in optimization.daily_net_returns])
    total_pnl_usdc = previous_equity - starting_capital_usdc
    total_return_pct = total_pnl_usdc / starting_capital_usdc
    max_drawdown_usdc = max((point.value for point in drawdown_series), default=0.0)
    max_drawdown_pct = _compute_max_drawdown_pct(equity_series, starting_equity=starting_capital_usdc)
    avg_gross_weight = (
        sum(point.value for point in gross_weight_series) / len(gross_weight_series)
        if gross_weight_series
        else 0.0
    )
    max_gross_weight = max((point.value for point in gross_weight_series), default=0.0)

    contribution_series = tuple(
        StrategyContributionSeries(
            strategy_instance_id=sleeve.strategy_instance_id,
            strategy_id=strategy_id_by_instance[sleeve.strategy_instance_id],
            sleeve_run_id=sleeve_run_ids[strategy_index[sleeve.strategy_instance_id]],
            total_gross_pnl_usdc=sum(
                point.value for point in contribution_points[sleeve.strategy_instance_id]
            ),
            daily_gross_pnl_series=tuple(contribution_points[sleeve.strategy_instance_id]),
        )
        for sleeve in sleeves
    )
    analysis = PortfolioRunAnalysis(
        run_id=run_id,
        dataset_id=dataset.dataset_id,
        dataset_fingerprint=dataset.fingerprint,
        dataset_source=dataset.source,
        dataset_version=dataset.version,
        date_range_start=dataset.start.isoformat(),
        date_range_end=dataset.end.isoformat(),
        created_at=created_at.isoformat(),
        starting_capital_usdc=starting_capital_usdc,
        ending_equity_usdc=previous_equity,
        total_pnl_usdc=total_pnl_usdc,
        total_return_pct=total_return_pct,
        sharpe_ratio=sharpe_ratio,
        max_drawdown_usdc=max_drawdown_usdc,
        max_drawdown_pct=max_drawdown_pct,
        total_turnover_usdc=sum(point.value for point in turnover_series_usdc),
        transaction_cost_total_usdc=sum(point.value for point in transaction_cost_series_usdc),
        avg_gross_weight=avg_gross_weight,
        max_gross_weight=max_gross_weight,
        strategy_instance_ids=tuple(sleeve.strategy_instance_id for sleeve in sleeves),
        sleeve_run_ids=sleeve_run_ids,
        equity_series=tuple(equity_series),
        drawdown_series=tuple(drawdown_series),
        gross_return_series=optimization.daily_gross_returns,
        net_return_series=optimization.daily_net_returns,
        turnover_series_usdc=tuple(turnover_series_usdc),
        transaction_cost_series_usdc=tuple(transaction_cost_series_usdc),
        gross_weight_series=tuple(gross_weight_series),
        contribution_totals_usdc={
            item.strategy_instance_id: item.total_gross_pnl_usdc
            for item in contribution_series
        },
    )
    return analysis, contribution_series, weight_rows, diagnostic_rows


def load_portfolio_run_detail(run_dir: Path) -> dict[str, object]:
    return {
        "manifest": _load_json(run_dir / "manifest.json"),
        "config": _load_json(run_dir / "config.json"),
        "state": _load_json(run_dir / "state.json"),
        "analysis": _load_json(run_dir / "analysis.json"),
        "weights": _load_ndjson(run_dir / "weights.ndjson"),
        "diagnostics": _load_ndjson(run_dir / "diagnostics.ndjson"),
        "contributions": _load_json(run_dir / "contributions.json"),
    }


def _load_or_run_sleeve(
    *,
    base_runs_dir: Path,
    dataset: HistoricalDataset,
    config: AppConfig,
    strategy_instance: StrategyInstanceSpec,
) -> tuple[str, StrategySleeveAnalysis]:
    config_fingerprint = compute_strategy_instance_fingerprint(
        config=config,
        strategy_instance=strategy_instance,
    )
    cached_run_dir = _find_cached_sleeve_run(
        base_runs_dir=base_runs_dir,
        dataset_id=dataset.dataset_id,
        config_fingerprint=config_fingerprint,
    )
    if cached_run_dir is not None:
        return cached_run_dir.name, _coerce_sleeve_analysis(load_strategy_sleeve_analysis(cached_run_dir))

    result = run_strategy_sleeve(
        base_runs_dir=base_runs_dir,
        dataset=dataset,
        config=config,
        strategy_instance=strategy_instance,
    )
    return result.run_id, result.sleeve_analysis


def _find_cached_sleeve_run(
    *,
    base_runs_dir: Path,
    dataset_id: str,
    config_fingerprint: str,
) -> Path | None:
    sleeves_dir = base_runs_dir / "backtests" / "sleeves"
    if not sleeves_dir.exists():
        return None
    for run_dir in sorted((path for path in sleeves_dir.iterdir() if path.is_dir()), reverse=True):
        manifest_path = run_dir / "manifest.json"
        if not manifest_path.exists() or not (run_dir / "sleeve_analysis.json").exists():
            continue
        try:
            manifest = _load_json(manifest_path)
        except (OSError, ValueError, json.JSONDecodeError):
            continue
        if (
            manifest.get("dataset_id") == dataset_id
            and manifest.get("config_fingerprint") == config_fingerprint
        ):
            return run_dir
    return None


def _coerce_sleeve_analysis(payload: dict[str, object]) -> StrategySleeveAnalysis:
    asset_contributions_payload = payload.get("asset_contributions")
    if not isinstance(asset_contributions_payload, list):
        raise ValueError("invalid sleeve analysis payload: asset_contributions")
    return StrategySleeveAnalysis(
        run_id=str(payload["run_id"]),
        dataset_id=str(payload["dataset_id"]),
        dataset_fingerprint=str(payload["dataset_fingerprint"]),
        dataset_source=str(payload["dataset_source"]),
        dataset_version=str(payload["dataset_version"]),
        strategy_instance_id=str(payload["strategy_instance_id"]),
        strategy_id=str(payload["strategy_id"]),
        config_fingerprint=str(payload["config_fingerprint"]),
        date_range_start=str(payload["date_range_start"]),
        date_range_end=str(payload["date_range_end"]),
        total_pnl_usdc=float(payload["total_pnl_usdc"]),
        total_return_pct=float(payload["total_return_pct"]),
        max_drawdown_usdc=float(payload["max_drawdown_usdc"]),
        max_drawdown_pct=float(payload["max_drawdown_pct"]),
        daily_returns=tuple(_parse_series_point(item) for item in _require_list(payload, "daily_returns")),
        daily_turnover_usdc=tuple(_parse_series_point(item) for item in _require_list(payload, "daily_turnover_usdc")),
        daily_avg_abs_exposure_pct=tuple(
            _parse_series_point(item) for item in _require_list(payload, "daily_avg_abs_exposure_pct")
        ),
        daily_drawdown_usdc=tuple(_parse_series_point(item) for item in _require_list(payload, "daily_drawdown_usdc")),
        asset_contributions=tuple(
            AssetContributionSeries(
                product_id=str(item["product_id"]),
                total_pnl_usdc=float(item["total_pnl_usdc"]),
                daily_pnl_series=tuple(
                    _parse_series_point(point)
                    for point in _require_list(item, "daily_pnl_series")
                ),
            )
            for item in asset_contributions_payload
            if isinstance(item, dict)
        ),
    )


def _parse_series_point(payload: object) -> SeriesPoint:
    if not isinstance(payload, dict):
        raise ValueError("invalid series point payload")
    return SeriesPoint(label=str(payload["label"]), value=float(payload["value"]))


def _require_list(payload: dict[str, object], key: str) -> list[object]:
    value = payload.get(key)
    if not isinstance(value, list):
        raise ValueError(f"invalid sleeve analysis payload: {key}")
    return value


def _compute_daily_sharpe(returns: list[float]) -> float | None:
    if len(returns) < 2:
        return None
    volatility = statistics.stdev(returns)
    if math.isclose(volatility, 0.0, abs_tol=1e-12):
        return None
    return statistics.mean(returns) / volatility * math.sqrt(DAILY_PERIODS_PER_YEAR)


def _compute_max_drawdown_pct(
    equity_series: list[SeriesPoint],
    *,
    starting_equity: float,
) -> float:
    peak = starting_equity
    max_drawdown_pct = 0.0
    for point in equity_series:
        peak = max(peak, point.value)
        if peak <= 0.0:
            continue
        max_drawdown_pct = max(max_drawdown_pct, max(peak - point.value, 0.0) / peak)
    return max_drawdown_pct


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_ndjson(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text(
        "\n".join(json.dumps(row, sort_keys=True) for row in rows) + ("\n" if rows else ""),
        encoding="utf-8",
    )


def _load_json(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"invalid json object in {path}")
    return payload


def _load_ndjson(path: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        if not isinstance(payload, dict):
            raise ValueError(f"invalid ndjson row in {path}")
        rows.append(payload)
    return rows
