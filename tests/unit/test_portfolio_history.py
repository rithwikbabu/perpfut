import json

from perpfut.portfolio_history import compare_portfolio_runs, list_portfolio_runs, load_portfolio_run


def _write_json(path, payload) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def _make_portfolio_run(tmp_path, run_id: str, *, sharpe: float, return_pct: float) -> None:
    run_dir = tmp_path / "backtests" / "portfolio-runs" / run_id
    run_dir.mkdir(parents=True)
    _write_json(
        run_dir / "manifest.json",
        {
            "run_id": run_id,
            "created_at": f"{run_id}-created",
            "dataset_id": "dataset-1",
        },
    )
    _write_json(run_dir / "config.json", {"optimizer": {"lookback_days": 60}})
    _write_json(run_dir / "state.json", {"run_id": run_id, "ending_equity_usdc": 10100.0})
    _write_json(
        run_dir / "analysis.json",
        {
            "run_id": run_id,
            "dataset_id": "dataset-1",
            "dataset_fingerprint": "fp-1",
            "dataset_source": "coinbase",
            "dataset_version": "1",
            "date_range_start": "2026-03-20T00:00:00+00:00",
            "date_range_end": "2026-03-21T00:00:00+00:00",
            "created_at": f"{run_id}-created",
            "starting_capital_usdc": 10000.0,
            "ending_equity_usdc": 10000.0 * (1.0 + return_pct),
            "total_pnl_usdc": 10000.0 * return_pct,
            "total_return_pct": return_pct,
            "sharpe_ratio": sharpe,
            "max_drawdown_usdc": 25.0,
            "max_drawdown_pct": 0.01,
            "total_turnover_usdc": 500.0,
            "transaction_cost_total_usdc": 5.0,
            "avg_gross_weight": 0.5,
            "max_gross_weight": 0.8,
            "strategy_instance_ids": ["mom-a"],
            "sleeve_run_ids": ["sleeve-run-1"],
            "equity_series": [{"label": "2026-03-20", "value": 10100.0}],
            "drawdown_series": [{"label": "2026-03-20", "value": 0.0}],
            "gross_return_series": [{"label": "2026-03-20", "value": return_pct}],
            "net_return_series": [{"label": "2026-03-20", "value": return_pct}],
            "turnover_series_usdc": [{"label": "2026-03-20", "value": 500.0}],
            "transaction_cost_series_usdc": [{"label": "2026-03-20", "value": 5.0}],
            "gross_weight_series": [{"label": "2026-03-20", "value": 0.5}],
            "contribution_totals_usdc": {"mom-a": 100.0},
        },
    )
    (run_dir / "weights.ndjson").write_text(
        json.dumps(
            {
                "date": "2026-03-20",
                "weights": {"mom-a": 0.5},
                "cash_weight": 0.5,
                "turnover": 0.5,
                "gross_weight": 0.5,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (run_dir / "diagnostics.ndjson").write_text(
        json.dumps(
            {
                "date": "2026-03-20",
                "expected_returns": {"mom-a": 0.01},
                "covariance_matrix": {"mom-a": {"mom-a": 0.001}},
                "constraint_status": "optimized",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    _write_json(
        run_dir / "contributions.json",
        {
            "items": [
                {
                    "strategy_instance_id": "mom-a",
                    "strategy_id": "momentum",
                    "sleeve_run_id": "sleeve-run-1",
                    "total_gross_pnl_usdc": 100.0,
                    "daily_gross_pnl_series": [{"label": "2026-03-20", "value": 100.0}],
                }
            ],
            "transaction_cost_total_usdc": 5.0,
            "transaction_cost_series_usdc": [{"label": "2026-03-20", "value": 5.0}],
        },
    )


def test_portfolio_history_lists_loads_and_compares_runs(tmp_path) -> None:
    _make_portfolio_run(tmp_path, "run-b", sharpe=1.0, return_pct=0.02)
    _make_portfolio_run(tmp_path, "run-a", sharpe=1.5, return_pct=0.01)
    malformed_dir = tmp_path / "backtests" / "portfolio-runs" / "run-bad"
    malformed_dir.mkdir(parents=True)
    (malformed_dir / "manifest.json").write_text("[]", encoding="utf-8")

    items = list_portfolio_runs(tmp_path, limit=10)
    detail = load_portfolio_run(tmp_path, run_id="run-a")
    comparison = compare_portfolio_runs(tmp_path, limit=10)

    assert [item.run_id for item in items] == ["run-b", "run-a"]
    assert detail["analysis"]["run_id"] == "run-a"
    assert comparison.items[0].run_id == "run-a"
    assert comparison.items[0].rank == 1


def test_portfolio_history_keeps_zero_sharpe_above_negative_sharpe(tmp_path) -> None:
    _make_portfolio_run(tmp_path, "run-zero", sharpe=0.0, return_pct=0.01)
    _make_portfolio_run(tmp_path, "run-negative", sharpe=-0.5, return_pct=0.10)

    comparison = compare_portfolio_runs(tmp_path, limit=10)

    assert [item.run_id for item in comparison.items] == ["run-zero", "run-negative"]
