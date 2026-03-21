from datetime import datetime, timedelta, timezone

from perpfut.config import AppConfig
from perpfut.domain import (
    ExchangeFill,
    IntxPortfolioSummary,
    IntxReconciliationSnapshot,
    IntxPosition,
    MarketSnapshot,
    MoneyValue,
    OrderPreview,
    OrderStatusSnapshot,
    OrderSubmission,
)
from perpfut.live_execution import LiveExecutor
from perpfut.telemetry import ArtifactStore
from perpfut.domain import Candle


class FakeMarketData:
    def fetch_market(self, product_id: str, *, candle_limit: int) -> MarketSnapshot:
        now = datetime.now(timezone.utc)
        candles = tuple(
            Candle(
                start=now + timedelta(minutes=index),
                low=100.0 + index,
                high=101.0 + index,
                open=100.0 + index,
                close=110.0 + index,
                volume=1_000.0,
            )
            for index in range(candle_limit)
        )
        return MarketSnapshot(
            product_id=product_id,
            as_of=now,
            last_price=candles[-1].close,
            best_bid=candles[-1].close - 0.5,
            best_ask=candles[-1].close + 0.5,
            candles=candles,
        )


class FakeTradingClient:
    def __init__(self, *, preview_errs: tuple[str, ...] = ()):
        self.preview_errs = preview_errs
        self.submitted = False
        self.cancelled = False

    def reconcile_intx_portfolio(self, *, portfolio_uuid: str, product_id: str | None = None, fills_limit: int = 50):
        position = IntxPosition(
            product_id=product_id or "BTC-PERP-INTX",
            portfolio_uuid=portfolio_uuid,
            symbol=product_id or "BTC-PERP-INTX",
            position_side="LONG",
            margin_type="CROSS",
            net_size=0.0,
            leverage=1.0,
            vwap=None,
            entry_vwap=None,
            mark_price=MoneyValue(value=110.0, currency="USDC"),
            liquidation_price=None,
            position_notional=MoneyValue(value=0.0, currency="USDC"),
            unrealized_pnl=MoneyValue(value=0.0, currency="USDC"),
            aggregated_pnl=MoneyValue(value=0.0, currency="USDC"),
        )
        return IntxReconciliationSnapshot(
            portfolio_uuid=portfolio_uuid,
            product_id=product_id,
            as_of=datetime.now(timezone.utc),
            summary=IntxPortfolioSummary(
                portfolio_uuid=portfolio_uuid,
                collateral=10000.0,
                position_notional=0.0,
                open_position_notional=0.0,
                pending_fees=0.0,
                borrow=0.0,
                accrued_interest=0.0,
                rolling_debt=0.0,
                liquidation_percentage=0.0,
                buying_power=MoneyValue(value=10000.0, currency="USDC"),
                total_balance=MoneyValue(value=10000.0, currency="USDC"),
                unrealized_pnl=MoneyValue(value=0.0, currency="USDC"),
                max_withdrawal_amount=MoneyValue(value=10000.0, currency="USDC"),
            ),
            balances=(),
            positions=(position,),
            current_position=None,
            recent_fills=(),
        )

    def preview_market_order(self, *, portfolio_uuid: str, product_id: str, side: str, quantity: float, client_order_id: str):
        return OrderPreview(
            preview_id="preview-1",
            product_id=product_id,
            side=side,
            order_total=100.0,
            commission_total=1.0,
            errs=self.preview_errs,
        )

    def place_market_order(self, *, portfolio_uuid: str, product_id: str, side: str, quantity: float, client_order_id: str):
        self.submitted = True
        return OrderSubmission(
            order_id="order-1",
            client_order_id=client_order_id,
            product_id=product_id,
            side=side,
            success=True,
            failure_reason=None,
        )

    def get_order(self, order_id: str) -> OrderStatusSnapshot:
        return OrderStatusSnapshot(
            order_id=order_id,
            client_order_id="client-1",
            product_id="BTC-PERP-INTX",
            side="BUY",
            status="FILLED",
            filled_size=0.1,
            average_filled_price=110.5,
            total_fees=1.0,
        )

    def list_fills(self, *, product_id: str | None = None, order_id: str | None = None, limit: int = 50):
        return [
            ExchangeFill(
                entry_id="entry-1",
                trade_id="trade-1",
                order_id=order_id or "order-1",
                product_id=product_id or "BTC-PERP-INTX",
                portfolio_uuid="portfolio-123",
                side="BUY",
                price=110.5,
                size=0.1,
                commission=1.0,
                liquidity_indicator="TAKER",
                trade_time=datetime.now(timezone.utc),
            )
        ]

    def cancel_orders(self, order_ids: list[str]):
        self.cancelled = True
        return []


def test_live_executor_previews_submits_and_logs_fill(tmp_path) -> None:
    config = AppConfig.from_env().with_overrides(
        iterations=1,
        interval_seconds=0,
        runs_dir=tmp_path,
    )
    store = ArtifactStore.create(config.runtime.runs_dir)
    store.write_metadata(config)
    trading_client = FakeTradingClient()

    executor = LiveExecutor(
        config=config,
        market_data=FakeMarketData(),
        trading_client=trading_client,
        artifact_store=store,
        portfolio_uuid="portfolio-123",
    )

    executor.run_cycle(1)

    assert trading_client.submitted is True
    events = store.events_path.read_text(encoding="utf-8")
    assert "order_preview" in events
    assert "order_submit" in events
    assert "order_fill" in events


def test_live_executor_halts_on_preview_error_without_submit(tmp_path) -> None:
    config = AppConfig.from_env().with_overrides(
        iterations=1,
        interval_seconds=0,
        runs_dir=tmp_path,
    )
    store = ArtifactStore.create(config.runtime.runs_dir)
    store.write_metadata(config)
    trading_client = FakeTradingClient(preview_errs=("size too small",))

    executor = LiveExecutor(
        config=config,
        market_data=FakeMarketData(),
        trading_client=trading_client,
        artifact_store=store,
        portfolio_uuid="portfolio-123",
    )

    executor.run_cycle(1)

    assert trading_client.submitted is False
    events = store.events_path.read_text(encoding="utf-8")
    assert "halt" in events
    assert "preview_rejected" in events
