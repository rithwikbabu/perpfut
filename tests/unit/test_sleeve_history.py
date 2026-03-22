import json

from perpfut.sleeve_history import compare_strategy_sleeves, list_strategy_sleeves, load_strategy_sleeve


def _write_json(path, payload) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def _make_strategy_sleeve(tmp_path, run_id: str, *, dataset_id: str, strategy_instance_id: str, return_pct: float) -> None:
    run_dir = tmp_path / "backtests" / "sleeves" / run_id
    run_dir.mkdir(parents=True)
    _write_json(
        run_dir / "manifest.json",
        {
            "run_id": run_id,
            "created_at": f"{run_id}-created",
            "dataset_id": dataset_id,
        },
    )
    _write_json(run_dir / "state.json", {"run_id": run_id, "ending_equity_usdc": 10_000.0 * (1.0 + return_pct)})
    _write_json(
        run_dir / "analysis.json",
        {
            "run_id": run_id,
            "mode": "backtest",
            "product_id": "MULTI_ASSET",
            "strategy_id": "momentum",
            "started_at": None,
            "ended_at": None,
            "date_range_start": "2026-03-20T00:00:00+00:00",
            "date_range_end": "2026-03-21T00:00:00+00:00",
            "sharpe_ratio": 1.0,
            "cycle_count": 2,
            "starting_equity_usdc": 10_000.0,
            "ending_equity_usdc": 10_000.0 * (1.0 + return_pct),
            "realized_pnl_usdc": 10_000.0 * return_pct,
            "unrealized_pnl_usdc": 0.0,
            "total_pnl_usdc": 10_000.0 * return_pct,
            "total_return_pct": return_pct,
            "max_drawdown_usdc": 25.0,
            "max_drawdown_pct": 0.01,
            "turnover_usdc": 500.0,
            "fill_count": 2,
            "trade_count": 2,
            "avg_abs_exposure_pct": 0.2,
            "max_abs_exposure_pct": 0.3,
            "decision_counts": {"filled": 2},
            "equity_series": [{"label": "2026-03-20", "value": 10_000.0 * (1.0 + return_pct)}],
            "drawdown_series": [{"label": "2026-03-20", "value": 25.0}],
            "exposure_series": [{"label": "2026-03-20", "value": 0.2}],
        },
    )
    _write_json(
        run_dir / "sleeve_analysis.json",
        {
            "run_id": run_id,
            "dataset_id": dataset_id,
            "strategy_instance_id": strategy_instance_id,
            "strategy_id": "momentum",
            "date_range_start": "2026-03-20T00:00:00+00:00",
            "date_range_end": "2026-03-21T00:00:00+00:00",
            "total_pnl_usdc": 10_000.0 * return_pct,
            "total_return_pct": return_pct,
            "max_drawdown_usdc": 25.0,
            "max_drawdown_pct": 0.01,
            "daily_turnover_usdc": [{"label": "2026-03-20", "value": 500.0}],
            "daily_avg_abs_exposure_pct": [{"label": "2026-03-20", "value": 0.2}],
            "asset_contributions": [
                {"product_id": "BTC-PERP-INTX", "total_pnl_usdc": 60.0},
                {"product_id": "ETH-PERP-INTX", "total_pnl_usdc": 40.0},
            ],
        },
    )


def test_sleeve_history_lists_loads_and_compares_runs(tmp_path) -> None:
    _make_strategy_sleeve(tmp_path, "sleeve-b", dataset_id="dataset-1", strategy_instance_id="mom-b", return_pct=0.02)
    _make_strategy_sleeve(tmp_path, "sleeve-a", dataset_id="dataset-1", strategy_instance_id="mom-a", return_pct=0.01)
    malformed_dir = tmp_path / "backtests" / "sleeves" / "sleeve-bad"
    malformed_dir.mkdir(parents=True)
    (malformed_dir / "manifest.json").write_text("[]", encoding="utf-8")

    items = list_strategy_sleeves(tmp_path, limit=10, dataset_id="dataset-1")
    detail = load_strategy_sleeve(tmp_path, run_id="sleeve-a")
    comparison = compare_strategy_sleeves(tmp_path, limit=10, dataset_id="dataset-1")

    assert [item.run_id for item in items] == ["sleeve-b", "sleeve-a"]
    assert detail["sleeve_analysis"]["strategy_instance_id"] == "mom-a"
    assert comparison.items[0].run_id == "sleeve-b"
    assert comparison.items[0].rank == 1
    assert comparison.items[0].asset_contribution_totals == {
        "BTC-PERP-INTX": 60.0,
        "ETH-PERP-INTX": 40.0,
    }

