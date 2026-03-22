"""Risk helpers for clipping targets and deciding whether to trade."""

from __future__ import annotations

from .domain import NoTradeReason


def clip_target_position(target_position: float, *, max_abs_position: float) -> float:
    return max(-max_abs_position, min(max_abs_position, target_position))


def should_rebalance(
    *,
    target_position: float,
    current_position: float,
    delta_notional_usdc: float,
    rebalance_threshold: float,
    min_trade_notional_usdc: float,
) -> bool:
    if abs(delta_notional_usdc) < min_trade_notional_usdc:
        return False
    return abs(target_position - current_position) >= rebalance_threshold


def should_halt_for_drawdown(
    *,
    starting_collateral_usdc: float,
    equity_usdc: float,
    max_daily_drawdown_usdc: float,
) -> bool:
    return (starting_collateral_usdc - equity_usdc) >= max_daily_drawdown_usdc


def classify_rebalance_skip_reason(
    *,
    target_position: float,
    current_position: float,
    delta_notional_usdc: float,
    rebalance_threshold: float,
    min_trade_notional_usdc: float,
) -> NoTradeReason | None:
    if abs(delta_notional_usdc) < min_trade_notional_usdc:
        return NoTradeReason(
            code="below_min_trade_notional",
            message=(
                f"Delta notional {delta_notional_usdc:.2f} USDC is below the minimum trade "
                f"threshold of {min_trade_notional_usdc:.2f} USDC."
            ),
        )
    delta_position = abs(target_position - current_position)
    if delta_position < rebalance_threshold:
        return NoTradeReason(
            code="below_rebalance_threshold",
            message=(
                f"Delta position {delta_position:.4f} is below the rebalance threshold of "
                f"{rebalance_threshold:.4f}."
            ),
        )
    return None
