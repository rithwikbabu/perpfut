from datetime import datetime, timedelta, timezone
import json

from perpfut.backtest_data import HistoricalDatasetBuilder, synthesize_aligned_snapshots
from perpfut.domain import Candle


def _build_candles(
    *,
    anchor: datetime,
    count: int,
    missing_indexes: set[int] | None = None,
    base_price: float = 100.0,
) -> list[Candle]:
    missing_indexes = missing_indexes or set()
    candles: list[Candle] = []
    for index in range(count):
        if index in missing_indexes:
            continue
        price = base_price + index
        candles.append(
            Candle(
                start=anchor + timedelta(minutes=index),
                low=price - 1.0,
                high=price + 1.0,
                open=price,
                close=price + 0.5,
                volume=1_000.0 + index,
            )
        )
    return candles


class FakeHistoricalClient:
    def __init__(self, candles_by_product: dict[str, list[Candle]]):
        self.candles_by_product = candles_by_product
        self.calls: list[tuple[str, datetime, datetime, str]] = []

    def fetch_historical_candles(
        self,
        product_id: str,
        *,
        start: datetime,
        end: datetime,
        granularity: str = "ONE_MINUTE",
    ) -> list[Candle]:
        self.calls.append((product_id, start, end, granularity))
        return list(self.candles_by_product[product_id])


def test_historical_dataset_builder_persists_manifest_and_candles(tmp_path) -> None:
    anchor = datetime(2026, 3, 20, 0, 0, tzinfo=timezone.utc)
    client = FakeHistoricalClient(
        {
            "BTC-PERP-INTX": _build_candles(anchor=anchor, count=5, base_price=100.0),
            "ETH-PERP-INTX": _build_candles(anchor=anchor, count=5, base_price=200.0),
        }
    )
    builder = HistoricalDatasetBuilder(client=client, base_runs_dir=tmp_path)

    dataset = builder.build_dataset(
        products=["BTC-PERP-INTX", "ETH-PERP-INTX"],
        start=anchor,
        end=anchor + timedelta(minutes=5),
    )

    dataset_dir = tmp_path / "backtests" / "datasets" / dataset.dataset_id
    manifest = json.loads((dataset_dir / "manifest.json").read_text(encoding="utf-8"))

    assert dataset_dir.exists()
    assert manifest["products"] == ["BTC-PERP-INTX", "ETH-PERP-INTX"]
    assert manifest["candle_counts"] == {"BTC-PERP-INTX": 5, "ETH-PERP-INTX": 5}
    assert (dataset_dir / "BTC-PERP-INTX.json").exists()
    assert (dataset_dir / "ETH-PERP-INTX.json").exists()
    assert client.calls == [
        ("BTC-PERP-INTX", anchor, anchor + timedelta(minutes=5), "ONE_MINUTE"),
        ("ETH-PERP-INTX", anchor, anchor + timedelta(minutes=5), "ONE_MINUTE"),
    ]

    loaded = builder.load_dataset(dataset.dataset_id)
    assert loaded.products == dataset.products
    assert loaded.candles_by_product["BTC-PERP-INTX"][0].close == 100.5


def test_synthesize_aligned_snapshots_uses_common_timestamps_and_lookback(tmp_path) -> None:
    anchor = datetime(2026, 3, 20, 0, 0, tzinfo=timezone.utc)
    client = FakeHistoricalClient(
        {
            "BTC-PERP-INTX": _build_candles(anchor=anchor, count=6, base_price=100.0),
            "ETH-PERP-INTX": _build_candles(
                anchor=anchor,
                count=6,
                missing_indexes={2},
                base_price=200.0,
            ),
        }
    )
    builder = HistoricalDatasetBuilder(client=client, base_runs_dir=tmp_path)
    dataset = builder.build_dataset(
        products=["BTC-PERP-INTX", "ETH-PERP-INTX"],
        start=anchor,
        end=anchor + timedelta(minutes=6),
    )

    frames = synthesize_aligned_snapshots(dataset, lookback_candles=3)

    assert [frame.timestamp for frame in frames] == [
        anchor + timedelta(minutes=3),
        anchor + timedelta(minutes=4),
        anchor + timedelta(minutes=5),
    ]
    for frame in frames:
        assert set(frame.snapshots) == {"BTC-PERP-INTX", "ETH-PERP-INTX"}
        assert len(frame.snapshots["BTC-PERP-INTX"].candles) == 3
        assert len(frame.snapshots["ETH-PERP-INTX"].candles) == 3
        assert frame.snapshots["BTC-PERP-INTX"].as_of == frame.timestamp
