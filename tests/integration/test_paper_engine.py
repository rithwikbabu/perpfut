from datetime import datetime, timedelta, timezone
import json

from perpfut.config import AppConfig
from perpfut.domain import Candle, MarketSnapshot
from perpfut.engine import PaperEngine
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
                close=100.0 + index,
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


class FailingMarketData:
    def fetch_market(self, product_id: str, *, candle_limit: int) -> MarketSnapshot:
        raise AssertionError("market fetch should not be called")


def build_snapshot(*, product_id: str, anchor: datetime) -> MarketSnapshot:
    candles = tuple(
        Candle(
            start=anchor + timedelta(minutes=index),
            low=100.0 + index,
            high=101.0 + index,
            open=100.0 + index,
            close=100.0 + index,
            volume=1_000.0,
        )
        for index in range(30)
    )
    return MarketSnapshot(
        product_id=product_id,
        as_of=anchor,
        last_price=candles[-1].close,
        best_bid=candles[-1].close - 0.5,
        best_ask=candles[-1].close + 0.5,
        candles=candles,
    )


def test_paper_engine_runs_one_cycle_and_writes_artifacts(tmp_path) -> None:
    config = AppConfig.from_env().with_overrides(
        product_id="BTC-PERP-INTX",
        iterations=1,
        interval_seconds=0,
        runs_dir=tmp_path,
    )
    artifact_store = ArtifactStore.create(config.runtime.runs_dir)
    artifact_store.write_metadata(config)
    engine = PaperEngine(
        config=config,
        market_data=FakeMarketData(),
        artifact_store=artifact_store,
    )

    result = engine.run_cycle(1)

    assert result.order_intent is not None
    assert result.fill is not None
    assert result.execution_summary.action == "filled"
    assert result.execution_summary.reason_code == "filled"
    assert result.no_trade_reason is None
    assert result.risk_decision.rebalance_eligible is True
    assert result.state.quantity > 0.0
    assert artifact_store.events_path.exists()
    assert artifact_store.positions_path.exists()
    assert artifact_store.state_path.exists()
    manifest = json.loads(artifact_store.manifest_path.read_text(encoding="utf-8"))
    assert manifest["strategy_id"] == "momentum"


def test_paper_engine_records_skip_reason_when_delta_is_below_rebalance_threshold(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("REBALANCE_THRESHOLD", "0.6")
    config = AppConfig.from_env().with_overrides(
        product_id="BTC-PERP-INTX",
        iterations=1,
        interval_seconds=0,
        runs_dir=tmp_path,
    )
    artifact_store = ArtifactStore.create(config.runtime.runs_dir)
    artifact_store.write_metadata(config)
    engine = PaperEngine(
        config=config,
        market_data=FakeMarketData(),
        artifact_store=artifact_store,
    )

    result = engine.run_cycle(1)

    assert result.order_intent is None
    assert result.fill is None
    assert result.no_trade_reason is not None
    assert result.no_trade_reason.code == "below_rebalance_threshold"
    assert result.execution_summary.action == "skipped"
    assert result.risk_decision.rebalance_eligible is False


def test_paper_engine_records_skip_reason_when_delta_is_below_min_trade_notional(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("MIN_TRADE_NOTIONAL_USDC", "15000")
    config = AppConfig.from_env().with_overrides(
        product_id="BTC-PERP-INTX",
        iterations=1,
        interval_seconds=0,
        runs_dir=tmp_path,
    )
    artifact_store = ArtifactStore.create(config.runtime.runs_dir)
    artifact_store.write_metadata(config)
    engine = PaperEngine(
        config=config,
        market_data=FakeMarketData(),
        artifact_store=artifact_store,
    )

    result = engine.run_cycle(1)

    assert result.order_intent is None
    assert result.no_trade_reason is not None
    assert result.no_trade_reason.code == "below_min_trade_notional"
    assert result.execution_summary.reason_code == "below_min_trade_notional"


def test_paper_engine_can_run_a_cycle_from_a_supplied_market_snapshot(tmp_path) -> None:
    config = AppConfig.from_env().with_overrides(
        product_id="BTC-PERP-INTX",
        iterations=1,
        interval_seconds=0,
        runs_dir=tmp_path,
    )
    artifact_store = ArtifactStore.create(config.runtime.runs_dir)
    artifact_store.write_metadata(config)
    engine = PaperEngine(
        config=config,
        market_data=FailingMarketData(),
        artifact_store=artifact_store,
    )

    snapshot = build_snapshot(
        product_id="BTC-PERP-INTX",
        anchor=datetime(2026, 3, 22, 5, 0, tzinfo=timezone.utc),
    )

    result = engine.run_market_cycle(1, snapshot)

    assert result.market == snapshot
    assert result.order_intent is not None
    assert result.fill is not None
    assert result.state.quantity > 0.0
    state_payload = json.loads(artifact_store.state_path.read_text(encoding="utf-8"))
    assert state_payload["product_id"] == "BTC-PERP-INTX"
    assert state_payload["fill"]["price"] == result.fill.price
