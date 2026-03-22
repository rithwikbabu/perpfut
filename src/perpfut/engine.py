"""Main execution loop orchestration."""

from __future__ import annotations

import time
from dataclasses import replace
from typing import Protocol

from .config import AppConfig
from .domain import (
    CycleResult,
    ExecutionSummary,
    MarketSnapshot,
    Mode,
    NoTradeReason,
    OrderIntent,
    OrderPlan,
    PositionState,
    RiskDecision,
)
from .risk import (
    classify_rebalance_skip_reason,
    clip_target_position,
    should_halt_for_drawdown,
)
from .sim import apply_fill, simulate_market_fill
from .strategy_registry import compute_strategy_signal
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
        signal = compute_strategy_signal(
            market.candles,
            self.config.strategy,
        )
        raw_target_position = signal.target_position
        target_position = clip_target_position(
            raw_target_position,
            max_abs_position=self.config.risk.max_abs_position,
        )
        current_position = marked_state.position_notional_usdc / self.config.max_abs_notional_usdc
        target_notional_usdc = target_position * self.config.max_abs_notional_usdc
        delta_notional_usdc = target_notional_usdc - marked_state.position_notional_usdc

        order_plan = OrderPlan(order_intent=None, no_trade_reason=None)
        fill = None
        halted = should_halt_for_drawdown(
            starting_collateral_usdc=self.config.simulation.starting_collateral_usdc,
            equity_usdc=marked_state.equity_usdc,
            max_daily_drawdown_usdc=self.config.risk.max_daily_drawdown_usdc,
        )
        risk_decision = build_risk_decision(
            target_before_risk=raw_target_position,
            target_after_risk=target_position,
            current_position=current_position,
            target_notional_usdc=target_notional_usdc,
            current_notional_usdc=marked_state.position_notional_usdc,
            delta_notional_usdc=delta_notional_usdc,
            config=self.config,
            halted=halted,
            rebalance_eligible=False,
        )
        if halted:
            order_plan = OrderPlan(
                order_intent=None,
                no_trade_reason=build_halt_no_trade_reason(),
            )
        else:
            order_plan = build_order_plan(
                market=market,
                target_position=target_position,
                current_position=current_position,
                current_notional_usdc=marked_state.position_notional_usdc,
                target_notional_usdc=target_notional_usdc,
                delta_notional_usdc=delta_notional_usdc,
                config=self.config,
            )
            risk_decision = build_risk_decision(
                target_before_risk=raw_target_position,
                target_after_risk=target_position,
                current_position=current_position,
                target_notional_usdc=target_notional_usdc,
                current_notional_usdc=marked_state.position_notional_usdc,
                delta_notional_usdc=delta_notional_usdc,
                config=self.config,
                halted=False,
                rebalance_eligible=order_plan.order_intent is not None,
            )

        if order_plan.order_intent is not None:
            fill = simulate_market_fill(
                order_plan.order_intent,
                mark_price=market.mid_price,
                slippage_bps=self.config.simulation.slippage_bps,
                timestamp=market.as_of,
            )
            marked_state = apply_fill(marked_state, fill)
            marked_state = replace(marked_state, mark_price=market.mid_price)
        execution_summary = build_execution_summary(
            fill=fill,
            no_trade_reason=order_plan.no_trade_reason,
        )

        cycle_result = CycleResult(
            cycle_id=f"cycle-{cycle_number:04d}",
            mode=Mode.PAPER,
            market=market,
            signal=replace(signal, target_position=target_position),
            risk_decision=risk_decision,
            execution_summary=execution_summary,
            no_trade_reason=order_plan.no_trade_reason,
            state=marked_state,
            order_intent=order_plan.order_intent,
            fill=fill,
        )
        self.state = marked_state
        self.artifact_store.record_cycle(cycle_result)
        return cycle_result


def build_order_plan(
    *,
    market: MarketSnapshot,
    target_position: float,
    current_position: float,
    current_notional_usdc: float,
    target_notional_usdc: float,
    delta_notional_usdc: float,
    config: AppConfig,
) -> OrderPlan:
    no_trade_reason = classify_rebalance_skip_reason(
        target_position=target_position,
        current_position=current_position,
        delta_notional_usdc=delta_notional_usdc,
        rebalance_threshold=config.risk.rebalance_threshold,
        min_trade_notional_usdc=config.risk.min_trade_notional_usdc,
    )
    if no_trade_reason is not None:
        return OrderPlan(order_intent=None, no_trade_reason=no_trade_reason)

    side = "BUY" if delta_notional_usdc > 0.0 else "SELL"
    quantity = abs(delta_notional_usdc) / market.mid_price
    return OrderPlan(
        order_intent=OrderIntent(
            product_id=market.product_id,
            side=side,
            quantity=quantity,
            target_position=target_position,
            target_notional_usdc=target_notional_usdc,
            current_notional_usdc=current_notional_usdc,
            reason="rebalance_to_target",
        ),
        no_trade_reason=None,
    )


def build_order_intent(**kwargs) -> OrderIntent | None:
    return build_order_plan(**kwargs).order_intent


def build_risk_decision(
    *,
    target_before_risk: float,
    target_after_risk: float,
    current_position: float,
    target_notional_usdc: float,
    current_notional_usdc: float,
    delta_notional_usdc: float,
    config: AppConfig,
    halted: bool,
    rebalance_eligible: bool,
) -> RiskDecision:
    return RiskDecision(
        target_before_risk=target_before_risk,
        target_after_risk=target_after_risk,
        current_position=current_position,
        target_notional_usdc=target_notional_usdc,
        current_notional_usdc=current_notional_usdc,
        delta_notional_usdc=delta_notional_usdc,
        rebalance_threshold=config.risk.rebalance_threshold,
        min_trade_notional_usdc=config.risk.min_trade_notional_usdc,
        halted=halted,
        rebalance_eligible=rebalance_eligible,
    )


def build_halt_no_trade_reason() -> NoTradeReason:
    return NoTradeReason(
        code="drawdown_halt",
        message="Trading halted because the configured daily drawdown limit was breached.",
    )


def build_execution_summary(
    *,
    fill: object | None = None,
    no_trade_reason: NoTradeReason | None = None,
) -> ExecutionSummary:
    if fill is not None:
        return ExecutionSummary(
            action="filled",
            reason_code="filled",
            reason_message="Cycle placed and filled a rebalance order.",
            summary="Filled a rebalance order toward the target position.",
        )
    if no_trade_reason is not None and no_trade_reason.code == "drawdown_halt":
        return ExecutionSummary(
            action="halted",
            reason_code=no_trade_reason.code,
            reason_message=no_trade_reason.message,
            summary="Trading halted for the cycle because the drawdown guard triggered.",
        )
    if no_trade_reason is not None:
        return ExecutionSummary(
            action="skipped",
            reason_code=no_trade_reason.code,
            reason_message=no_trade_reason.message,
            summary=f"Skipped rebalancing: {no_trade_reason.message}",
        )
    return ExecutionSummary(
        action="skipped",
        reason_code="unknown",
        reason_message="The cycle did not produce a fill.",
        summary="Cycle ended without a fill.",
    )
