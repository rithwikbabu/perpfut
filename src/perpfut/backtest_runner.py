"""Shared-capital historical backtest runner."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Iterable

from .backtest_data import HistoricalDataset, synthesize_aligned_backtest_steps
from .config import AppConfig
from .domain import (
    ExecutionSummary,
    Mode,
    NoTradeReason,
    OrderIntent,
    PositionState,
    RiskDecision,
    SignalDecision,
    SimulatedFill,
)
from .engine import (
    build_execution_summary,
    build_halt_no_trade_reason,
    build_order_plan,
    build_risk_decision,
)
from .risk import clip_target_position, should_halt_for_drawdown
from .sim import apply_fill, simulate_market_fill
from .strategy_registry import compute_strategy_signal


@dataclass(frozen=True, slots=True)
class BacktestPortfolioState:
    collateral_usdc: float
    realized_pnl_usdc: float
    unrealized_pnl_usdc: float
    equity_usdc: float
    gross_notional_usdc: float
    net_notional_usdc: float


@dataclass(frozen=True, slots=True)
class BacktestAssetCycle:
    product_id: str
    signal: SignalDecision
    risk_decision: RiskDecision
    execution_summary: ExecutionSummary
    no_trade_reason: NoTradeReason | None
    order_intent: OrderIntent | None
    fill: SimulatedFill | None
    state: PositionState


@dataclass(frozen=True, slots=True)
class BacktestCycleResult:
    cycle_id: str
    mode: Mode
    timestamp: str
    portfolio: BacktestPortfolioState
    assets: dict[str, BacktestAssetCycle]


class SharedCapitalBacktestRunner:
    def __init__(
        self,
        *,
        config: AppConfig,
        dataset: HistoricalDataset,
        products: Iterable[str] | None = None,
    ):
        self.config = config
        self.dataset = dataset
        self.products = tuple(products or dataset.products)
        self.asset_states = {
            product_id: PositionState()
            for product_id in self.products
        }

    def run(self) -> list[BacktestCycleResult]:
        results: list[BacktestCycleResult] = []
        steps = synthesize_aligned_backtest_steps(
            self.dataset,
            lookback_candles=self.config.strategy.lookback_candles,
        )
        for cycle_number, step in enumerate(steps, start=1):
            marked_states = {
                product_id: replace(state, mark_price=step.snapshots[product_id].mid_price)
                for product_id, state in self.asset_states.items()
            }
            portfolio_before = summarize_portfolio(
                marked_states,
                starting_collateral_usdc=self.config.simulation.starting_collateral_usdc,
            )
            halted = should_halt_for_drawdown(
                starting_collateral_usdc=self.config.simulation.starting_collateral_usdc,
                equity_usdc=portfolio_before.equity_usdc,
                max_daily_drawdown_usdc=self.config.risk.max_daily_drawdown_usdc,
            )
            raw_signals = {
                product_id: compute_strategy_signal(
                    step.snapshots[product_id].candles,
                    self.config.strategy,
                )
                for product_id in self.products
            }
            target_positions = allocate_target_positions(
                {
                    product_id: clip_target_position(
                        signal.target_position,
                        max_abs_position=self.config.risk.max_abs_position,
                    )
                    for product_id, signal in raw_signals.items()
                },
                max_gross_position=self.config.risk.max_gross_position,
            )

            next_states = dict(marked_states)
            asset_cycles: dict[str, BacktestAssetCycle] = {}
            max_notional_usdc = portfolio_before.equity_usdc * self.config.simulation.max_leverage
            for product_id in self.products:
                state = marked_states[product_id]
                market = step.snapshots[product_id]
                current_notional_usdc = state.position_notional_usdc
                current_position = (
                    current_notional_usdc / max_notional_usdc if abs(max_notional_usdc) > 1e-12 else 0.0
                )
                target_position = target_positions[product_id]
                target_notional_usdc = target_position * max_notional_usdc
                delta_notional_usdc = target_notional_usdc - current_notional_usdc
                risk_decision = build_risk_decision(
                    target_before_risk=raw_signals[product_id].target_position,
                    target_after_risk=target_position,
                    current_position=current_position,
                    target_notional_usdc=target_notional_usdc,
                    current_notional_usdc=current_notional_usdc,
                    delta_notional_usdc=delta_notional_usdc,
                    config=self.config,
                    halted=halted,
                    rebalance_eligible=False,
                )
                no_trade_reason = None
                order_intent = None
                fill = None
                if halted:
                    no_trade_reason = build_halt_no_trade_reason()
                else:
                    order_plan = build_order_plan(
                        market=market,
                        target_position=target_position,
                        current_position=current_position,
                        current_notional_usdc=current_notional_usdc,
                        target_notional_usdc=target_notional_usdc,
                        delta_notional_usdc=delta_notional_usdc,
                        config=self.config,
                    )
                    order_intent = order_plan.order_intent
                    no_trade_reason = order_plan.no_trade_reason
                    risk_decision = build_risk_decision(
                        target_before_risk=raw_signals[product_id].target_position,
                        target_after_risk=target_position,
                        current_position=current_position,
                        target_notional_usdc=target_notional_usdc,
                        current_notional_usdc=current_notional_usdc,
                        delta_notional_usdc=delta_notional_usdc,
                        config=self.config,
                        halted=False,
                        rebalance_eligible=order_intent is not None,
                    )
                    if order_intent is not None:
                        order_intent = replace(
                            order_intent,
                            quantity=abs(delta_notional_usdc) / step.next_open_by_product[product_id],
                        )
                        fill = simulate_market_fill(
                            order_intent,
                            mark_price=step.next_open_by_product[product_id],
                            slippage_bps=self.config.simulation.slippage_bps,
                            timestamp=step.next_timestamp,
                        )
                        next_states[product_id] = apply_fill(state, fill)
                next_states[product_id] = replace(
                    next_states[product_id],
                    mark_price=step.next_open_by_product[product_id],
                )
                asset_cycles[product_id] = BacktestAssetCycle(
                    product_id=product_id,
                    signal=replace(raw_signals[product_id], target_position=target_position),
                    risk_decision=risk_decision,
                    execution_summary=build_execution_summary(fill=fill, no_trade_reason=no_trade_reason),
                    no_trade_reason=no_trade_reason,
                    order_intent=order_intent,
                    fill=fill,
                    state=next_states[product_id],
                )

            self.asset_states = next_states
            portfolio_after = summarize_portfolio(
                self.asset_states,
                starting_collateral_usdc=self.config.simulation.starting_collateral_usdc,
            )
            results.append(
                BacktestCycleResult(
                    cycle_id=f"cycle-{cycle_number:04d}",
                    mode=Mode.BACKTEST,
                    timestamp=step.next_timestamp.isoformat(),
                    portfolio=portfolio_after,
                    assets=asset_cycles,
                )
            )
        return results


def allocate_target_positions(
    raw_targets: dict[str, float],
    *,
    max_gross_position: float,
) -> dict[str, float]:
    if max_gross_position <= 0.0:
        raise ValueError("max_gross_position must be positive")
    gross = sum(abs(target) for target in raw_targets.values())
    if gross <= max_gross_position or gross <= 1e-12:
        return dict(raw_targets)
    scale = max_gross_position / gross
    return {
        product_id: target * scale
        for product_id, target in raw_targets.items()
    }


def summarize_portfolio(
    asset_states: dict[str, PositionState],
    *,
    starting_collateral_usdc: float,
) -> BacktestPortfolioState:
    realized_pnl_usdc = sum(state.realized_pnl_usdc for state in asset_states.values())
    unrealized_pnl_usdc = sum(state.unrealized_pnl_usdc for state in asset_states.values())
    net_notional_usdc = sum(state.position_notional_usdc for state in asset_states.values())
    gross_notional_usdc = sum(abs(state.position_notional_usdc) for state in asset_states.values())
    equity_usdc = starting_collateral_usdc + realized_pnl_usdc + unrealized_pnl_usdc
    return BacktestPortfolioState(
        collateral_usdc=starting_collateral_usdc,
        realized_pnl_usdc=realized_pnl_usdc,
        unrealized_pnl_usdc=unrealized_pnl_usdc,
        equity_usdc=equity_usdc,
        gross_notional_usdc=gross_notional_usdc,
        net_notional_usdc=net_notional_usdc,
    )
