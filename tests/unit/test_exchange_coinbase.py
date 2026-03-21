import json
from pathlib import Path

import pytest

from perpfut.exchange_coinbase import (
    CoinbaseExchangeError,
    parse_public_candles,
    parse_public_market_snapshot,
    parse_public_products,
)


FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "coinbase"


def _load_fixture(name: str) -> dict:
    return json.loads((FIXTURES_DIR / name).read_text(encoding="utf-8"))


def test_parse_public_products_from_real_fixture() -> None:
    payload = _load_fixture("public_products_btc_perp.json")

    products = parse_public_products(payload)

    assert [product.product_id for product in products] == ["SOL-PERP-INTX", "BTC-PERP-INTX"]
    assert products[0].funding_rate == pytest.approx(-0.000013)
    assert products[1].max_leverage == pytest.approx(50.0)


def test_parse_public_candles_sorts_exchange_order() -> None:
    payload = _load_fixture("public_candles_btc_perp.json")

    candles = parse_public_candles(payload)

    assert [candle.start.isoformat() for candle in candles] == [
        "2026-03-21T23:04:00+00:00",
        "2026-03-21T23:05:00+00:00",
        "2026-03-21T23:06:00+00:00",
    ]
    assert candles[-1].close == pytest.approx(70224.0)


def test_parse_public_market_snapshot_from_real_fixtures() -> None:
    candles = parse_public_candles(_load_fixture("public_candles_btc_perp.json"))
    ticker_payload = _load_fixture("public_ticker_btc_perp.json")

    market = parse_public_market_snapshot(
        product_id="BTC-PERP-INTX",
        candles=candles,
        ticker_payload=ticker_payload,
    )

    assert market.product_id == "BTC-PERP-INTX"
    assert market.last_price == pytest.approx(70224.1)
    assert market.mid_price == pytest.approx(70224.15)
    assert market.as_of.isoformat() == "2026-03-21T23:07:02.716603+00:00"


def test_parse_public_products_rejects_missing_product_id() -> None:
    with pytest.raises(CoinbaseExchangeError, match="missing string field product_id"):
        parse_public_products({"products": [{"display_name": "broken"}]})


def test_parse_public_candles_rejects_empty_payload() -> None:
    with pytest.raises(CoinbaseExchangeError, match="contained no candles"):
        parse_public_candles({"candles": []})


def test_parse_public_market_snapshot_rejects_missing_trades() -> None:
    candles = parse_public_candles(_load_fixture("public_candles_btc_perp.json"))

    with pytest.raises(CoinbaseExchangeError, match="contained no trades"):
        parse_public_market_snapshot(
            product_id="BTC-PERP-INTX",
            candles=candles,
            ticker_payload={"best_bid": "1", "best_ask": "2", "trades": []},
        )
