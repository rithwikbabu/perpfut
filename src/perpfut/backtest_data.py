"""Historical candle datasets and aligned snapshot synthesis for backtests."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

from .domain import Candle, MarketSnapshot


@dataclass(frozen=True, slots=True)
class HistoricalDataset:
    dataset_id: str
    created_at: datetime
    products: tuple[str, ...]
    start: datetime
    end: datetime
    granularity: str
    candles_by_product: dict[str, tuple[Candle, ...]]


@dataclass(frozen=True, slots=True)
class AlignedSnapshotFrame:
    timestamp: datetime
    snapshots: dict[str, MarketSnapshot]


class HistoricalCandleClient(Protocol):
    def fetch_historical_candles(
        self,
        product_id: str,
        *,
        start: datetime,
        end: datetime,
        granularity: str = "ONE_MINUTE",
    ) -> list[Candle]:
        ...


class HistoricalDatasetBuilder:
    def __init__(self, *, client: HistoricalCandleClient, base_runs_dir: Path):
        self._client = client
        self._datasets_dir = base_runs_dir / "backtests" / "datasets"

    def build_dataset(
        self,
        *,
        products: list[str],
        start: datetime,
        end: datetime,
        granularity: str = "ONE_MINUTE",
    ) -> HistoricalDataset:
        if not products:
            raise ValueError("dataset requires at least one product")
        if end <= start:
            raise ValueError("dataset end must be after start")

        created_at = datetime.now(timezone.utc)
        dataset_id = created_at.strftime("%Y%m%dT%H%M%S%fZ")
        candles_by_product: dict[str, tuple[Candle, ...]] = {}
        for product_id in products:
            candles = tuple(
                self._client.fetch_historical_candles(
                    product_id,
                    start=start,
                    end=end,
                    granularity=granularity,
                )
            )
            candles_by_product[product_id] = candles

        dataset = HistoricalDataset(
            dataset_id=dataset_id,
            created_at=created_at,
            products=tuple(products),
            start=start,
            end=end,
            granularity=granularity,
            candles_by_product=candles_by_product,
        )
        self._persist_dataset(dataset)
        return dataset

    def load_dataset(self, dataset_id: str) -> HistoricalDataset:
        dataset_dir = self._datasets_dir / dataset_id
        manifest = json.loads((dataset_dir / "manifest.json").read_text(encoding="utf-8"))
        candles_by_product: dict[str, tuple[Candle, ...]] = {}
        for product_id in manifest["products"]:
            payload = json.loads((dataset_dir / f"{product_id}.json").read_text(encoding="utf-8"))
            candles_by_product[product_id] = tuple(_parse_candle(item) for item in payload["candles"])
        return HistoricalDataset(
            dataset_id=manifest["dataset_id"],
            created_at=datetime.fromisoformat(manifest["created_at"]),
            products=tuple(manifest["products"]),
            start=datetime.fromisoformat(manifest["start"]),
            end=datetime.fromisoformat(manifest["end"]),
            granularity=manifest["granularity"],
            candles_by_product=candles_by_product,
        )

    def _persist_dataset(self, dataset: HistoricalDataset) -> None:
        dataset_dir = self._datasets_dir / dataset.dataset_id
        dataset_dir.mkdir(parents=True, exist_ok=False)
        manifest = {
            "dataset_id": dataset.dataset_id,
            "created_at": dataset.created_at.isoformat(),
            "products": list(dataset.products),
            "start": dataset.start.isoformat(),
            "end": dataset.end.isoformat(),
            "granularity": dataset.granularity,
            "candle_counts": {
                product_id: len(candles)
                for product_id, candles in dataset.candles_by_product.items()
            },
        }
        (dataset_dir / "manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        for product_id, candles in dataset.candles_by_product.items():
            payload = {
                "product_id": product_id,
                "candles": [_serialize_candle(candle) for candle in candles],
            }
            (dataset_dir / f"{product_id}.json").write_text(
                json.dumps(payload, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )


def synthesize_aligned_snapshots(
    dataset: HistoricalDataset,
    *,
    lookback_candles: int,
) -> tuple[AlignedSnapshotFrame, ...]:
    if lookback_candles <= 0:
        raise ValueError("lookback_candles must be positive")

    timestamp_indexes: dict[str, dict[datetime, int]] = {}
    for product_id, candles in dataset.candles_by_product.items():
        timestamp_indexes[product_id] = {
            candle.start: index for index, candle in enumerate(candles)
        }

    common_timestamps: set[datetime] | None = None
    for indexes in timestamp_indexes.values():
        timestamps = set(indexes.keys())
        common_timestamps = timestamps if common_timestamps is None else common_timestamps & timestamps
    if not common_timestamps:
        return ()

    frames: list[AlignedSnapshotFrame] = []
    for timestamp in sorted(common_timestamps):
        snapshots: dict[str, MarketSnapshot] = {}
        for product_id, candles in dataset.candles_by_product.items():
            index = timestamp_indexes[product_id][timestamp]
            if index + 1 < lookback_candles:
                snapshots = {}
                break
            window = candles[index + 1 - lookback_candles : index + 1]
            current = candles[index]
            snapshots[product_id] = MarketSnapshot(
                product_id=product_id,
                as_of=current.start,
                last_price=current.close,
                best_bid=current.close,
                best_ask=current.close,
                candles=tuple(window),
            )
        if snapshots:
            frames.append(AlignedSnapshotFrame(timestamp=timestamp, snapshots=snapshots))
    return tuple(frames)


def _serialize_candle(candle: Candle) -> dict[str, object]:
    payload = asdict(candle)
    payload["start"] = candle.start.isoformat()
    return payload


def _parse_candle(payload: dict[str, object]) -> Candle:
    return Candle(
        start=datetime.fromisoformat(str(payload["start"])),
        low=float(payload["low"]),
        high=float(payload["high"]),
        open=float(payload["open"]),
        close=float(payload["close"]),
        volume=float(payload["volume"]),
    )
