"""Offline experiment replay helpers."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .analysis import analyze_run
from .config import AppConfig, RiskConfig, RuntimeConfig, SimulationConfig, StrategyConfig
from .domain import Candle, MarketSnapshot, Mode
from .engine import PaperEngine
from .run_history import load_run_manifest
from .strategy_registry import validate_strategy_id
from .telemetry import ArtifactStore


@dataclass(frozen=True, slots=True)
class ExperimentComparisonEntry:
    rank: int
    run_id: str
    strategy_id: str | None
    strategy_params: dict[str, Any]
    total_pnl_usdc: float
    total_return_pct: float
    max_drawdown_usdc: float
    max_drawdown_pct: float
    turnover_usdc: float
    fill_count: int
    avg_abs_exposure_pct: float
    max_abs_exposure_pct: float
    decision_counts: dict[str, int]


@dataclass(frozen=True, slots=True)
class ExperimentBaselineSummary:
    run_id: str
    strategy_id: str | None
    total_pnl_usdc: float
    total_return_pct: float
    max_drawdown_usdc: float
    max_drawdown_pct: float
    turnover_usdc: float
    fill_count: int
    avg_abs_exposure_pct: float
    max_abs_exposure_pct: float
    decision_counts: dict[str, int]


@dataclass(frozen=True, slots=True)
class ExperimentComparisonReport:
    source_run_id: str
    ranking_policy: str
    experiments_count: int
    baseline: ExperimentBaselineSummary | None
    items: tuple[ExperimentComparisonEntry, ...]


class ReplayMarketDataClient:
    """Feeds pre-recorded market snapshots back into the paper engine."""

    def __init__(self, snapshots: list[MarketSnapshot]):
        if not snapshots:
            raise ValueError("source run does not contain replayable market snapshots")
        self._snapshots = snapshots
        self._index = 0

    def fetch_market(self, product_id: str, *, candle_limit: int) -> MarketSnapshot:
        del candle_limit
        if self._index >= len(self._snapshots):
            raise RuntimeError("replay market snapshot sequence exhausted")
        snapshot = self._snapshots[self._index]
        self._index += 1
        if snapshot.product_id != product_id:
            raise ValueError(
                f"replay snapshot product_id '{snapshot.product_id}' does not match requested product '{product_id}'"
            )
        return snapshot


def run_experiment(
    *,
    base_runs_dir: Path,
    source_run_id: str,
    strategy_id: str,
    lookback_candles: int | None = None,
    signal_scale: float | None = None,
) -> ArtifactStore:
    validate_strategy_id(strategy_id)
    source_run_dir = base_runs_dir / source_run_id
    if not source_run_dir.exists():
        raise FileNotFoundError(f"source run not found: {source_run_id}")

    source_manifest = _require_dict(load_run_manifest(source_run_dir), source_run_dir / "manifest.json")
    source_config = _load_optional_dict(source_run_dir / "config.json") or {}
    replay_snapshots = load_replay_snapshots(source_run_dir)
    if not replay_snapshots:
        raise ValueError(f"source run has no replayable market snapshots: {source_run_id}")

    config = build_experiment_config(
        source_manifest=source_manifest,
        source_config=source_config,
        base_runs_dir=base_runs_dir,
        strategy_id=strategy_id,
        lookback_candles=lookback_candles,
        signal_scale=signal_scale,
        replay_iterations=len(replay_snapshots),
    )
    artifact_store = ArtifactStore.create(config.runtime.runs_dir)
    artifact_store.write_metadata(
        config,
        extra_manifest={
            "analysis_path": "analysis.json",
            "generated_at": datetime.now(timezone.utc),
            "source_run_id": source_run_id,
            "strategy_params": {
                "lookback_candles": config.strategy.lookback_candles,
                "signal_scale": config.strategy.signal_scale,
            },
        },
    )
    engine = PaperEngine(
        config=config,
        market_data=ReplayMarketDataClient(replay_snapshots),
        artifact_store=artifact_store,
    )
    engine.run()
    analysis = analyze_run(artifact_store.run_dir)
    (artifact_store.run_dir / "analysis.json").write_text(
        json.dumps(asdict(analysis), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return artifact_store


def load_replay_snapshots(source_run_dir: Path) -> list[MarketSnapshot]:
    events_path = source_run_dir / "events.ndjson"
    if not events_path.exists():
        return []
    snapshots: list[MarketSnapshot] = []
    for payload in _load_ndjson(events_path):
        if payload.get("event_type") != "cycle":
            continue
        market = payload.get("market")
        if not isinstance(market, dict):
            continue
        snapshots.append(_parse_market_snapshot(market))
    return snapshots


def compare_experiments(*, base_runs_dir: Path, source_run_id: str) -> ExperimentComparisonReport:
    source_run_dir = base_runs_dir / source_run_id
    if not source_run_dir.exists():
        raise FileNotFoundError(f"source run not found: {source_run_id}")

    entries: list[ExperimentComparisonEntry] = []
    for run_dir in _list_experiment_runs(base_runs_dir / "experiments"):
        manifest = _load_optional_dict(run_dir / "manifest.json")
        if not isinstance(manifest, dict):
            continue
        if _as_str(manifest.get("source_run_id")) != source_run_id:
            continue
        analysis = _load_analysis_payload(run_dir)
        entries.append(
            ExperimentComparisonEntry(
                rank=0,
                run_id=run_dir.name,
                strategy_id=_as_str(analysis.get("strategy_id")),
                strategy_params=_coerce_dict(manifest.get("strategy_params")),
                total_pnl_usdc=_analysis_float(analysis, "total_pnl_usdc"),
                total_return_pct=_analysis_float(analysis, "total_return_pct"),
                max_drawdown_usdc=_analysis_float(analysis, "max_drawdown_usdc"),
                max_drawdown_pct=_analysis_float(analysis, "max_drawdown_pct"),
                turnover_usdc=_analysis_float(analysis, "turnover_usdc"),
                fill_count=_analysis_int(analysis, "fill_count"),
                avg_abs_exposure_pct=_analysis_float(analysis, "avg_abs_exposure_pct"),
                max_abs_exposure_pct=_analysis_float(analysis, "max_abs_exposure_pct"),
                decision_counts=_coerce_int_dict(analysis.get("decision_counts")),
            )
        )

    if not entries:
        raise ValueError(f"no experiments found for source run: {source_run_id}")

    sorted_entries = sorted(
        entries,
        key=lambda item: (
            -item.total_return_pct,
            item.max_drawdown_pct,
            item.turnover_usdc,
            item.fill_count,
            item.run_id,
        ),
    )
    ranked_entries = tuple(
        replace(entry, rank=index)
        for index, entry in enumerate(sorted_entries, start=1)
    )
    baseline = _load_baseline_summary(source_run_dir)
    return ExperimentComparisonReport(
        source_run_id=source_run_id,
        ranking_policy=(
            "rank by total_return_pct desc, max_drawdown_pct asc, "
            "turnover_usdc asc, fill_count asc, run_id asc"
        ),
        experiments_count=len(ranked_entries),
        baseline=baseline,
        items=ranked_entries,
    )


def build_experiment_config(
    *,
    source_manifest: dict[str, Any],
    source_config: dict[str, Any],
    base_runs_dir: Path,
    strategy_id: str,
    lookback_candles: int | None,
    signal_scale: float | None,
    replay_iterations: int,
) -> AppConfig:
    base_config = AppConfig.from_env()
    product_id = _as_str(source_manifest.get("product_id")) or base_config.runtime.product_id

    runtime = RuntimeConfig(
        mode=Mode.PAPER,
        product_id=product_id,
        interval_seconds=0,
        iterations=replay_iterations,
        runs_dir=base_runs_dir / "experiments",
    )
    strategy = _build_strategy_config(
        source_config=source_config,
        base_config=base_config,
        strategy_id=strategy_id,
        lookback_candles=lookback_candles,
        signal_scale=signal_scale,
    )
    risk = _build_risk_config(source_config=source_config, base_config=base_config)
    simulation = _build_simulation_config(source_config=source_config, base_config=base_config)
    return AppConfig(
        runtime=runtime,
        strategy=strategy,
        risk=risk,
        simulation=simulation,
        coinbase=base_config.coinbase,
    )


def _build_strategy_config(
    *,
    source_config: dict[str, Any],
    base_config: AppConfig,
    strategy_id: str,
    lookback_candles: int | None,
    signal_scale: float | None,
) -> StrategyConfig:
    strategy = source_config.get("strategy")
    if not isinstance(strategy, dict):
        return replace(
            base_config.strategy,
            strategy_id=strategy_id,
            lookback_candles=lookback_candles
            if lookback_candles is not None
            else base_config.strategy.lookback_candles,
            signal_scale=signal_scale if signal_scale is not None else base_config.strategy.signal_scale,
        )
    return StrategyConfig(
        strategy_id=strategy_id,
        lookback_candles=int(strategy.get("lookback_candles", base_config.strategy.lookback_candles))
        if lookback_candles is None
        else lookback_candles,
        signal_scale=float(strategy.get("signal_scale", base_config.strategy.signal_scale))
        if signal_scale is None
        else signal_scale,
    )


def _build_risk_config(*, source_config: dict[str, Any], base_config: AppConfig) -> RiskConfig:
    risk = source_config.get("risk")
    if not isinstance(risk, dict):
        return base_config.risk
    return RiskConfig(
        max_abs_position=float(risk.get("max_abs_position", base_config.risk.max_abs_position)),
        rebalance_threshold=float(
            risk.get("rebalance_threshold", base_config.risk.rebalance_threshold)
        ),
        min_trade_notional_usdc=float(
            risk.get("min_trade_notional_usdc", base_config.risk.min_trade_notional_usdc)
        ),
        max_daily_drawdown_usdc=float(
            risk.get("max_daily_drawdown_usdc", base_config.risk.max_daily_drawdown_usdc)
        ),
    )


def _build_simulation_config(
    *,
    source_config: dict[str, Any],
    base_config: AppConfig,
) -> SimulationConfig:
    simulation = source_config.get("simulation")
    if not isinstance(simulation, dict):
        return base_config.simulation
    return SimulationConfig(
        starting_collateral_usdc=float(
            simulation.get(
                "starting_collateral_usdc",
                base_config.simulation.starting_collateral_usdc,
            )
        ),
        max_leverage=float(simulation.get("max_leverage", base_config.simulation.max_leverage)),
        slippage_bps=float(simulation.get("slippage_bps", base_config.simulation.slippage_bps)),
    )


def _load_optional_dict(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return _require_dict(json.loads(path.read_text(encoding="utf-8")), path)


def _load_ndjson(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        if not isinstance(payload, dict):
            raise ValueError(f"invalid ndjson row in {path}")
        rows.append(payload)
    return rows


def _list_experiment_runs(experiments_dir: Path) -> list[Path]:
    if not experiments_dir.exists():
        return []
    return sorted((path for path in experiments_dir.iterdir() if path.is_dir()), reverse=True)


def _load_analysis_payload(run_dir: Path) -> dict[str, Any]:
    analysis_path = run_dir / "analysis.json"
    if analysis_path.exists():
        payload = json.loads(analysis_path.read_text(encoding="utf-8"))
        return _require_dict(payload, analysis_path)
    return asdict(analyze_run(run_dir))


def _load_baseline_summary(source_run_dir: Path) -> ExperimentBaselineSummary | None:
    try:
        analysis = analyze_run(source_run_dir)
    except (FileNotFoundError, OSError, json.JSONDecodeError, ValueError):
        return None
    return ExperimentBaselineSummary(
        run_id=analysis.run_id,
        strategy_id=analysis.strategy_id,
        total_pnl_usdc=analysis.total_pnl_usdc,
        total_return_pct=analysis.total_return_pct,
        max_drawdown_usdc=analysis.max_drawdown_usdc,
        max_drawdown_pct=analysis.max_drawdown_pct,
        turnover_usdc=analysis.turnover_usdc,
        fill_count=analysis.fill_count,
        avg_abs_exposure_pct=analysis.avg_abs_exposure_pct,
        max_abs_exposure_pct=analysis.max_abs_exposure_pct,
        decision_counts=analysis.decision_counts,
    )


def _parse_market_snapshot(payload: dict[str, Any]) -> MarketSnapshot:
    candles_payload = payload.get("candles")
    candles: list[Candle] = []
    if isinstance(candles_payload, list):
        for item in candles_payload:
            if not isinstance(item, dict):
                raise ValueError("market snapshot candle row must be an object")
            candles.append(
                Candle(
                    start=_parse_datetime(item.get("start")),
                    low=_as_float(item.get("low")),
                    high=_as_float(item.get("high")),
                    open=_as_float(item.get("open")),
                    close=_as_float(item.get("close")),
                    volume=_as_float(item.get("volume")),
                )
            )
    return MarketSnapshot(
        product_id=_as_str(payload.get("product_id")) or "",
        as_of=_parse_datetime(payload.get("as_of")),
        last_price=_as_float(payload.get("last_price")),
        best_bid=_as_float(payload.get("best_bid")),
        best_ask=_as_float(payload.get("best_ask")),
        candles=tuple(candles),
    )


def _parse_datetime(value: Any) -> datetime:
    text = _as_str(value)
    if text is None:
        raise ValueError("timestamp is required")
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def _as_str(value: Any) -> str | None:
    return value if isinstance(value, str) else None


def _analysis_float(payload: dict[str, Any], key: str) -> float:
    value = payload.get(key)
    if isinstance(value, (int, float)):
        return float(value)
    raise ValueError(f"invalid analysis payload missing numeric field '{key}'")


def _analysis_int(payload: dict[str, Any], key: str) -> int:
    value = payload.get(key)
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    raise ValueError(f"invalid analysis payload missing integer field '{key}'")


def _coerce_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _coerce_int_dict(value: Any) -> dict[str, int]:
    if not isinstance(value, dict):
        return {}
    items: dict[str, int] = {}
    for key, item in value.items():
        if isinstance(key, str) and isinstance(item, int):
            items[key] = item
    return items


def _as_float(value: Any) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        return float(value)
    raise ValueError(f"expected numeric value, got {value!r}")


def _require_dict(payload: Any, path: Path) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError(f"expected object payload in {path}")
    return payload
