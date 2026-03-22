"""Run analysis helpers for canonical performance reporting."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .run_history import load_run_manifest, load_run_state


@dataclass(frozen=True, slots=True)
class SeriesPoint:
    label: str
    value: float


@dataclass(frozen=True, slots=True)
class RunAnalysis:
    run_id: str
    mode: str | None
    product_id: str | None
    strategy_id: str | None
    started_at: str | None
    ended_at: str | None
    cycle_count: int
    starting_equity_usdc: float
    ending_equity_usdc: float
    realized_pnl_usdc: float
    unrealized_pnl_usdc: float
    total_pnl_usdc: float
    total_return_pct: float
    max_drawdown_usdc: float
    max_drawdown_pct: float
    turnover_usdc: float
    fill_count: int
    trade_count: int
    avg_abs_exposure_pct: float
    max_abs_exposure_pct: float
    decision_counts: dict[str, int]
    equity_series: tuple[SeriesPoint, ...]
    drawdown_series: tuple[SeriesPoint, ...]
    exposure_series: tuple[SeriesPoint, ...]


def analyze_run(run_dir: Path) -> RunAnalysis:
    manifest = _require_dict(load_run_manifest(run_dir), run_dir / "manifest.json")
    state = _require_dict(load_run_state(run_dir), run_dir / "state.json")
    config = _load_optional_json(run_dir / "config.json") or {}
    events = _load_optional_ndjson(run_dir / "events.ndjson")
    positions = _load_optional_ndjson(run_dir / "positions.ndjson")
    fills = _collect_fill_rows(run_dir, events)

    max_abs_notional = _resolve_max_abs_notional(config)
    configured_starting_equity = _resolve_starting_equity(
        config,
        ending_equity=_resolve_ending_equity(state),
        manifest=manifest,
        run_dir=run_dir,
    )
    equity_series = _build_equity_series(positions)
    equity_series = _prepend_configured_starting_equity(equity_series, configured_starting_equity)
    if not equity_series:
        ending_equity = _resolve_ending_equity(state)
        starting_equity = configured_starting_equity
        equity_series = [SeriesPoint(label="start", value=starting_equity)]
        if str(state.get("cycle_id") or "latest") != "start" or ending_equity != starting_equity:
            equity_series.append(
                SeriesPoint(label=str(state.get("cycle_id") or "latest"), value=ending_equity)
            )
    drawdown_series = _build_drawdown_series(equity_series)
    exposure_series = _build_exposure_series(positions, state, max_abs_notional)
    decision_counts = _count_decisions(events, state)

    starting_equity = equity_series[0].value
    ending_equity = equity_series[-1].value
    total_pnl = ending_equity - starting_equity
    total_return_pct = (total_pnl / starting_equity) if abs(starting_equity) > 1e-12 else 0.0
    max_drawdown_usdc = max((point.value for point in drawdown_series), default=0.0)
    max_drawdown_pct = _compute_max_drawdown_pct(equity_series)
    avg_abs_exposure_pct = (
        sum(point.value for point in exposure_series) / len(exposure_series)
        if exposure_series
        else 0.0
    )
    max_abs_exposure_pct = max((point.value for point in exposure_series), default=0.0)

    return RunAnalysis(
        run_id=run_dir.name,
        mode=_as_str(manifest.get("mode")),
        product_id=_as_str(manifest.get("product_id")),
        strategy_id=_resolve_strategy_id(manifest, config),
        started_at=_resolve_started_at(manifest, events),
        ended_at=_resolve_ended_at(state, events),
        cycle_count=_count_cycles(events, state, equity_series),
        starting_equity_usdc=starting_equity,
        ending_equity_usdc=ending_equity,
        realized_pnl_usdc=_resolve_realized_pnl(state),
        unrealized_pnl_usdc=_resolve_unrealized_pnl(state),
        total_pnl_usdc=total_pnl,
        total_return_pct=total_return_pct,
        max_drawdown_usdc=max_drawdown_usdc,
        max_drawdown_pct=max_drawdown_pct,
        turnover_usdc=sum(_fill_notional(fill) for fill in fills),
        fill_count=len(fills),
        trade_count=len(fills),
        avg_abs_exposure_pct=avg_abs_exposure_pct,
        max_abs_exposure_pct=max_abs_exposure_pct,
        decision_counts=decision_counts,
        equity_series=tuple(equity_series),
        drawdown_series=tuple(drawdown_series),
        exposure_series=tuple(exposure_series),
    )


def _load_optional_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return _require_dict(json.loads(path.read_text(encoding="utf-8")), path)


def _load_optional_ndjson(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        if not isinstance(payload, dict):
            raise ValueError(f"invalid ndjson row in {path}")
        rows.append(payload)
    return rows


def _resolve_max_abs_notional(config: dict[str, Any]) -> float:
    simulation = config.get("simulation")
    if isinstance(simulation, dict):
        starting_collateral = _as_float(simulation.get("starting_collateral_usdc"))
        max_leverage = _as_float(simulation.get("max_leverage"))
        if starting_collateral is not None and max_leverage is not None:
            return starting_collateral * max_leverage
    return 1.0


def _build_equity_series(positions: list[dict[str, Any]]) -> list[SeriesPoint]:
    points: list[SeriesPoint] = []
    for row in positions:
        position = row.get("position")
        if not isinstance(position, dict):
            continue
        label = str(row.get("cycle_id") or len(points))
        points.append(SeriesPoint(label=label, value=_position_equity(position)))
    return points


def _build_drawdown_series(equity_series: list[SeriesPoint]) -> list[SeriesPoint]:
    peak = float("-inf")
    points: list[SeriesPoint] = []
    for point in equity_series:
        peak = max(peak, point.value)
        points.append(SeriesPoint(label=point.label, value=max(peak - point.value, 0.0)))
    return points


def _prepend_configured_starting_equity(
    equity_series: list[SeriesPoint],
    starting_equity: float,
) -> list[SeriesPoint]:
    if not equity_series:
        return equity_series
    first_point = equity_series[0]
    if abs(first_point.value - starting_equity) <= 1e-12:
        return equity_series
    return [SeriesPoint(label="start", value=starting_equity), *equity_series]


def _compute_max_drawdown_pct(equity_series: list[SeriesPoint]) -> float:
    peak = float("-inf")
    max_drawdown_pct = 0.0
    for point in equity_series:
        peak = max(peak, point.value)
        if peak <= 0.0:
            continue
        max_drawdown_pct = max(max_drawdown_pct, max(peak - point.value, 0.0) / peak)
    return max_drawdown_pct


def _build_exposure_series(
    positions: list[dict[str, Any]],
    state: dict[str, Any],
    max_abs_notional: float,
) -> list[SeriesPoint]:
    points: list[SeriesPoint] = []
    for row in positions:
        position = row.get("position")
        if not isinstance(position, dict):
            continue
        quantity = _as_float(position.get("quantity")) or 0.0
        mark_price = _as_float(position.get("mark_price")) or 0.0
        label = str(row.get("cycle_id") or len(points))
        points.append(
            SeriesPoint(label=label, value=abs((quantity * mark_price) / max_abs_notional))
        )
    if points:
        return points
    current_position = _as_float(state.get("current_position"))
    if current_position is not None:
        return [SeriesPoint(label=str(state.get("cycle_id") or "latest"), value=abs(current_position))]
    return []


def _collect_fill_rows(run_dir: Path, events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    fills_path = run_dir / "fills.ndjson"
    if fills_path.exists():
        return _load_optional_ndjson(fills_path)

    rows: list[dict[str, Any]] = []
    for event in events:
        fills = event.get("fills")
        if isinstance(fills, list):
            rows.extend({"fill": fill} for fill in fills if isinstance(fill, dict))
    return rows


def _count_decisions(events: list[dict[str, Any]], state: dict[str, Any]) -> dict[str, int]:
    latest_reason_by_cycle: dict[str, str] = {}
    for event in events:
        cycle_id = _as_str(event.get("cycle_id"))
        if cycle_id is None:
            continue
        code = _extract_reason_code(event)
        if code is None:
            continue
        latest_reason_by_cycle[cycle_id] = code
    if latest_reason_by_cycle:
        counts: dict[str, int] = {}
        for code in latest_reason_by_cycle.values():
            counts[code] = counts.get(code, 0) + 1
        return counts
    code = _extract_reason_code(state)
    return {code: 1} if code is not None else {}


def _count_cycles(
    events: list[dict[str, Any]],
    state: dict[str, Any],
    equity_series: list[SeriesPoint],
) -> int:
    cycle_ids = {
        cycle_id
        for cycle_id in (_as_str(event.get("cycle_id")) for event in events)
        if cycle_id is not None
    }
    if cycle_ids:
        return len(cycle_ids)
    cycle_id = _as_str(state.get("cycle_id"))
    if cycle_id is not None:
        return 1
    return len(equity_series)


def _extract_reason_code(payload: dict[str, Any]) -> str | None:
    execution_summary = payload.get("execution_summary")
    if isinstance(execution_summary, dict):
        reason_code = _as_str(execution_summary.get("reason_code"))
        if reason_code:
            return reason_code
    no_trade_reason = payload.get("no_trade_reason")
    if isinstance(no_trade_reason, dict):
        return _as_str(no_trade_reason.get("code"))
    return None


def _resolve_strategy_id(manifest: dict[str, Any], config: dict[str, Any]) -> str | None:
    strategy_id = _as_str(manifest.get("strategy_id"))
    if strategy_id:
        return strategy_id
    strategy = config.get("strategy")
    if isinstance(strategy, dict):
        return _as_str(strategy.get("strategy_id"))
    return None


def _resolve_started_at(manifest: dict[str, Any], events: list[dict[str, Any]]) -> str | None:
    first_event = next((event for event in events if isinstance(event.get("timestamp"), str)), None)
    return _as_str((first_event or {}).get("timestamp")) or _as_str(manifest.get("created_at"))


def _resolve_ended_at(state: dict[str, Any], events: list[dict[str, Any]]) -> str | None:
    exchange_snapshot = state.get("exchange_snapshot")
    if isinstance(exchange_snapshot, dict) and isinstance(exchange_snapshot.get("as_of"), str):
        return _as_str(exchange_snapshot.get("as_of"))
    for event in reversed(events):
        timestamp = _as_str(event.get("timestamp"))
        if timestamp:
            return timestamp
    return None


def _resolve_realized_pnl(state: dict[str, Any]) -> float:
    position = state.get("position")
    if isinstance(position, dict):
        return _as_float(position.get("realized_pnl_usdc")) or 0.0
    return 0.0


def _resolve_unrealized_pnl(state: dict[str, Any]) -> float:
    position = state.get("position")
    if isinstance(position, dict):
        return _position_unrealized(position)
    exchange_snapshot = state.get("exchange_snapshot")
    if isinstance(exchange_snapshot, dict):
        summary = exchange_snapshot.get("summary")
        if isinstance(summary, dict):
            unrealized = summary.get("unrealized_pnl")
            if isinstance(unrealized, dict):
                return _as_float(unrealized.get("value")) or 0.0
    return 0.0


def _resolve_ending_equity(state: dict[str, Any]) -> float:
    position = state.get("position")
    if isinstance(position, dict):
        return _position_equity(position)
    exchange_snapshot = state.get("exchange_snapshot")
    if isinstance(exchange_snapshot, dict):
        summary = exchange_snapshot.get("summary")
        if isinstance(summary, dict):
            total_balance = summary.get("total_balance")
            if isinstance(total_balance, dict):
                value = _as_float(total_balance.get("value"))
                if value is not None:
                    return value
    equity = _as_float(state.get("equity_usdc"))
    return equity if equity is not None else 0.0


def _resolve_starting_equity(
    config: dict[str, Any],
    *,
    ending_equity: float,
    manifest: dict[str, Any],
    run_dir: Path,
) -> float:
    resumed_from_run_id = _as_str(manifest.get("resumed_from_run_id"))
    if resumed_from_run_id:
        resumed_state = _load_resumed_state(run_dir, resumed_from_run_id)
        if resumed_state is not None:
            return _resolve_ending_equity(resumed_state)
    simulation = config.get("simulation")
    if isinstance(simulation, dict):
        starting_collateral = _as_float(simulation.get("starting_collateral_usdc"))
        if starting_collateral is not None:
            return starting_collateral
    return ending_equity


def _load_resumed_state(run_dir: Path, resumed_from_run_id: str) -> dict[str, Any] | None:
    resumed_run_dir = run_dir.parent / resumed_from_run_id
    if not resumed_run_dir.exists():
        return None
    try:
        state = load_run_state(resumed_run_dir)
    except (FileNotFoundError, OSError, json.JSONDecodeError, ValueError):
        return None
    return state if isinstance(state, dict) else None


def _position_equity(position: dict[str, Any]) -> float:
    collateral = _as_float(position.get("collateral_usdc")) or 0.0
    realized = _as_float(position.get("realized_pnl_usdc")) or 0.0
    return collateral + realized + _position_unrealized(position)


def _position_unrealized(position: dict[str, Any]) -> float:
    quantity = _as_float(position.get("quantity"))
    entry_price = _as_float(position.get("entry_price"))
    mark_price = _as_float(position.get("mark_price"))
    if quantity is None or entry_price is None or mark_price is None:
        return 0.0
    return (mark_price - entry_price) * quantity


def _fill_notional(row: dict[str, Any]) -> float:
    fill = row.get("fill") if isinstance(row.get("fill"), dict) else row
    if not isinstance(fill, dict):
        return 0.0
    quantity = _as_float(fill.get("quantity"))
    if quantity is None:
        quantity = _as_float(fill.get("size"))
    price = _as_float(fill.get("price"))
    if quantity is None or price is None:
        return 0.0
    return abs(quantity * price)


def _as_float(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _as_str(value: Any) -> str | None:
    return value if isinstance(value, str) else None


def _require_dict(value: Any, path: Path) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"invalid json object in {path}")
    return value
