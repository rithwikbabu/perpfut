from perpfut.backtest_runner import BacktestAssetCycle, BacktestCycleResult, BacktestPortfolioState
from perpfut.domain import ExecutionSummary, Mode, PositionState, RiskDecision, SignalDecision
from perpfut.sleeve_backtest import _aggregate_daily_metrics


def _build_cycle(timestamp: str, equity_usdc: float) -> BacktestCycleResult:
    asset = BacktestAssetCycle(
        product_id="BTC-PERP-INTX",
        signal=SignalDecision(strategy="momentum", raw_value=0.1, target_position=0.2),
        risk_decision=RiskDecision(
            target_before_risk=0.2,
            target_after_risk=0.2,
            current_position=0.0,
            target_notional_usdc=2_000.0,
            current_notional_usdc=0.0,
            delta_notional_usdc=2_000.0,
            rebalance_threshold=0.0,
            min_trade_notional_usdc=0.0,
            halted=False,
            rebalance_eligible=True,
        ),
        execution_summary=ExecutionSummary(
            action="skipped",
            reason_code="test",
            reason_message="test",
            summary="test",
        ),
        no_trade_reason=None,
        order_intent=None,
        fill=None,
        state=PositionState(collateral_usdc=equity_usdc, mark_price=1.0),
    )
    return BacktestCycleResult(
        cycle_id=timestamp,
        mode=Mode.BACKTEST,
        timestamp=timestamp,
        portfolio=BacktestPortfolioState(
            collateral_usdc=equity_usdc,
            realized_pnl_usdc=0.0,
            unrealized_pnl_usdc=0.0,
            equity_usdc=equity_usdc,
            gross_notional_usdc=0.0,
            net_notional_usdc=0.0,
        ),
        assets={"BTC-PERP-INTX": asset},
    )


def test_aggregate_daily_metrics_uses_worst_intraday_drawdown() -> None:
    results = [
        _build_cycle("2026-03-20T23:57:00+00:00", 10_000.0),
        _build_cycle("2026-03-20T23:58:00+00:00", 9_500.0),
        _build_cycle("2026-03-20T23:59:00+00:00", 9_800.0),
        _build_cycle("2026-03-21T00:00:00+00:00", 10_200.0),
        _build_cycle("2026-03-21T00:01:00+00:00", 8_700.0),
        _build_cycle("2026-03-21T00:02:00+00:00", 10_400.0),
    ]

    daily = _aggregate_daily_metrics(
        results=results,
        starting_equity_usdc=10_000.0,
        max_leverage=2.0,
        universe=("BTC-PERP-INTX",),
    )

    assert [(point.label, point.value) for point in daily["drawdown"]] == [
        ("2026-03-20", 500.0),
        ("2026-03-21", 1_500.0),
    ]
