"""Coinbase REST adapters and response normalization."""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
import jwt

from .domain import (
    Candle,
    ExchangeFill,
    IntxAssetBalance,
    IntxPortfolioSummary,
    IntxPosition,
    MarketSnapshot,
    MoneyValue,
)
from .reconciliation import reconcile_intx_state


API_BASE_URL = "https://api.coinbase.com/api/v3/brokerage"


@dataclass(frozen=True, slots=True)
class PerpetualProduct:
    product_id: str
    display_name: str
    price: float
    funding_rate: float | None
    max_leverage: float | None


@dataclass(frozen=True, slots=True)
class TickerSnapshot:
    product_id: str
    as_of: datetime
    last_price: float
    best_bid: float
    best_ask: float


class CoinbaseExchangeError(RuntimeError):
    """Raised when Coinbase returns a malformed or failing response."""


class CoinbaseAuthError(CoinbaseExchangeError):
    """Raised when Coinbase private auth configuration is invalid."""


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
        return parse_perpetual_products(response.json())

    def fetch_market(self, product_id: str, *, candle_limit: int) -> MarketSnapshot:
        candles = self.fetch_candles(product_id, limit=candle_limit)
        ticker = self.fetch_ticker(product_id)
        return MarketSnapshot(
            product_id=product_id,
            as_of=ticker.as_of,
            last_price=ticker.last_price,
            best_bid=ticker.best_bid,
            best_ask=ticker.best_ask,
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
        return parse_candles(response.json(), product_id=product_id)

    def fetch_ticker(self, product_id: str) -> TickerSnapshot:
        response = self._client.get(
            f"/market/products/{product_id}/ticker",
            params={"limit": 1},
        )
        response.raise_for_status()
        return parse_ticker(response.json(), product_id=product_id)


class CoinbasePrivateClient:
    """Authenticated read-only client for Coinbase INTX state."""

    def __init__(
        self,
        *,
        api_key_id: str,
        api_key_secret: str,
        timeout_seconds: float = 10.0,
    ):
        self._token_provider = CoinbaseJWTTokenProvider(
            api_key_id=api_key_id,
            api_key_secret=api_key_secret,
        )
        self._client = httpx.Client(
            base_url=API_BASE_URL,
            timeout=timeout_seconds,
            headers={
                "user-agent": "perpfut/0.1.0",
            },
        )

    def __enter__(self) -> "CoinbasePrivateClient":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def close(self) -> None:
        self._client.close()

    def preview_market_order(self, *_: object, **__: object) -> None:
        raise NotImplementedError("live Coinbase execution is not scaffolded yet")

    def place_market_order(self, *_: object, **__: object) -> None:
        raise NotImplementedError("live Coinbase execution is not scaffolded yet")

    def get_intx_portfolio_summary(self, portfolio_uuid: str) -> IntxPortfolioSummary:
        payload = self._get(f"/intx/portfolio/{portfolio_uuid}")
        return parse_intx_portfolio_summary(payload, portfolio_uuid=portfolio_uuid)

    def get_portfolio_balances(self, portfolio_uuid: str) -> list[IntxAssetBalance]:
        payload = self._get(f"/intx/balances/{portfolio_uuid}")
        return parse_portfolio_balances(payload, portfolio_uuid=portfolio_uuid)

    def list_intx_positions(self, portfolio_uuid: str) -> list[IntxPosition]:
        payload = self._get(f"/intx/positions/{portfolio_uuid}")
        return parse_intx_positions(payload, portfolio_uuid=portfolio_uuid)

    def list_fills(
        self,
        *,
        product_id: str | None = None,
        limit: int = 50,
    ) -> list[ExchangeFill]:
        payload = self._get(
            "/orders/historical/fills",
            params={
                "product_id": product_id,
                "limit": limit,
            },
        )
        return parse_order_fills(payload)

    def reconcile_intx_portfolio(
        self,
        *,
        portfolio_uuid: str,
        product_id: str | None = None,
        fills_limit: int = 50,
    ):
        summary = self.get_intx_portfolio_summary(portfolio_uuid)
        balances = self.get_portfolio_balances(portfolio_uuid)
        positions = self.list_intx_positions(portfolio_uuid)
        fills = self.list_fills(product_id=product_id, limit=fills_limit)
        return reconcile_intx_state(
            portfolio_uuid=portfolio_uuid,
            summary=summary,
            balances=balances,
            positions=positions,
            fills=fills,
            product_id=product_id,
        )

    def _get(self, path: str, *, params: dict[str, Any] | None = None) -> dict[str, Any]:
        response = self._client.get(
            path,
            params={key: value for key, value in (params or {}).items() if value is not None},
            headers=self._auth_headers("GET", path),
        )
        response.raise_for_status()
        return response.json()

    def _auth_headers(self, method: str, path: str) -> dict[str, str]:
        request_path = f"/api/v3/brokerage{path}"
        return {
            "Authorization": f"Bearer {self._token_provider.build_rest_token(method, request_path)}",
        }


class CoinbaseJWTTokenProvider:
    """Builds short-lived request-scoped JWTs for Coinbase App APIs."""

    def __init__(
        self,
        *,
        api_key_id: str,
        api_key_secret: str,
        request_host: str = "api.coinbase.com",
    ):
        if not api_key_id or not api_key_secret:
            raise CoinbaseAuthError("Coinbase API key id and secret are required")

        self.api_key_id = api_key_id
        self.api_key_secret = api_key_secret.replace("\\n", "\n")
        self.request_host = request_host

    def build_rest_token(self, request_method: str, request_path: str) -> str:
        now = int(datetime.now(timezone.utc).timestamp())
        payload = {
            "iss": "cdp",
            "nbf": now,
            "exp": now + 120,
            "sub": self.api_key_id,
            "uri": f"{request_method.upper()} {self.request_host}{request_path}",
        }
        headers = {
            "kid": self.api_key_id,
            "nonce": secrets.token_hex(16),
        }
        return jwt.encode(payload, self.api_key_secret, algorithm="ES256", headers=headers)


def _parse_iso8601(value: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    return datetime.fromisoformat(normalized)


def parse_perpetual_products(payload: dict[str, Any]) -> list[PerpetualProduct]:
    raw_products = payload.get("products")
    if not isinstance(raw_products, list):
        raise CoinbaseExchangeError("products payload is missing the products list")

    products: list[PerpetualProduct] = []
    for raw in raw_products:
        try:
            future_details = raw.get("future_product_details") or {}
            perpetual_details = future_details.get("perpetual_details") or {}
            product_id = raw["product_id"]
            price = raw.get("mid_market_price") or raw.get("price")
            if price in (None, ""):
                raise CoinbaseExchangeError(f"missing price for product {product_id}")

            products.append(
                PerpetualProduct(
                    product_id=product_id,
                    display_name=raw.get("display_name", product_id),
                    price=float(price),
                    funding_rate=_optional_float(
                        perpetual_details.get("funding_rate") or future_details.get("funding_rate")
                    ),
                    max_leverage=_optional_float(perpetual_details.get("max_leverage")),
                )
            )
        except KeyError as exc:
            raise CoinbaseExchangeError("product payload is missing a required field") from exc
        except ValueError as exc:
            raise CoinbaseExchangeError("product payload contains an invalid numeric field") from exc

    return products


def parse_candles(payload: dict[str, Any], *, product_id: str) -> list[Candle]:
    raw_candles = payload.get("candles")
    if not isinstance(raw_candles, list) or not raw_candles:
        raise CoinbaseExchangeError(f"no candles returned for {product_id}")

    candles: list[Candle] = []
    for raw in raw_candles:
        try:
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
        except KeyError as exc:
            raise CoinbaseExchangeError(f"candle payload is missing a required field for {product_id}") from exc
        except ValueError as exc:
            raise CoinbaseExchangeError(f"candle payload contains an invalid value for {product_id}") from exc

    candles.sort(key=lambda candle: candle.start)
    return candles


def parse_ticker(payload: dict[str, Any], *, product_id: str) -> TickerSnapshot:
    trades = payload.get("trades")
    if not isinstance(trades, list) or not trades:
        raise CoinbaseExchangeError(f"no trades returned for {product_id}")

    last_trade = trades[0]
    try:
        return TickerSnapshot(
            product_id=product_id,
            as_of=_parse_iso8601(last_trade["time"]),
            last_price=float(last_trade["price"]),
            best_bid=float(payload.get("best_bid") or 0.0),
            best_ask=float(payload.get("best_ask") or 0.0),
        )
    except KeyError as exc:
        raise CoinbaseExchangeError(f"ticker payload is missing a required field for {product_id}") from exc
    except ValueError as exc:
        raise CoinbaseExchangeError(f"ticker payload contains an invalid value for {product_id}") from exc


def parse_intx_portfolio_summary(
    payload: dict[str, Any],
    *,
    portfolio_uuid: str,
) -> IntxPortfolioSummary:
    portfolios = payload.get("portfolios")
    if not isinstance(portfolios, list) or not portfolios:
        raise CoinbaseExchangeError(f"no portfolio summary returned for {portfolio_uuid}")

    raw_portfolio = portfolios[0]
    raw_summary = payload.get("summary") or {}
    try:
        return IntxPortfolioSummary(
            portfolio_uuid=raw_portfolio["portfolio_uuid"],
            collateral=float(raw_portfolio.get("collateral") or 0.0),
            position_notional=float(raw_portfolio.get("position_notional") or 0.0),
            open_position_notional=float(raw_portfolio.get("open_position_notional") or 0.0),
            pending_fees=float(raw_portfolio.get("pending_fees") or 0.0),
            borrow=float(raw_portfolio.get("borrow") or 0.0),
            accrued_interest=float(raw_portfolio.get("accrued_interest") or 0.0),
            rolling_debt=float(raw_portfolio.get("rolling_debt") or 0.0),
            liquidation_percentage=float(raw_portfolio.get("liquidation_percentage") or 0.0),
            buying_power=_optional_money(raw_summary.get("buying_power")),
            total_balance=_optional_money(raw_summary.get("total_balance")),
            unrealized_pnl=_optional_money(raw_summary.get("unrealized_pnl")),
            max_withdrawal_amount=_optional_money(raw_summary.get("max_withdrawal_amount")),
        )
    except KeyError as exc:
        raise CoinbaseExchangeError("portfolio summary payload is missing a required field") from exc
    except ValueError as exc:
        raise CoinbaseExchangeError("portfolio summary payload contains an invalid value") from exc


def parse_portfolio_balances(payload: dict[str, Any], *, portfolio_uuid: str) -> list[IntxAssetBalance]:
    portfolio_balances = payload.get("portfolio_balances")
    if not isinstance(portfolio_balances, list) or not portfolio_balances:
        raise CoinbaseExchangeError(f"no portfolio balances returned for {portfolio_uuid}")

    balances: list[IntxAssetBalance] = []
    try:
        for portfolio in portfolio_balances:
            current_portfolio_uuid = portfolio["portfolio_uuid"]
            for raw_balance in portfolio.get("balances", []):
                raw_asset = raw_balance["asset"]
                balances.append(
                    IntxAssetBalance(
                        portfolio_uuid=current_portfolio_uuid,
                        asset_id=raw_asset["asset_id"],
                        asset_name=raw_asset["asset_name"],
                        quantity=float(raw_balance.get("quantity") or 0.0),
                        hold=float(raw_balance.get("hold") or 0.0),
                        transfer_hold=float(raw_balance.get("transfer_hold") or 0.0),
                        collateral_value=float(raw_balance.get("collateral_value") or 0.0),
                        max_withdraw_amount=float(raw_balance.get("max_withdraw_amount") or 0.0),
                    )
                )
    except KeyError as exc:
        raise CoinbaseExchangeError("portfolio balances payload is missing a required field") from exc
    except ValueError as exc:
        raise CoinbaseExchangeError("portfolio balances payload contains an invalid value") from exc

    return balances


def parse_intx_positions(payload: dict[str, Any], *, portfolio_uuid: str) -> list[IntxPosition]:
    raw_positions = payload.get("positions")
    if not isinstance(raw_positions, list):
        raise CoinbaseExchangeError(f"positions payload is missing the positions list for {portfolio_uuid}")

    positions: list[IntxPosition] = []
    try:
        for raw_position in raw_positions:
            positions.append(
                IntxPosition(
                    product_id=raw_position["product_id"],
                    portfolio_uuid=raw_position["portfolio_uuid"],
                    symbol=raw_position.get("symbol", raw_position["product_id"]),
                    position_side=raw_position.get("position_side", "POSITION_SIDE_UNKNOWN"),
                    margin_type=raw_position.get("margin_type", "MARGIN_TYPE_UNSPECIFIED"),
                    net_size=float(raw_position.get("net_size") or 0.0),
                    leverage=_optional_float(raw_position.get("leverage")),
                    vwap=_optional_money(raw_position.get("vwap")),
                    entry_vwap=_optional_money(raw_position.get("entry_vwap")),
                    mark_price=_optional_money(raw_position.get("mark_price")),
                    liquidation_price=_optional_money(raw_position.get("liquidation_price")),
                    position_notional=_optional_money(raw_position.get("position_notional")),
                    unrealized_pnl=_optional_money(raw_position.get("unrealized_pnl")),
                    aggregated_pnl=_optional_money(raw_position.get("aggregated_pnl")),
                )
            )
    except KeyError as exc:
        raise CoinbaseExchangeError("positions payload is missing a required field") from exc
    except ValueError as exc:
        raise CoinbaseExchangeError("positions payload contains an invalid value") from exc

    return positions


def parse_order_fills(payload: dict[str, Any]) -> list[ExchangeFill]:
    raw_fills = payload.get("fills")
    if not isinstance(raw_fills, list):
        raise CoinbaseExchangeError("fills payload is missing the fills list")

    fills: list[ExchangeFill] = []
    try:
        for raw_fill in raw_fills:
            fills.append(
                ExchangeFill(
                    entry_id=raw_fill["entry_id"],
                    trade_id=raw_fill["trade_id"],
                    order_id=raw_fill["order_id"],
                    product_id=raw_fill["product_id"],
                    portfolio_uuid=raw_fill.get("retail_portfolio_id"),
                    side=raw_fill.get("side", "UNKNOWN"),
                    price=float(raw_fill["price"]),
                    size=float(raw_fill["size"]),
                    commission=float(raw_fill.get("commission") or 0.0),
                    liquidity_indicator=raw_fill.get("liquidity_indicator"),
                    trade_time=_parse_iso8601(raw_fill["trade_time"]),
                )
            )
    except KeyError as exc:
        raise CoinbaseExchangeError("fills payload is missing a required field") from exc
    except ValueError as exc:
        raise CoinbaseExchangeError("fills payload contains an invalid value") from exc

    return fills


def _optional_float(value: str | None) -> float | None:
    if value in (None, ""):
        return None
    return float(value)


def _optional_money(value: dict[str, str] | None) -> MoneyValue | None:
    if not value:
        return None
    return MoneyValue(
        value=float(value["value"]),
        currency=value["currency"],
    )
