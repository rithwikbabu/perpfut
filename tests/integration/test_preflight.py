from datetime import datetime, timezone
from perpfut.config import AppConfig
from perpfut.domain import Candle
from perpfut.domain import (
    IntxPortfolioSummary,
    IntxReconciliationSnapshot,
    MarketSnapshot,
    MoneyValue,
    OrderPreview,
)
from perpfut import preflight as preflight_module
from perpfut.preflight import run_preflight


class FakePublicClient:
    def fetch_market(self, product_id: str, *, candle_limit: int):
        now = datetime.now(timezone.utc)
        candles = tuple(
            Candle(
                start=now,
                low=100.0,
                high=101.0,
                open=100.0,
                close=101.0,
                volume=1_000.0,
            )
            for _ in range(candle_limit)
        )
        return MarketSnapshot(
            product_id=product_id,
            as_of=now,
            last_price=101.0,
            best_bid=100.9,
            best_ask=101.1,
            candles=candles,
        )


class FakePrivateClient:
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


def test_run_preflight_live_reports_ready_with_private_checks(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("PERPFUT_ENABLE_LIVE", "1")
    monkeypatch.setenv("COINBASE_API_KEY_ID", "key-id")
    monkeypatch.setenv("COINBASE_API_KEY_SECRET", "secret")
    monkeypatch.setenv("COINBASE_INTX_PORTFOLIO_UUID", "portfolio-123")
    config = AppConfig.from_env().with_overrides(runs_dir=tmp_path)

    report = run_preflight(
        config=config,
        mode="live",
        public_client=FakePublicClient(),
        private_client=FakePrivateClient(),
        portfolio_uuid="portfolio-123",
        preview_quantity=0.001,
    )

    assert report.ready is True
    assert {check.name for check in report.checks} >= {
        "runs_dir",
        "public_market_data",
        "live_gate_env",
        "private_reconcile",
        "order_preview",
    }


def test_run_preflight_live_requires_preview_quantity(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("PERPFUT_ENABLE_LIVE", "1")
    monkeypatch.setenv("COINBASE_API_KEY_ID", "key-id")
    monkeypatch.setenv("COINBASE_API_KEY_SECRET", "secret")
    config = AppConfig.from_env().with_overrides(runs_dir=tmp_path)

    report = run_preflight(
        config=config,
        mode="live",
        public_client=FakePublicClient(),
        private_client=FakePrivateClient(),
        portfolio_uuid="portfolio-123",
    )

    assert report.ready is False
    preview_check = next(check for check in report.checks if check.name == "order_preview")
    assert preview_check.ok is False
    assert "--preview-quantity" in preview_check.detail


def test_run_preflight_reports_non_writable_runs_dir(tmp_path, monkeypatch) -> None:
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()

    def deny_temporary_directory(*args, **kwargs):
        raise PermissionError("read-only runs dir")

    monkeypatch.setattr(preflight_module.tempfile, "TemporaryDirectory", deny_temporary_directory)
    config = AppConfig.from_env().with_overrides(runs_dir=runs_dir)

    report = run_preflight(
        config=config,
        mode="paper",
        public_client=FakePublicClient(),
    )

    assert report.ready is False
    runs_check = next(check for check in report.checks if check.name == "runs_dir")
    assert runs_check.ok is False
    assert "read-only runs dir" in runs_check.detail
