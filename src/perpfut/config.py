"""Configuration loading and runtime overrides."""

from __future__ import annotations

import os
from dataclasses import dataclass, field, replace
from pathlib import Path

from .domain import Mode


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    return int(value) if value is not None else default


def _env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    return float(value) if value is not None else default


def _env_mode(name: str, default: Mode) -> Mode:
    value = os.getenv(name)
    return Mode(value.lower()) if value is not None else default


@dataclass(frozen=True, slots=True)
class StrategyConfig:
    strategy_id: str = "momentum"
    lookback_candles: int = 20
    signal_scale: float = 35.0


@dataclass(frozen=True, slots=True)
class RiskConfig:
    max_abs_position: float = 0.5
    max_gross_position: float = 1.0
    rebalance_threshold: float = 0.10
    min_trade_notional_usdc: float = 10.0
    max_daily_drawdown_usdc: float = 250.0


@dataclass(frozen=True, slots=True)
class SimulationConfig:
    starting_collateral_usdc: float = 10_000.0
    max_leverage: float = 2.0
    slippage_bps: float = 3.0


@dataclass(frozen=True, slots=True)
class RuntimeConfig:
    mode: Mode = Mode.PAPER
    product_id: str = "BTC-PERP-INTX"
    interval_seconds: int = 60
    iterations: int = 3
    runs_dir: Path = Path("runs")


@dataclass(frozen=True, slots=True)
class CoinbaseConfig:
    api_key_id: str | None = None
    api_key_secret: str | None = None
    intx_portfolio_uuid: str | None = None


@dataclass(frozen=True, slots=True)
class AppConfig:
    runtime: RuntimeConfig = field(default_factory=RuntimeConfig)
    strategy: StrategyConfig = field(default_factory=StrategyConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)
    simulation: SimulationConfig = field(default_factory=SimulationConfig)
    coinbase: CoinbaseConfig = field(default_factory=CoinbaseConfig)

    @property
    def max_abs_notional_usdc(self) -> float:
        return self.simulation.starting_collateral_usdc * self.simulation.max_leverage

    @classmethod
    def from_env(cls) -> "AppConfig":
        return cls(
            runtime=RuntimeConfig(
                mode=_env_mode("MODE", Mode.PAPER),
                product_id=os.getenv("PRODUCT_ID", "BTC-PERP-INTX"),
                interval_seconds=_env_int("INTERVAL_SECONDS", 60),
                iterations=_env_int("ITERATIONS", 3),
                runs_dir=Path(os.getenv("RUNS_DIR", "runs")),
            ),
            strategy=StrategyConfig(
                strategy_id=os.getenv("STRATEGY_ID", "momentum"),
                lookback_candles=_env_int("LOOKBACK_CANDLES", 20),
                signal_scale=_env_float("SIGNAL_SCALE", 35.0),
            ),
            risk=RiskConfig(
                max_abs_position=_env_float("MAX_ABS_POSITION", 0.5),
                max_gross_position=_env_float("MAX_GROSS_POSITION", 1.0),
                rebalance_threshold=_env_float("REBALANCE_THRESHOLD", 0.10),
                min_trade_notional_usdc=_env_float("MIN_TRADE_NOTIONAL_USDC", 10.0),
                max_daily_drawdown_usdc=_env_float("MAX_DAILY_DRAWDOWN_USDC", 250.0),
            ),
            simulation=SimulationConfig(
                starting_collateral_usdc=_env_float("STARTING_COLLATERAL_USDC", 10_000.0),
                max_leverage=_env_float("MAX_LEVERAGE", 2.0),
                slippage_bps=_env_float("SLIPPAGE_BPS", 3.0),
            ),
            coinbase=CoinbaseConfig(
                api_key_id=os.getenv("COINBASE_API_KEY_ID"),
                api_key_secret=os.getenv("COINBASE_API_KEY_SECRET"),
                intx_portfolio_uuid=os.getenv("COINBASE_INTX_PORTFOLIO_UUID"),
            ),
        )

    def with_overrides(
        self,
        *,
        mode: Mode | None = None,
        product_id: str | None = None,
        interval_seconds: int | None = None,
        iterations: int | None = None,
        runs_dir: Path | None = None,
    ) -> "AppConfig":
        runtime = replace(
            self.runtime,
            mode=mode if mode is not None else self.runtime.mode,
            product_id=product_id if product_id is not None else self.runtime.product_id,
            interval_seconds=(
                interval_seconds if interval_seconds is not None else self.runtime.interval_seconds
            ),
            iterations=iterations if iterations is not None else self.runtime.iterations,
            runs_dir=runs_dir if runs_dir is not None else self.runtime.runs_dir,
        )
        return replace(self, runtime=runtime)
