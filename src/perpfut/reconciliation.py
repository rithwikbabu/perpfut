"""Read-only reconciliation from Coinbase exchange truth."""

from __future__ import annotations

from datetime import datetime, timezone

from .domain import (
    ExchangeFill,
    IntxAssetBalance,
    IntxPortfolioSummary,
    IntxPosition,
    IntxReconciliationSnapshot,
)


def reconcile_intx_state(
    *,
    portfolio_uuid: str,
    summary: IntxPortfolioSummary,
    balances: list[IntxAssetBalance],
    positions: list[IntxPosition],
    fills: list[ExchangeFill],
    product_id: str | None = None,
) -> IntxReconciliationSnapshot:
    filtered_fills = [
        fill
        for fill in fills
        if fill.portfolio_uuid in (None, portfolio_uuid)
        and (product_id is None or fill.product_id == product_id)
    ]
    as_of = max((fill.trade_time for fill in filtered_fills), default=datetime.now(timezone.utc))

    current_position = None
    if product_id is not None:
        current_position = next(
            (position for position in positions if position.product_id == product_id),
            None,
        )
    elif positions:
        current_position = max(
            positions,
            key=lambda position: abs(position.position_notional.value)
            if position.position_notional is not None
            else 0.0,
        )

    return IntxReconciliationSnapshot(
        portfolio_uuid=portfolio_uuid,
        product_id=product_id,
        as_of=as_of,
        summary=summary,
        balances=tuple(balances),
        positions=tuple(positions),
        current_position=current_position,
        recent_fills=tuple(filtered_fills),
    )
