from datetime import datetime, timedelta, timezone

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
    assert result.state.quantity > 0.0
    assert artifact_store.events_path.exists()
    assert artifact_store.positions_path.exists()
    assert artifact_store.state_path.exists()
