import json
from pathlib import Path

from perpfut.analysis import analyze_run


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_ndjson(path: Path, items: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(item) for item in items) + "\n", encoding="utf-8")


def test_analyze_run_computes_canonical_metrics_for_paper_artifacts(tmp_path) -> None:
    run_dir = tmp_path / "20260322T020000000000Z_demo"
    run_dir.mkdir(parents=True)
    _write_json(
        run_dir / "manifest.json",
        {
            "run_id": run_dir.name,
            "created_at": "2026-03-22T02:00:00Z",
            "mode": "paper",
            "product_id": "BTC-PERP-INTX",
        },
    )
    _write_json(
        run_dir / "config.json",
        {
            "simulation": {
                "starting_collateral_usdc": 10000.0,
                "max_leverage": 2.0,
            }
        },
    )
    _write_ndjson(
        run_dir / "positions.ndjson",
        [
            {
                "cycle_id": "cycle-0001",
                "position": {
                    "quantity": 0.0,
                    "entry_price": None,
                    "mark_price": 100.0,
                    "collateral_usdc": 10000.0,
                    "realized_pnl_usdc": 0.0,
                },
            },
            {
                "cycle_id": "cycle-0002",
                "position": {
                    "quantity": 1.0,
                    "entry_price": 100.0,
                    "mark_price": 90.0,
                    "collateral_usdc": 10000.0,
                    "realized_pnl_usdc": 0.0,
                },
            },
            {
                "cycle_id": "cycle-0003",
                "position": {
                    "quantity": 1.0,
                    "entry_price": 100.0,
                    "mark_price": 115.0,
                    "collateral_usdc": 10000.0,
                    "realized_pnl_usdc": 50.0,
                },
            },
        ],
    )
    _write_ndjson(
        run_dir / "fills.ndjson",
        [
            {"fill": {"quantity": 1.0, "price": 100.0}},
            {"fill": {"quantity": 0.5, "price": 110.0}},
        ],
    )
    _write_ndjson(
        run_dir / "events.ndjson",
        [
            {"cycle_id": "cycle-0001", "timestamp": "2026-03-22T02:01:00Z", "execution_summary": {"reason_code": "below_rebalance_threshold"}},
            {"cycle_id": "cycle-0002", "timestamp": "2026-03-22T02:02:00Z", "execution_summary": {"reason_code": "filled"}},
            {"cycle_id": "cycle-0003", "timestamp": "2026-03-22T02:03:00Z", "execution_summary": {"reason_code": "filled"}},
        ],
    )
    _write_json(
        run_dir / "state.json",
        {
            "run_id": run_dir.name,
            "cycle_id": "cycle-0003",
            "position": {
                "quantity": 1.0,
                "entry_price": 100.0,
                "mark_price": 115.0,
                "collateral_usdc": 10000.0,
                "realized_pnl_usdc": 50.0,
            },
        },
    )

    analysis = analyze_run(run_dir)

    assert analysis.run_id == run_dir.name
    assert analysis.mode == "paper"
    assert analysis.starting_equity_usdc == 10000.0
    assert analysis.ending_equity_usdc == 10065.0
    assert analysis.total_pnl_usdc == 65.0
    assert analysis.turnover_usdc == 155.0
    assert analysis.fill_count == 2
    assert analysis.trade_count == 2
    assert analysis.decision_counts == {"below_rebalance_threshold": 1, "filled": 2}
    assert analysis.max_drawdown_usdc == 10.0
    assert analysis.max_drawdown_pct == 0.001
    assert round(analysis.avg_abs_exposure_pct, 4) == round((0.0 + 0.0045 + 0.00575) / 3, 4)


