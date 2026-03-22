from datetime import datetime, timedelta, timezone
import json

from perpfut.backtest_data import (
    DATASET_SOURCE,
    DATASET_VERSION,
    HistoricalDatasetBuilder,
    compute_dataset_fingerprint,
    synthesize_aligned_snapshots,
)
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
    registry = json.loads(
        (tmp_path / "backtests" / "datasets" / "registry.json").read_text(encoding="utf-8")
    )

    assert dataset_dir.exists()
    assert manifest["fingerprint"] == dataset.fingerprint
    assert manifest["products"] == ["BTC-PERP-INTX", "ETH-PERP-INTX"]
    assert manifest["source"] == DATASET_SOURCE
    assert manifest["version"] == DATASET_VERSION
    assert manifest["candle_counts"] == {"BTC-PERP-INTX": 5, "ETH-PERP-INTX": 5}
    assert (dataset_dir / "BTC-PERP-INTX.json").exists()
    assert (dataset_dir / "ETH-PERP-INTX.json").exists()
    assert registry[dataset.fingerprint] == dataset.dataset_id
    assert client.calls == [
        ("BTC-PERP-INTX", anchor, anchor + timedelta(minutes=5), "ONE_MINUTE"),
        ("ETH-PERP-INTX", anchor, anchor + timedelta(minutes=5), "ONE_MINUTE"),
    ]

    loaded = builder.load_dataset(dataset.dataset_id)
    assert loaded.fingerprint == dataset.fingerprint
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

    assert [frame.timestamp for frame in frames] == [anchor + timedelta(minutes=5)]
    for frame in frames:
        assert set(frame.snapshots) == {"BTC-PERP-INTX", "ETH-PERP-INTX"}
        assert len(frame.snapshots["BTC-PERP-INTX"].candles) == 3
        assert len(frame.snapshots["ETH-PERP-INTX"].candles) == 3
        assert frame.snapshots["BTC-PERP-INTX"].as_of == frame.timestamp


def test_historical_dataset_builder_rejects_products_without_candles(tmp_path) -> None:
    anchor = datetime(2026, 3, 20, 0, 0, tzinfo=timezone.utc)
    client = FakeHistoricalClient(
        {
            "BTC-PERP-INTX": _build_candles(anchor=anchor, count=5, base_price=100.0),
            "ETH-PERP-INTX": [],
        }
    )
    builder = HistoricalDatasetBuilder(client=client, base_runs_dir=tmp_path)

    try:
        builder.build_dataset(
            products=["BTC-PERP-INTX", "ETH-PERP-INTX"],
            start=anchor,
            end=anchor + timedelta(minutes=5),
        )
    except ValueError as exc:
        assert "no candles for product 'ETH-PERP-INTX'" in str(exc)
    else:
        raise AssertionError("expected builder to reject empty-product datasets")


def test_historical_dataset_builder_reuses_cached_dataset_for_identical_requests(tmp_path) -> None:
    anchor = datetime(2026, 3, 20, 0, 0, tzinfo=timezone.utc)
    client = FakeHistoricalClient(
        {
            "BTC-PERP-INTX": _build_candles(anchor=anchor, count=5, base_price=100.0),
            "ETH-PERP-INTX": _build_candles(anchor=anchor, count=5, base_price=200.0),
        }
    )
    builder = HistoricalDatasetBuilder(client=client, base_runs_dir=tmp_path)

    first = builder.build_dataset(
        products=["BTC-PERP-INTX", "ETH-PERP-INTX"],
        start=anchor,
        end=anchor + timedelta(minutes=5),
    )
    second = builder.build_dataset(
        products=["ETH-PERP-INTX", "BTC-PERP-INTX"],
        start=anchor,
        end=anchor + timedelta(minutes=5),
    )

    assert second.dataset_id == first.dataset_id
    assert client.calls == [
        ("BTC-PERP-INTX", anchor, anchor + timedelta(minutes=5), "ONE_MINUTE"),
        ("ETH-PERP-INTX", anchor, anchor + timedelta(minutes=5), "ONE_MINUTE"),
    ]


def test_historical_dataset_builder_raises_on_missing_dataset_id(tmp_path) -> None:
    builder = HistoricalDatasetBuilder(client=FakeHistoricalClient({}), base_runs_dir=tmp_path)

    try:
        builder.load_dataset("missing")
    except FileNotFoundError as exc:
        assert "backtest dataset not found: missing" in str(exc)
    else:
        raise AssertionError("expected missing dataset id to raise FileNotFoundError")


def test_compute_dataset_fingerprint_is_order_insensitive() -> None:
    anchor = datetime(2026, 3, 20, 0, 0, tzinfo=timezone.utc)

    first = compute_dataset_fingerprint(
        products=["BTC-PERP-INTX", "ETH-PERP-INTX"],
        start=anchor,
        end=anchor + timedelta(minutes=5),
        granularity="ONE_MINUTE",
    )
    second = compute_dataset_fingerprint(
        products=["ETH-PERP-INTX", "BTC-PERP-INTX"],
        start=anchor,
        end=anchor + timedelta(minutes=5),
        granularity="ONE_MINUTE",
    )

    assert first == second


def test_historical_dataset_builder_recovers_from_stale_registry_entry(tmp_path) -> None:
    anchor = datetime(2026, 3, 20, 0, 0, tzinfo=timezone.utc)
    client = FakeHistoricalClient(
        {
            "BTC-PERP-INTX": _build_candles(anchor=anchor, count=5, base_price=100.0),
        }
    )
    builder = HistoricalDatasetBuilder(client=client, base_runs_dir=tmp_path)
    fingerprint = compute_dataset_fingerprint(
        products=["BTC-PERP-INTX"],
        start=anchor,
        end=anchor + timedelta(minutes=5),
        granularity="ONE_MINUTE",
    )
    registry_path = tmp_path / "backtests" / "datasets" / "registry.json"
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(
        json.dumps({fingerprint: "missing-dataset"}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    dataset = builder.build_dataset(
        products=["BTC-PERP-INTX"],
        start=anchor,
        end=anchor + timedelta(minutes=5),
    )

    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    assert registry[fingerprint] == dataset.dataset_id
    assert client.calls == [
        ("BTC-PERP-INTX", anchor, anchor + timedelta(minutes=5), "ONE_MINUTE"),
    ]
