from datetime import datetime, timedelta, timezone

from perpfut.config import AppConfig
from perpfut.domain import (
    Candle,
    ExchangeFill,
    IntxPortfolioSummary,
    IntxReconciliationSnapshot,
    MarketSnapshot,
    MoneyValue,
    OrderPreview,
    OrderStatusSnapshot,
    OrderSubmission,
)
from perpfut.engine import PaperEngine
from perpfut.live_execution import LiveExecutor
from perpfut.telemetry import ArtifactStore


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
    def reconcile_intx_portfolio(self, *, portfolio_uuid: str, product_id: str | None = None, fills_limit: int = 50):
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
            positions=(),
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
            errs=(),
        )

    def place_market_order(self, *, portfolio_uuid: str, product_id: str, side: str, quantity: float, client_order_id: str):
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

    def list_orders(self, *, product_id: str | None = None, order_status: str | None = None, limit: int = 50):
        return []

    def cancel_orders(self, order_ids: list[str]):
        return []


def test_mvp_smoke_covers_paper_then_live_artifacts(tmp_path) -> None:
    config = AppConfig.from_env().with_overrides(
        iterations=1,
        interval_seconds=0,
        runs_dir=tmp_path,
    )

    paper_store = ArtifactStore.create(tmp_path)
    paper_store.write_metadata(config)
    paper_engine = PaperEngine(
        config=config,
        market_data=FakeMarketData(),
        artifact_store=paper_store,
    )
    paper_engine.run_cycle(1)

    live_store = ArtifactStore.create(tmp_path, resumed_from_run_id=paper_store.run_id)
    live_store.write_metadata(config)
    live_executor = LiveExecutor(
        config=config,
        market_data=FakeMarketData(),
        trading_client=FakeTradingClient(),
        artifact_store=live_store,
        portfolio_uuid="portfolio-123",
        resume_state={"run_id": paper_store.run_id, "current_position_notional_usdc": 0.0},
    )
    live_executor.run_cycle(1)

    assert paper_store.events_path.exists()
    assert live_store.events_path.exists()
    assert "order_preview" in live_store.events_path.read_text(encoding="utf-8")