def test_analyze_run_uses_live_state_fallbacks_when_positions_and_fills_are_absent(tmp_path) -> None:
    run_dir = tmp_path / "20260322T020000000000Z_live"
    run_dir.mkdir(parents=True)
    _write_json(
        run_dir / "manifest.json",
        {
            "run_id": run_dir.name,
            "created_at": "2026-03-22T02:00:00Z",
            "mode": "live",
            "product_id": "BTC-PERP-INTX",
        },
    )
    _write_json(
        run_dir / "config.json",
        {
            "simulation": {
                "starting_collateral_usdc": 10000.0,
                "max_leverage": 2.0,
            }
        },
    )
    _write_json(
        run_dir / "state.json",
        {
            "run_id": run_dir.name,
            "cycle_id": "cycle-0001",
            "current_position": 0.2,
            "execution_summary": {"reason_code": "filled"},
            "exchange_snapshot": {
                "as_of": "2026-03-22T02:05:00Z",
                "summary": {
                    "total_balance": {"value": 10125.0},
                    "unrealized_pnl": {"value": 25.0},
                },
            },
        },
    )
    _write_ndjson(
        run_dir / "events.ndjson",
        [
            {"event_type": "reconciliation", "cycle_id": "cycle-0001"},
            {"event_type": "order_preview", "cycle_id": "cycle-0001"},
            {
                "event_type": "order_fill",
                "cycle_id": "cycle-0001",
                "fills": [
                    {"size": 0.1, "price": 100.0},
                    {"size": 0.05, "price": 110.0},
                ],
                "execution_summary": {"reason_code": "filled"},
            }
        ],
    )

    analysis = analyze_run(run_dir)

    assert analysis.mode == "live"
    assert analysis.cycle_count == 1
    assert analysis.starting_equity_usdc == 10000.0
    assert analysis.ending_equity_usdc == 10125.0
    assert analysis.total_pnl_usdc == 125.0
    assert analysis.total_return_pct == 0.0125
    assert analysis.unrealized_pnl_usdc == 25.0
    assert analysis.fill_count == 2
    assert analysis.turnover_usdc == 15.5
    assert analysis.avg_abs_exposure_pct == 0.2
    assert analysis.decision_counts == {"filled": 1}


def test_analyze_run_prepends_configured_start_for_single_snapshot_positions(tmp_path) -> None:
    run_dir = tmp_path / "20260322T020000000000Z_single"
    run_dir.mkdir(parents=True)
    _write_json(
        run_dir / "manifest.json",
        {
            "run_id": run_dir.name,
            "created_at": "2026-03-22T02:00:00Z",
            "mode": "paper",
            "product_id": "BTC-PERP-INTX",
        },
    )
    _write_json(
        run_dir / "config.json",
        {
            "simulation": {
                "starting_collateral_usdc": 10000.0,
                "max_leverage": 2.0,
            }
        },
    )
    _write_ndjson(
        run_dir / "positions.ndjson",
        [
            {
                "cycle_id": "cycle-0001",
                "position": {
                    "quantity": 0.5,
                    "entry_price": 100.0,
                    "mark_price": 110.0,
                    "collateral_usdc": 10000.0,
                    "realized_pnl_usdc": 20.0,
                },
            },
        ],
    )
    _write_ndjson(
        run_dir / "events.ndjson",
        [
            {"cycle_id": "cycle-0001", "timestamp": "2026-03-22T02:01:00Z", "execution_summary": {"reason_code": "filled"}},
        ],
    )
    _write_json(
        run_dir / "state.json",
        {
            "run_id": run_dir.name,
            "cycle_id": "cycle-0001",
            "position": {
                "quantity": 0.5,
                "entry_price": 100.0,
                "mark_price": 110.0,
                "collateral_usdc": 10000.0,
                "realized_pnl_usdc": 20.0,
            },
        },
    )

    analysis = analyze_run(run_dir)

    assert analysis.starting_equity_usdc == 10000.0
    assert analysis.ending_equity_usdc == 10025.0
    assert analysis.total_pnl_usdc == 25.0
    assert analysis.total_return_pct == 0.0025
    assert [point.label for point in analysis.equity_series] == ["start", "cycle-0001"]
