"""Shared trading types and value objects."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class Mode(StrEnum):
    PAPER = "paper"
    LIVE = "live"


@dataclass(frozen=True, slots=True)
class Candle:
    start: datetime
    low: float
    high: float
    open: float
    close: float
    volume: float


@dataclass(frozen=True, slots=True)
class MarketSnapshot:
    product_id: str
    as_of: datetime
    last_price: float
    best_bid: float
    best_ask: float
    candles: tuple[Candle, ...]

    @property
    def mid_price(self) -> float:
        if self.best_bid > 0.0 and self.best_ask > 0.0:
            return (self.best_bid + self.best_ask) / 2.0
        return self.last_price


@dataclass(frozen=True, slots=True)
class SignalDecision:
    strategy: str
    raw_value: float
    target_position: float


@dataclass(frozen=True, slots=True)
class PositionState:
    quantity: float = 0.0
    entry_price: float | None = None
    mark_price: float = 0.0
    collateral_usdc: float = 0.0
    realized_pnl_usdc: float = 0.0

    @property
    def is_flat(self) -> bool:
        return abs(self.quantity) < 1e-12

    @property
    def position_notional_usdc(self) -> float:
        return self.quantity * self.mark_price

    @property
    def unrealized_pnl_usdc(self) -> float:
        if self.is_flat or self.entry_price is None:
            return 0.0
        return (self.mark_price - self.entry_price) * self.quantity

    @property
    def equity_usdc(self) -> float:
        return self.collateral_usdc + self.realized_pnl_usdc + self.unrealized_pnl_usdc


@dataclass(frozen=True, slots=True)
class OrderIntent:
    product_id: str
    side: str
    quantity: float
    target_position: float
    target_notional_usdc: float
    current_notional_usdc: float
    reason: str


@dataclass(frozen=True, slots=True)
class SimulatedFill:
    product_id: str
    side: str
    quantity: float
    price: float
    mark_price: float
    slippage_bps: float
    timestamp: datetime

    @property
    def signed_quantity(self) -> float:
        return self.quantity if self.side == "BUY" else -self.quantity


@dataclass(frozen=True, slots=True)
class CycleResult:
    cycle_id: str
    mode: Mode
    market: MarketSnapshot
    signal: SignalDecision
    state: PositionState
    order_intent: OrderIntent | None
    fill: SimulatedFill | None
