import json
from pathlib import Path

import pytest

from perpfut.exchange_coinbase import (
    CoinbaseExchangeError,
    parse_candles,
    parse_perpetual_products,
    parse_ticker,
)


FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "coinbase"


def _load_fixture(name: str) -> dict:
    return json.loads((FIXTURES_DIR / name).read_text(encoding="utf-8"))


def test_parse_perpetual_products_uses_fixture_shape() -> None:
    payload = _load_fixture("public_products_perpetuals.json")

    products = parse_perpetual_products(payload)

    assert [product.product_id for product in products] == ["SOL-PERP-INTX", "BTC-PERP-INTX"]
    assert products[0].price == 89.7055
    assert products[1].max_leverage == 50.0


def test_parse_perpetual_products_falls_back_to_price_when_mid_market_missing() -> None:
    payload = _load_fixture("public_products_perpetuals.json")
    payload["products"][0]["mid_market_price"] = ""

    products = parse_perpetual_products(payload)

    assert products[0].price == 89.705


def test_parse_perpetual_products_raises_on_missing_products_list() -> None:
    with pytest.raises(CoinbaseExchangeError, match="products payload is missing"):
        parse_perpetual_products({})


def test_parse_candles_sorts_fixture_from_oldest_to_newest() -> None:
    payload = _load_fixture("public_candles_btc_perp_1m.json")

    candles = parse_candles(payload, product_id="BTC-PERP-INTX")

    assert [candle.start.timestamp() for candle in candles] == sorted(
        candle.start.timestamp() for candle in candles
    )
    assert candles[0].close == 70267.6
    assert candles[-1].close == 70240.0


def test_parse_candles_raises_on_empty_payload() -> None:
    with pytest.raises(CoinbaseExchangeError, match="no candles returned"):
        parse_candles({"candles": []}, product_id="BTC-PERP-INTX")


def test_parse_ticker_uses_fixture_trade_and_quotes() -> None:
    payload = _load_fixture("public_ticker_btc_perp.json")

    ticker = parse_ticker(payload, product_id="BTC-PERP-INTX")

    assert ticker.last_price == 70218.6
    assert ticker.best_bid == 70218.5
    assert ticker.best_ask == 70218.6


def test_parse_ticker_raises_when_trades_missing() -> None:
    with pytest.raises(CoinbaseExchangeError, match="no trades returned"):
        parse_ticker({"trades": []}, product_id="BTC-PERP-INTX")
