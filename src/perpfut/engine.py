"""Main execution loop orchestration."""

from __future__ import annotations

import time
from dataclasses import replace
from typing import Protocol

from .config import AppConfig
from .domain import CycleResult, MarketSnapshot, Mode, OrderIntent, PositionState
from .risk import clip_target_position, should_halt_for_drawdown, should_rebalance
from .signal_momentum import compute_signal
from .sim import apply_fill, simulate_market_fill
from .telemetry import ArtifactStore


class MarketDataClient(Protocol):
    def fetch_market(self, product_id: str, *, candle_limit: int) -> MarketSnapshot:
        ...


class PaperEngine:
    """Coordinates the paper-trading loop."""

    def __init__(
        self,
        *,
        config: AppConfig,
        market_data: MarketDataClient,
        artifact_store: ArtifactStore,
    ):
        self.config = config
        self.market_data = market_data
        self.artifact_store = artifact_store
        self.state = PositionState(
            collateral_usdc=config.simulation.starting_collateral_usdc,
        )

    def run(self) -> list[CycleResult]:
        results = []
        for cycle_number in range(1, self.config.runtime.iterations + 1):
            result = self.run_cycle(cycle_number)
            results.append(result)
            if cycle_number < self.config.runtime.iterations:
                time.sleep(self.config.runtime.interval_seconds)
        return results

    def run_cycle(self, cycle_number: int) -> CycleResult:
        market = self.market_data.fetch_market(
            self.config.runtime.product_id,
            candle_limit=self.config.strategy.lookback_candles,
        )
        marked_state = replace(self.state, mark_price=market.mid_price)
        signal = compute_signal(
            market.candles,
            lookback_candles=self.config.strategy.lookback_candles,
            signal_scale=self.config.strategy.signal_scale,
        )
        target_position = clip_target_position(
            signal.target_position,
            max_abs_position=self.config.risk.max_abs_position,
        )
        current_position = marked_state.position_notional_usdc / self.config.max_abs_notional_usdc
        target_notional_usdc = target_position * self.config.max_abs_notional_usdc
        delta_notional_usdc = target_notional_usdc - marked_state.position_notional_usdc

        order_intent = None
        fill = None
        halted = should_halt_for_drawdown(
            starting_collateral_usdc=self.config.simulation.starting_collateral_usdc,
            equity_usdc=marked_state.equity_usdc,
            max_daily_drawdown_usdc=self.config.risk.max_daily_drawdown_usdc,
        )
        if not halted:
            order_intent = self._build_order_intent(
                market=market,
                target_position=target_position,
                current_position=current_position,
                current_notional_usdc=marked_state.position_notional_usdc,
                target_notional_usdc=target_notional_usdc,
                delta_notional_usdc=delta_notional_usdc,
            )

        if order_intent is not None:
            fill = simulate_market_fill(
                order_intent,
                mark_price=market.mid_price,
                slippage_bps=self.config.simulation.slippage_bps,
                timestamp=market.as_of,
            )
            marked_state = apply_fill(marked_state, fill)
            marked_state = replace(marked_state, mark_price=market.mid_price)

        cycle_result = CycleResult(
            cycle_id=f"cycle-{cycle_number:04d}",
            mode=Mode.PAPER,
            market=market,
            signal=replace(signal, target_position=target_position),
            state=marked_state,
            order_intent=order_intent,
            fill=fill,
        )
        self.state = marked_state
        self.artifact_store.record_cycle(cycle_result)
        return cycle_result

    def _build_order_intent(
        self,
        *,
        market: MarketSnapshot,
        target_position: float,
        current_position: float,
        current_notional_usdc: float,
        target_notional_usdc: float,
        delta_notional_usdc: float,
    ) -> OrderIntent | None:
        if not should_rebalance(
            target_position=target_position,
            current_position=current_position,
            delta_notional_usdc=delta_notional_usdc,
            rebalance_threshold=self.config.risk.rebalance_threshold,
            min_trade_notional_usdc=self.config.risk.min_trade_notional_usdc,
        ):
            return None

        side = "BUY" if delta_notional_usdc > 0.0 else "SELL"
        quantity = abs(delta_notional_usdc) / market.mid_price
        return OrderIntent(
            product_id=market.product_id,
            side=side,
            quantity=quantity,
            target_position=target_position,
            target_notional_usdc=target_notional_usdc,
            current_notional_usdc=current_notional_usdc,
            reason="rebalance_to_target",
        )
