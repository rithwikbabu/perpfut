"""Coinbase REST adapters and response normalization."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

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
        payload = self._get_json(
            "/market/products",
            params={
                "limit": limit,
                "product_type": "FUTURE",
                "contract_expiry_type": "PERPETUAL",
            },
            error_context="public products",
        )
        return parse_public_products(payload)

    def fetch_market(self, product_id: str, *, candle_limit: int) -> MarketSnapshot:
        candles = self.fetch_candles(product_id, limit=candle_limit)
        ticker_payload = self.fetch_ticker(product_id)
        return parse_public_market_snapshot(
            product_id=product_id,
            candles=candles,
            ticker_payload=ticker_payload,
        )

    def fetch_candles(self, product_id: str, *, limit: int) -> list[Candle]:
        end = datetime.now(timezone.utc)
        start = end - timedelta(minutes=max(limit, 2))
        payload = self._get_json(
            f"/market/products/{product_id}/candles",
            params={
                "start": str(int(start.timestamp())),
                "end": str(int(end.timestamp())),
                "granularity": "ONE_MINUTE",
                "limit": limit,
            },
            error_context=f"public candles for {product_id}",
        )
        return parse_public_candles(payload)

    def fetch_ticker(self, product_id: str) -> dict:
        return self._get_json(
            f"/market/products/{product_id}/ticker",
            params={"limit": 1},
            error_context=f"public ticker for {product_id}",
        )

    def _get_json(self, path: str, *, params: dict[str, Any], error_context: str) -> dict[str, Any]:
        try:
            response = self._client.get(path, params=params)
            response.raise_for_status()
            payload = response.json()
        except httpx.HTTPError as exc:
            raise CoinbaseExchangeError(f"{error_context} request failed: {exc}") from exc
        except ValueError as exc:
            raise CoinbaseExchangeError(f"{error_context} response was not valid JSON") from exc

        if not isinstance(payload, dict):
            raise CoinbaseExchangeError(f"{error_context} response was not a JSON object")
        return payload


class CoinbasePrivateClient:
    """Future home for JWT auth, live execution, and INTX reconciliation."""

    def preview_market_order(self, *_: object, **__: object) -> None:
        raise NotImplementedError("live Coinbase execution is not scaffolded yet")

    def place_market_order(self, *_: object, **__: object) -> None:
        raise NotImplementedError("live Coinbase execution is not scaffolded yet")

    def get_intx_portfolio(self, *_: object, **__: object) -> None:
        raise NotImplementedError("live Coinbase execution is not scaffolded yet")


def parse_public_products(payload: dict[str, Any]) -> list[PerpetualProduct]:
    raw_products = payload.get("products")
    if not isinstance(raw_products, list):
        raise CoinbaseExchangeError("public products payload missing products list")

    products: list[PerpetualProduct] = []
    for index, raw_product in enumerate(raw_products):
        if not isinstance(raw_product, dict):
            raise CoinbaseExchangeError(f"public products payload item {index} was not an object")
        product_id = _require_string(raw_product, "product_id", context=f"products[{index}]")
        display_name = raw_product.get("display_name") or product_id
        future_details = raw_product.get("future_product_details") or {}
        if not isinstance(future_details, dict):
            raise CoinbaseExchangeError(f"public products payload future details invalid for {product_id}")
        perpetual_details = future_details.get("perpetual_details") or {}
        if not isinstance(perpetual_details, dict):
            raise CoinbaseExchangeError(
                f"public products payload perpetual details invalid for {product_id}"
            )
        products.append(
            PerpetualProduct(
                product_id=product_id,
                display_name=str(display_name),
                price=_require_float_from_keys(
                    raw_product,
                    keys=("mid_market_price", "price"),
                    context=f"products[{index}]",
                ),
                funding_rate=_optional_float(
                    perpetual_details.get("funding_rate") or future_details.get("funding_rate")
                ),
                max_leverage=_optional_float(perpetual_details.get("max_leverage")),
            )
        )
    return products


def parse_public_candles(payload: dict[str, Any]) -> list[Candle]:
    raw_candles = payload.get("candles")
    if not isinstance(raw_candles, list):
        raise CoinbaseExchangeError("public candles payload missing candles list")
    if not raw_candles:
        raise CoinbaseExchangeError("public candles payload contained no candles")

    candles = []
    for index, raw_candle in enumerate(raw_candles):
        if not isinstance(raw_candle, dict):
            raise CoinbaseExchangeError(f"public candles payload item {index} was not an object")
        candles.append(
            Candle(
                start=datetime.fromtimestamp(
                    int(_require_string(raw_candle, "start", context=f"candles[{index}]")),
                    tz=timezone.utc,
                ),
                low=_require_float(raw_candle, "low", context=f"candles[{index}]"),
                high=_require_float(raw_candle, "high", context=f"candles[{index}]"),
                open=_require_float(raw_candle, "open", context=f"candles[{index}]"),
                close=_require_float(raw_candle, "close", context=f"candles[{index}]"),
                volume=_require_float(raw_candle, "volume", context=f"candles[{index}]"),
            )
        )

    candles.sort(key=lambda candle: candle.start)
    return candles


def parse_public_market_snapshot(
    *,
    product_id: str,
    candles: list[Candle],
    ticker_payload: dict[str, Any],
) -> MarketSnapshot:
    raw_trades = ticker_payload.get("trades")
    if not isinstance(raw_trades, list) or not raw_trades:
        raise CoinbaseExchangeError(f"public ticker payload contained no trades for {product_id}")

    first_trade = raw_trades[0]
    if not isinstance(first_trade, dict):
        raise CoinbaseExchangeError(f"public ticker payload trade was invalid for {product_id}")

    return MarketSnapshot(
        product_id=product_id,
        as_of=_parse_iso8601(_require_string(first_trade, "time", context=f"ticker[{product_id}]")),
        last_price=_require_float(first_trade, "price", context=f"ticker[{product_id}]"),
        best_bid=_require_float(ticker_payload, "best_bid", context=f"ticker[{product_id}]"),
        best_ask=_require_float(ticker_payload, "best_ask", context=f"ticker[{product_id}]"),
        candles=tuple(candles),
    )


def _parse_iso8601(value: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    return datetime.fromisoformat(normalized)


def _optional_float(value: str | None) -> float | None:
    if value in (None, ""):
        return None
    return float(value)


def _require_string(payload: dict[str, Any], key: str, *, context: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or value == "":
        raise CoinbaseExchangeError(f"{context} missing string field {key}")
    return value


def _require_float(payload: dict[str, Any], key: str, *, context: str) -> float:
    value = payload.get(key)
    if value in (None, ""):
        raise CoinbaseExchangeError(f"{context} missing numeric field {key}")
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise CoinbaseExchangeError(f"{context} invalid numeric field {key}: {value!r}") from exc


def _require_float_from_keys(
    payload: dict[str, Any],
    *,
    keys: tuple[str, ...],
    context: str,
) -> float:
    for key in keys:
        value = payload.get(key)
        if value not in (None, ""):
            try:
                return float(value)
            except (TypeError, ValueError) as exc:
                raise CoinbaseExchangeError(
                    f"{context} invalid numeric field {key}: {value!r}"
                ) from exc
    joined_keys = ", ".join(keys)
    raise CoinbaseExchangeError(f"{context} missing numeric field from: {joined_keys}")
