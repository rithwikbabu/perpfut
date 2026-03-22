"""Historical candle datasets and aligned snapshot synthesis for backtests."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

from .domain import Candle, MarketSnapshot

GRANULARITY_SECONDS = {
    "ONE_MINUTE": 60,
}


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
            if not candles:
                raise ValueError(
                    f"historical dataset contains no candles for product '{product_id}' "
                    f"between {start.isoformat()} and {end.isoformat()}"
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

    granularity_seconds = GRANULARITY_SECONDS.get(dataset.granularity)
    if granularity_seconds is None:
        raise ValueError(f"unsupported dataset granularity: {dataset.granularity}")
    expected_gap_seconds = granularity_seconds
    ordered_common_timestamps = sorted(common_timestamps)
    frames: list[AlignedSnapshotFrame] = []
    for end_index in range(lookback_candles - 1, len(ordered_common_timestamps)):
        selected_timestamps = ordered_common_timestamps[end_index + 1 - lookback_candles : end_index + 1]
        if any(
            (next_timestamp - current_timestamp).total_seconds() != expected_gap_seconds
            for current_timestamp, next_timestamp in zip(selected_timestamps, selected_timestamps[1:])
        ):
            continue
        timestamp = selected_timestamps[-1]
        snapshots: dict[str, MarketSnapshot] = {}
        for product_id, candles in dataset.candles_by_product.items():
            window = tuple(candles[timestamp_indexes[product_id][item]] for item in selected_timestamps)
            current = window[-1]
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
