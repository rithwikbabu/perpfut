"""Live execution loop with preview-first market IOC trading."""

from __future__ import annotations

import time
import uuid
from typing import Protocol

from .config import AppConfig
from .domain import IntxReconciliationSnapshot, OrderIntent, OrderPreview, OrderStatusSnapshot
from .engine import MarketDataClient, build_order_intent
from .risk import clip_target_position, should_halt_for_drawdown
from .signal_momentum import compute_signal
from .telemetry import ArtifactStore


class LiveTradingClient(Protocol):
    def reconcile_intx_portfolio(
        self,
        *,
        portfolio_uuid: str,
        product_id: str | None = None,
        fills_limit: int = 50,
    ) -> IntxReconciliationSnapshot:
        ...

    def preview_market_order(
        self,
        *,
        portfolio_uuid: str,
        product_id: str,
        side: str,
        quantity: float,
        client_order_id: str,
    ) -> OrderPreview:
        ...

    def place_market_order(
        self,
        *,
        portfolio_uuid: str,
        product_id: str,
        side: str,
        quantity: float,
        client_order_id: str,
    ):
        ...

    def get_order(self, order_id: str) -> OrderStatusSnapshot:
        ...

    def list_fills(
        self,
        *,
        product_id: str | None = None,
        order_id: str | None = None,
        limit: int = 50,
    ):
        ...

    def list_orders(
        self,
        *,
        product_id: str | None = None,
        order_status: str | None = None,
        limit: int = 50,
    ):
        ...

    def cancel_orders(self, order_ids: list[str]):
        ...


