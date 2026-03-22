import json
from pathlib import Path

from perpfut.backtest_history import compare_backtest_suite, list_backtest_runs, list_backtest_suites


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_ndjson(path: Path, items: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(item) for item in items) + "\n", encoding="utf-8")


def _make_run(
    base_dir: Path,
    run_id: str,
    *,
    suite_id: str,
    strategy_id: str,
    equities: list[float],
) -> None:
    run_dir = base_dir / "backtests" / "runs" / run_id
    _write_json(
        run_dir / "manifest.json",
        {
            "run_id": run_id,
            "created_at": f"{run_id}-created",
            "mode": "backtest",
            "product_id": "MULTI_ASSET",
            "dataset_id": "dataset-1",
            "suite_id": suite_id,
            "strategy_id": strategy_id,
            "date_range_start": "2026-03-20T00:00:00+00:00",
            "date_range_end": "2026-03-20T00:04:00+00:00",
            "granularity": "ONE_MINUTE",
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
    position_rows = []
    for index, equity in enumerate(equities, start=1):
        position_rows.append(
            {
                "cycle_id": f"cycle-{index:04d}",
                "position": {
                    "equity_usdc": equity,
                    "gross_notional_usdc": 1000.0 + index,
                },
            }
        )
    _write_ndjson(run_dir / "positions.ndjson", position_rows)
    _write_ndjson(
        run_dir / "fills.ndjson",
        [{"fill": {"quantity": 1.0, "price": 100.0}}],
    )
    _write_ndjson(
        run_dir / "events.ndjson",
        [
            {
                "cycle_id": row["cycle_id"],
                "timestamp": f"2026-03-20T00:0{index}:00+00:00",
                "execution_summary": {"reason_code": "filled"},
            }
            for index, row in enumerate(position_rows, start=1)
        ],
    )
    _write_json(
        run_dir / "state.json",
        {
            "run_id": run_id,
            "cycle_id": position_rows[-1]["cycle_id"],
            "position": position_rows[-1]["position"],
        },
    )


def test_backtest_history_surfaces_date_range_and_sharpe_fields(tmp_path) -> None:
    suite_id = "suite-1"
    _make_run(tmp_path, "run-2", suite_id=suite_id, strategy_id="momentum", equities=[10100.0, 10000.0, 10200.0])
    _make_run(tmp_path, "run-1", suite_id=suite_id, strategy_id="mean_reversion", equities=[10050.0, 10025.0, 10075.0])
    _write_json(
        tmp_path / "backtests" / "suites" / suite_id / "manifest.json",
        {
            "suite_id": suite_id,
            "created_at": "suite-created",
            "dataset_id": "dataset-1",
            "products": ["BTC-PERP-INTX", "ETH-PERP-INTX"],
            "strategies": ["momentum", "mean_reversion"],
            "run_ids": ["run-2", "run-1"],
            "date_range_start": "2026-03-20T00:00:00+00:00",
            "date_range_end": "2026-03-20T00:04:00+00:00",
            "granularity": "ONE_MINUTE",
        },
    )

    run_summaries = list_backtest_runs(tmp_path, limit=5)
    suite_summaries = list_backtest_suites(tmp_path, limit=5)
    comparison = compare_backtest_suite(tmp_path, suite_id=suite_id)

    assert run_summaries[0].date_range_start == "2026-03-20T00:00:00+00:00"
    assert run_summaries[0].date_range_end == "2026-03-20T00:04:00+00:00"
    assert run_summaries[0].sharpe_ratio is not None
    assert suite_summaries[0].date_range_start == "2026-03-20T00:00:00+00:00"
    assert suite_summaries[0].date_range_end == "2026-03-20T00:04:00+00:00"
    assert suite_summaries[0].sharpe_ratio == comparison.items[0].sharpe_ratio
    assert comparison.items[0].date_range_start == "2026-03-20T00:00:00+00:00"
    assert comparison.items[0].date_range_end == "2026-03-20T00:04:00+00:00"
    assert comparison.items[0].sharpe_ratio is not None
