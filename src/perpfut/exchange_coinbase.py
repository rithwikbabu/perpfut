"""Coinbase REST adapters and response normalization."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import httpx

from .domain import Candle, MarketSnapshot


API_BASE_URL = "https://api.coinbase.com/api/v3/brokerage"


@dataclass(frozen=True, slots=True)
class PerpetualProduct:
    product_id: str
    display_name: str
    price: float
    funding_rate: float | None
    max_leverage: float | None


class CoinbaseExchangeError(RuntimeError):
    """Raised when Coinbase returns a malformed or failing response."""


class CoinbasePublicClient:
    """Public market-data client for the paper trading path."""

    def __init__(self, *, timeout_seconds: float = 10.0):
        self._client = httpx.Client(
            base_url=API_BASE_URL,
            timeout=timeout_seconds,
            headers={
                "cache-control": "no-cache",
                "user-agent": "perpfut/0.1.0",
            },
        )

    def __enter__(self) -> "CoinbasePublicClient":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def close(self) -> None:
        self._client.close()

    def list_perpetual_products(self, *, limit: int = 25) -> list[PerpetualProduct]:
        response = self._client.get(
            "/market/products",
            params={
                "limit": limit,
                "product_type": "FUTURE",
                "contract_expiry_type": "PERPETUAL",
            },
        )
        response.raise_for_status()
        payload = response.json()

        products: list[PerpetualProduct] = []
        for raw in payload.get("products", []):
            future_details = raw.get("future_product_details") or {}
            perpetual_details = future_details.get("perpetual_details") or {}
            products.append(
                PerpetualProduct(
                    product_id=raw["product_id"],
                    display_name=raw.get("display_name", raw["product_id"]),
                    price=float(raw.get("mid_market_price") or raw.get("price") or 0.0),
                    funding_rate=_optional_float(
                        perpetual_details.get("funding_rate") or future_details.get("funding_rate")
                    ),
                    max_leverage=_optional_float(perpetual_details.get("max_leverage")),
                )
            )
        return products

    def fetch_market(self, product_id: str, *, candle_limit: int) -> MarketSnapshot:
        candles = self.fetch_candles(product_id, limit=candle_limit)
        ticker = self.fetch_ticker(product_id)
        trades = ticker.get("trades") or []
        if not trades:
            raise CoinbaseExchangeError(f"no trades returned for {product_id}")

        last_trade = trades[0]
        as_of = _parse_iso8601(last_trade["time"])
        return MarketSnapshot(
            product_id=product_id,
            as_of=as_of,
            last_price=float(last_trade["price"]),
            best_bid=float(ticker.get("best_bid") or 0.0),
            best_ask=float(ticker.get("best_ask") or 0.0),
            candles=tuple(candles),
        )

    def fetch_candles(self, product_id: str, *, limit: int) -> list[Candle]:
        end = datetime.now(timezone.utc)
        start = end - timedelta(minutes=max(limit, 2))
        response = self._client.get(
            f"/market/products/{product_id}/candles",
            params={
                "start": str(int(start.timestamp())),
                "end": str(int(end.timestamp())),
                "granularity": "ONE_MINUTE",
                "limit": limit,
            },
        )
        response.raise_for_status()
        payload = response.json()

        candles = []
        for raw in payload.get("candles", []):
            candles.append(
                Candle(
                    start=datetime.fromtimestamp(int(raw["start"]), tz=timezone.utc),
                    low=float(raw["low"]),
                    high=float(raw["high"]),
                    open=float(raw["open"]),
                    close=float(raw["close"]),
                    volume=float(raw["volume"]),
                )
            )
        candles.sort(key=lambda candle: candle.start)
        if not candles:
            raise CoinbaseExchangeError(f"no candles returned for {product_id}")
        return candles

    def fetch_ticker(self, product_id: str) -> dict:
        response = self._client.get(
            f"/market/products/{product_id}/ticker",
            params={"limit": 1},
        )
        response.raise_for_status()
        return response.json()


class CoinbasePrivateClient:
    """Future home for JWT auth, live execution, and INTX reconciliation."""

    def preview_market_order(self, *_: object, **__: object) -> None:
        raise NotImplementedError("live Coinbase execution is not scaffolded yet")

    def place_market_order(self, *_: object, **__: object) -> None:
        raise NotImplementedError("live Coinbase execution is not scaffolded yet")

    def get_intx_portfolio(self, *_: object, **__: object) -> None:
        raise NotImplementedError("live Coinbase execution is not scaffolded yet")


def _parse_iso8601(value: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    return datetime.fromisoformat(normalized)


def _optional_float(value: str | None) -> float | None:
    if value in (None, ""):
        return None
    return float(value)
