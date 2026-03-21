"""Paper fill simulation and position state transitions."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime

from .domain import OrderIntent, PositionState, SimulatedFill


def simulate_market_fill(
    intent: OrderIntent,
    *,
    mark_price: float,
    slippage_bps: float,
    timestamp: datetime,
) -> SimulatedFill:
    direction = 1.0 if intent.side == "BUY" else -1.0
    slippage_multiplier = 1.0 + (direction * slippage_bps / 10_000.0)
    price = mark_price * slippage_multiplier
    return SimulatedFill(
        product_id=intent.product_id,
        side=intent.side,
        quantity=intent.quantity,
        price=price,
        mark_price=mark_price,
        slippage_bps=slippage_bps,
        timestamp=timestamp,
    )


def apply_fill(state: PositionState, fill: SimulatedFill) -> PositionState:
    current_quantity = state.quantity
    fill_quantity = fill.signed_quantity
    next_quantity = current_quantity + fill_quantity
    realized_pnl = state.realized_pnl_usdc
    entry_price = state.entry_price

    if abs(current_quantity) < 1e-12:
        next_entry_price = fill.price
    elif current_quantity * fill_quantity > 0.0:
        next_entry_price = (
            (abs(current_quantity) * (entry_price or fill.price))
            + (abs(fill_quantity) * fill.price)
        ) / (abs(current_quantity) + abs(fill_quantity))
    else:
        closed_quantity = min(abs(current_quantity), abs(fill_quantity))
        reference_entry = entry_price or fill.price
        realized_pnl += closed_quantity * (fill.price - reference_entry) * (
            1.0 if current_quantity > 0.0 else -1.0
        )

        if abs(next_quantity) < 1e-12:
            next_entry_price = None
            next_quantity = 0.0
        elif current_quantity * next_quantity > 0.0:
            next_entry_price = reference_entry
        else:
            next_entry_price = fill.price

    return replace(
        state,
        quantity=next_quantity,
        entry_price=next_entry_price,
        mark_price=fill.mark_price,
        realized_pnl_usdc=realized_pnl,
    )
