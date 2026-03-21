import json
from pathlib import Path

from perpfut.exchange_coinbase import (
    parse_intx_portfolio_summary,
    parse_intx_positions,
    parse_order_fills,
    parse_portfolio_balances,
)
from perpfut.reconciliation import reconcile_intx_state


FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "coinbase"


def _load_fixture(name: str) -> dict:
    return json.loads((FIXTURES_DIR / name).read_text(encoding="utf-8"))


def test_parse_private_intx_payloads_and_reconcile_current_position() -> None:
    summary = parse_intx_portfolio_summary(
        _load_fixture("intx_portfolio_summary.json"),
        portfolio_uuid="portfolio-123",
    )
    balances = parse_portfolio_balances(
        _load_fixture("intx_balances.json"),
        portfolio_uuid="portfolio-123",
    )
    positions = parse_intx_positions(
        _load_fixture("intx_positions.json"),
        portfolio_uuid="portfolio-123",
    )
    fills = parse_order_fills(_load_fixture("order_fills_btc_perp.json"))

    snapshot = reconcile_intx_state(
        portfolio_uuid="portfolio-123",
        summary=summary,
        balances=balances,
        positions=positions,
        fills=fills,
        product_id="BTC-PERP-INTX",
    )

    assert snapshot.summary.buying_power is not None
    assert snapshot.summary.buying_power.value == 14964.02
    assert snapshot.current_position is not None
    assert snapshot.current_position.product_id == "BTC-PERP-INTX"
    assert snapshot.current_position.position_notional is not None
    assert snapshot.current_position.position_notional.value == 17650.0
    assert len(snapshot.recent_fills) == 1
    assert snapshot.recent_fills[0].product_id == "BTC-PERP-INTX"
