"""Live execution loop with preview-first market IOC trading."""

from __future__ import annotations

import time
import uuid
from dataclasses import replace
from typing import Protocol

from .config import AppConfig
from .domain import (
    ExecutionSummary,
    IntxReconciliationSnapshot,
    NoTradeReason,
    OrderIntent,
    OrderPreview,
    OrderStatusSnapshot,
    RiskDecision,
)
from .engine import (
    MarketDataClient,
    build_execution_summary,
    build_halt_no_trade_reason,
    build_order_plan,
    build_risk_decision,
)
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
        resume_state: dict | None = None,
    ):
        self.config = config
        self.market_data = market_data
        self.trading_client = trading_client
        self.artifact_store = artifact_store
        self.portfolio_uuid = portfolio_uuid
        self.resume_state = resume_state
        self._resume_logged = False

    def run(self) -> None:
        for cycle_number in range(1, self.config.runtime.iterations + 1):
            self.run_cycle(cycle_number)
            if cycle_number < self.config.runtime.iterations:
                time.sleep(self.config.runtime.interval_seconds)

    def run_cycle(self, cycle_number: int) -> None:
        cycle_id = f"cycle-{cycle_number:04d}"
        product_id = self.config.runtime.product_id
        if self.resume_state is not None and not self._resume_logged:
            self.artifact_store.append_event(
                "resume_loaded",
                {
                    "run_id": self.artifact_store.run_id,
                    "cycle_id": cycle_id,
                    "mode": "live",
                    "product_id": product_id,
                    "resume_state": self.resume_state,
                },
            )
            self._resume_logged = True
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
        self._log_resume_mismatch_if_needed(cycle_id, current_notional_usdc)

        signal = compute_signal(
            market.candles,
            lookback_candles=self.config.strategy.lookback_candles,
            signal_scale=self.config.strategy.signal_scale,
        )
        raw_target_position = signal.target_position
        target_position = clip_target_position(
            raw_target_position,
            max_abs_position=self.config.risk.max_abs_position,
        )
        signal = replace(signal, target_position=target_position)
        target_notional_usdc = target_position * self.config.max_abs_notional_usdc
        delta_notional_usdc = target_notional_usdc - current_notional_usdc
        risk_decision = build_risk_decision(
            target_before_risk=raw_target_position,
            target_after_risk=target_position,
            current_position=current_position,
            target_notional_usdc=target_notional_usdc,
            current_notional_usdc=current_notional_usdc,
            delta_notional_usdc=delta_notional_usdc,
            config=self.config,
            halted=False,
            rebalance_eligible=False,
        )
        no_trade_reason: NoTradeReason | None = None

        if should_halt_for_drawdown(
            starting_collateral_usdc=self.config.simulation.starting_collateral_usdc,
            equity_usdc=total_balance,
            max_daily_drawdown_usdc=self.config.risk.max_daily_drawdown_usdc,
        ):
            no_trade_reason = build_halt_no_trade_reason()
            risk_decision = build_risk_decision(
                target_before_risk=raw_target_position,
                target_after_risk=target_position,
                current_position=current_position,
                target_notional_usdc=target_notional_usdc,
                current_notional_usdc=current_notional_usdc,
                delta_notional_usdc=delta_notional_usdc,
                config=self.config,
                halted=True,
                rebalance_eligible=False,
            )
            execution_summary = build_execution_summary(no_trade_reason=no_trade_reason)
            self._halt(
                cycle_id,
                reason="max_daily_drawdown",
                no_trade_reason=no_trade_reason,
                risk_decision=risk_decision,
                execution_summary=execution_summary,
                cancel_open_orders=True,
            )
            self._write_live_state(
                cycle_id,
                exchange_state=exchange_state,
                current_notional_usdc=current_notional_usdc,
                current_position=current_position,
                signal=signal,
                no_trade_reason=no_trade_reason,
                risk_decision=risk_decision,
                execution_summary=execution_summary,
            )
            return

        order_plan = build_order_plan(
            market=market,
            target_position=target_position,
            current_position=current_position,
            current_notional_usdc=current_notional_usdc,
            target_notional_usdc=target_notional_usdc,
            delta_notional_usdc=delta_notional_usdc,
            config=self.config,
        )
        risk_decision = build_risk_decision(
            target_before_risk=raw_target_position,
            target_after_risk=target_position,
            current_position=current_position,
            target_notional_usdc=target_notional_usdc,
            current_notional_usdc=current_notional_usdc,
            delta_notional_usdc=delta_notional_usdc,
            config=self.config,
            halted=False,
            rebalance_eligible=order_plan.order_intent is not None,
        )
        no_trade_reason = order_plan.no_trade_reason

        if order_plan.order_intent is None:
            execution_summary = build_execution_summary(no_trade_reason=no_trade_reason)
            self.artifact_store.append_event(
                "live_noop",
                {
                    "run_id": self.artifact_store.run_id,
                    "cycle_id": cycle_id,
                    "mode": "live",
                    "product_id": product_id,
                    "target_position": target_position,
                    "current_position": current_position,
                    "risk_decision": risk_decision,
                    "no_trade_reason": no_trade_reason,
                    "execution_summary": execution_summary,
                },
            )
            self._write_live_state(
                cycle_id,
                exchange_state=exchange_state,
                current_notional_usdc=current_notional_usdc,
                current_position=current_position,
                signal=signal,
                no_trade_reason=no_trade_reason,
                risk_decision=risk_decision,
                execution_summary=execution_summary,
            )
            return

        order_intent = order_plan.order_intent
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
                "risk_decision": risk_decision,
            },
        )
        if preview.errs:
            execution_summary = ExecutionSummary(
                action="halted",
                reason_code="preview_rejected",
                reason_message="Coinbase rejected the preview request for the proposed order.",
                summary="Trading halted because order preview rejected the candidate order.",
            )
            self._halt(
                cycle_id,
                reason="preview_rejected",
                order_intent=order_intent,
                preview=preview,
                risk_decision=risk_decision,
                execution_summary=execution_summary,
                cancel_open_orders=True,
            )
            self._write_live_state(
                cycle_id,
                exchange_state=exchange_state,
                current_notional_usdc=current_notional_usdc,
                current_position=current_position,
                signal=signal,
                order_intent=order_intent,
                risk_decision=risk_decision,
                execution_summary=execution_summary,
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
                "risk_decision": risk_decision,
            },
        )
        if not submission.success:
            execution_summary = ExecutionSummary(
                action="halted",
                reason_code="submit_rejected",
                reason_message="Coinbase rejected the live market order submission.",
                summary="Trading halted because the live market order submission failed.",
            )
            self._halt(
                cycle_id,
                reason="submit_rejected",
                order_intent=order_intent,
                submission=submission,
                risk_decision=risk_decision,
                execution_summary=execution_summary,
                cancel_open_orders=True,
            )
            self._write_live_state(
                cycle_id,
                exchange_state=exchange_state,
                current_notional_usdc=current_notional_usdc,
                current_position=current_position,
                signal=signal,
                order_intent=order_intent,
                risk_decision=risk_decision,
                execution_summary=execution_summary,
            )
            return

        order_status = self.trading_client.get_order(submission.order_id)
        fills = self.trading_client.list_fills(order_id=submission.order_id, limit=20)
        if order_status.status in {"OPEN", "PENDING"}:
            execution_summary = ExecutionSummary(
                action="halted",
                reason_code="open_order_after_submit",
                reason_message="Submitted market order remained open or pending after submission.",
                summary="Trading halted because the submitted market order did not finish immediately.",
            )
        else:
            execution_summary = build_execution_summary(fill=order_status)
        self.artifact_store.append_event(
            "order_fill",
            {
                "run_id": self.artifact_store.run_id,
                "cycle_id": cycle_id,
                "mode": "live",
                "product_id": product_id,
                "order_status": order_status,
                "fills": fills,
                "risk_decision": risk_decision,
                "execution_summary": execution_summary,
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
                    "risk_decision": risk_decision,
                    "execution_summary": execution_summary,
                },
            )

        self._write_live_state(
            cycle_id,
            exchange_state=exchange_state,
            current_notional_usdc=current_notional_usdc,
            current_position=current_position,
            signal=signal,
            order_intent=order_intent,
            last_submission=submission,
            last_order_status=order_status,
            risk_decision=risk_decision,
            execution_summary=execution_summary,
        )

    def _halt(
        self,
        cycle_id: str,
        *,
        reason: str,
        order_intent: OrderIntent | None = None,
        preview: OrderPreview | None = None,
        submission: object | None = None,
        no_trade_reason: NoTradeReason | None = None,
        risk_decision: RiskDecision | None = None,
        execution_summary: ExecutionSummary | None = None,
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
                "no_trade_reason": no_trade_reason,
                "risk_decision": risk_decision,
                "execution_summary": execution_summary,
                "cancel_results": cancel_results,
            },
        )

    def _log_resume_mismatch_if_needed(self, cycle_id: str, current_notional_usdc: float) -> None:
        if self.resume_state is None:
            return
        previous_notional = float(self.resume_state.get("current_position_notional_usdc") or 0.0)
        if abs(previous_notional - current_notional_usdc) < 1e-9:
            return
        self.artifact_store.append_event(
            "resume_mismatch",
            {
                "run_id": self.artifact_store.run_id,
                "cycle_id": cycle_id,
                "mode": "live",
                "product_id": self.config.runtime.product_id,
                "checkpoint_position_notional_usdc": previous_notional,
                "exchange_position_notional_usdc": current_notional_usdc,
            },
        )

    def _write_live_state(
        self,
        cycle_id: str,
        *,
        exchange_state: IntxReconciliationSnapshot,
        current_notional_usdc: float,
        current_position: float,
        signal: object | None = None,
        order_intent: object | None = None,
        last_submission: object | None = None,
        last_order_status: object | None = None,
        no_trade_reason: NoTradeReason | None = None,
        risk_decision: RiskDecision | None = None,
        execution_summary: ExecutionSummary | None = None,
    ) -> None:
        self.artifact_store.write_state(
            {
                "run_id": self.artifact_store.run_id,
                "cycle_id": cycle_id,
                "mode": "live",
                "product_id": self.config.runtime.product_id,
                "portfolio_uuid": self.portfolio_uuid,
                "current_position": current_position,
                "current_position_notional_usdc": current_notional_usdc,
                "signal": signal,
                "order_intent": order_intent,
                "exchange_snapshot": exchange_state,
                "no_trade_reason": no_trade_reason,
                "risk_decision": risk_decision,
                "execution_summary": execution_summary,
                "last_submission": last_submission,
                "last_order_status": last_order_status,
            }
        )
