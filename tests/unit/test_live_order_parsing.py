import json
from pathlib import Path

from perpfut.exchange_coinbase import (
    parse_cancel_results,
    parse_order_preview,
    parse_order_status,
    parse_order_submission,
)


FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "coinbase"


def _load_fixture(name: str) -> dict:
    return json.loads((FIXTURES_DIR / name).read_text(encoding="utf-8"))


def test_parse_order_preview_fixture() -> None:
    preview = parse_order_preview(
        _load_fixture("order_preview_success.json"),
        product_id="BTC-PERP-INTX",
        side="BUY",
    )

    assert preview.preview_id == "preview-123"
    assert preview.order_total == 3505.0
    assert preview.errs == ()


def test_parse_order_submission_fixture() -> None:
    submission = parse_order_submission(
        _load_fixture("order_create_success.json"),
        product_id="BTC-PERP-INTX",
        side="BUY",
        client_order_id="client-123",
    )

    assert submission.success is True
    assert submission.order_id == "order-123"
    assert submission.client_order_id == "client-123"


def test_parse_order_status_fixture() -> None:
    status = parse_order_status(_load_fixture("order_status_filled.json"))

    assert status.status == "FILLED"
    assert status.filled_size == 0.05
    assert status.average_filled_price == 70100.0


def test_parse_cancel_results_fixture() -> None:
    results = parse_cancel_results(_load_fixture("order_cancel_success.json"))

    assert len(results) == 1
    assert results[0].success is True
    assert results[0].order_id == "order-123"