class LiveExecutor:
    """Runs a narrow preview-first live execution cycle."""

    def __init__(
        self,
        *,
        config: AppConfig,
        market_data: MarketDataClient,
        trading_client: LiveTradingClient,
        artifact_store: ArtifactStore,
        portfolio_uuid: str,
    ):
        self.config = config
        self.market_data = market_data
        self.trading_client = trading_client
        self.artifact_store = artifact_store
        self.portfolio_uuid = portfolio_uuid

    def run(self) -> None:
        for cycle_number in range(1, self.config.runtime.iterations + 1):
            self.run_cycle(cycle_number)
            if cycle_number < self.config.runtime.iterations:
                time.sleep(self.config.runtime.interval_seconds)

    def run_cycle(self, cycle_number: int) -> None:
        cycle_id = f"cycle-{cycle_number:04d}"
        product_id = self.config.runtime.product_id
        market = self.market_data.fetch_market(
            product_id,
            candle_limit=self.config.strategy.lookback_candles,
        )
        exchange_state = self.trading_client.reconcile_intx_portfolio(
            portfolio_uuid=self.portfolio_uuid,
            product_id=product_id,
            fills_limit=50,
        )
        self.artifact_store.append_event(
            "reconciliation",
            {
                "run_id": self.artifact_store.run_id,
                "cycle_id": cycle_id,
                "mode": "live",
                "product_id": product_id,
                "snapshot": exchange_state,
            },
        )

        total_balance = (
            exchange_state.summary.total_balance.value
            if exchange_state.summary.total_balance is not None
            else self.config.simulation.starting_collateral_usdc
        )
        current_notional_usdc = (
            exchange_state.current_position.position_notional.value
            if exchange_state.current_position is not None
            and exchange_state.current_position.position_notional is not None
            else 0.0
        )
        current_position = current_notional_usdc / self.config.max_abs_notional_usdc

        signal = compute_signal(
            market.candles,
            lookback_candles=self.config.strategy.lookback_candles,
            signal_scale=self.config.strategy.signal_scale,
        )
        target_position = clip_target_position(
            signal.target_position,
            max_abs_position=self.config.risk.max_abs_position,
        )
        target_notional_usdc = target_position * self.config.max_abs_notional_usdc
        delta_notional_usdc = target_notional_usdc - current_notional_usdc

        if should_halt_for_drawdown(
            starting_collateral_usdc=self.config.simulation.starting_collateral_usdc,
            equity_usdc=total_balance,
            max_daily_drawdown_usdc=self.config.risk.max_daily_drawdown_usdc,
        ):
            self._halt(cycle_id, reason="max_daily_drawdown", cancel_open_orders=True)
            return

        order_intent = build_order_intent(
            market=market,
            target_position=target_position,
            current_position=current_position,
            current_notional_usdc=current_notional_usdc,
            target_notional_usdc=target_notional_usdc,
            delta_notional_usdc=delta_notional_usdc,
            config=self.config,
        )
        if order_intent is None:
            self.artifact_store.append_event(
                "live_noop",
                {
                    "run_id": self.artifact_store.run_id,
                    "cycle_id": cycle_id,
                    "mode": "live",
                    "product_id": product_id,
                    "target_position": target_position,
                    "current_position": current_position,
                },
            )
            return

        client_order_id = uuid.uuid4().hex
        preview = self.trading_client.preview_market_order(
            portfolio_uuid=self.portfolio_uuid,
            product_id=order_intent.product_id,
            side=order_intent.side,
            quantity=order_intent.quantity,
            client_order_id=client_order_id,
        )
        self.artifact_store.append_event(
            "order_preview",
            {
                "run_id": self.artifact_store.run_id,
                "cycle_id": cycle_id,
                "mode": "live",
                "product_id": product_id,
                "order_intent": order_intent,
                "preview": preview,
            },
        )
        if preview.errs:
            self._halt(
                cycle_id,
                reason="preview_rejected",
                order_intent=order_intent,
                preview=preview,
                cancel_open_orders=True,
            )
            return

        submission = self.trading_client.place_market_order(
            portfolio_uuid=self.portfolio_uuid,
            product_id=order_intent.product_id,
            side=order_intent.side,
            quantity=order_intent.quantity,
            client_order_id=client_order_id,
        )
        self.artifact_store.append_event(
            "order_submit",
            {
                "run_id": self.artifact_store.run_id,
                "cycle_id": cycle_id,
                "mode": "live",
                "product_id": product_id,
                "order_intent": order_intent,
                "submission": submission,
            },
        )
        if not submission.success:
            self._halt(
                cycle_id,
                reason="submit_rejected",
                order_intent=order_intent,
                submission=submission,
                cancel_open_orders=True,
            )
            return

        order_status = self.trading_client.get_order(submission.order_id)
        fills = self.trading_client.list_fills(order_id=submission.order_id, limit=20)
        self.artifact_store.append_event(
            "order_fill",
            {
                "run_id": self.artifact_store.run_id,
                "cycle_id": cycle_id,
                "mode": "live",
                "product_id": product_id,
                "order_status": order_status,
                "fills": fills,
            },
        )

        if order_status.status in {"OPEN", "PENDING"}:
            cancel_results = self.trading_client.cancel_orders([submission.order_id])
            self.artifact_store.append_event(
                "halt",
                {
                    "run_id": self.artifact_store.run_id,
                    "cycle_id": cycle_id,
                    "mode": "live",
                    "product_id": product_id,
                    "reason": "open_order_after_submit",
                    "cancel_results": cancel_results,
                },
            )

        self.artifact_store.write_state(
            {
                "run_id": self.artifact_store.run_id,
                "cycle_id": cycle_id,
                "mode": "live",
                "product_id": product_id,
                "order_id": submission.order_id,
                "client_order_id": submission.client_order_id,
            }
        )

    def _halt(
        self,
        cycle_id: str,
        *,
        reason: str,
        order_intent: OrderIntent | None = None,
        preview: OrderPreview | None = None,
        submission: object | None = None,
        cancel_open_orders: bool = False,
    ) -> None:
        cancel_results = []
        if cancel_open_orders:
            open_order_ids = []
            for order_status in ("OPEN", "PENDING"):
                open_orders = self.trading_client.list_orders(
                    product_id=self.config.runtime.product_id,
                    order_status=order_status,
                    limit=50,
                )
                open_order_ids.extend(order.order_id for order in open_orders)
            open_order_ids = sorted(set(open_order_ids))
            if open_order_ids:
                cancel_results = self.trading_client.cancel_orders(open_order_ids)

        self.artifact_store.append_event(
            "halt",
            {
                "run_id": self.artifact_store.run_id,
                "cycle_id": cycle_id,
                "mode": "live",
                "product_id": self.config.runtime.product_id,
                "reason": reason,
                "order_intent": order_intent,
                "preview": preview,
                "submission": submission,
                "cancel_results": cancel_results,
            },
        )
