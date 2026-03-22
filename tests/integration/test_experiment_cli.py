import json
from pathlib import Path

from perpfut.cli import main


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_ndjson(path: Path, items: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(item) for item in items) + "\n", encoding="utf-8")


def _market_snapshot(timestamp: str, closes: tuple[float, float, float]) -> dict:
    candles = []
    for index, close in enumerate(closes):
        candles.append(
            {
                "start": f"2026-03-22T02:0{index}:00Z",
                "low": close - 1.0,
                "high": close + 1.0,
                "open": close - 0.5,
                "close": close,
                "volume": 10.0 + index,
            }
        )
    return {
        "product_id": "BTC-PERP-INTX",
        "as_of": timestamp,
        "last_price": closes[-1],
        "best_bid": closes[-1] - 0.5,
        "best_ask": closes[-1] + 0.5,
        "candles": candles,
    }


def test_experiment_cli_replays_source_run_and_persists_analysis(tmp_path, capsys) -> None:
    source_run_id = "20260322T020000000000Z_source"
    source_run_dir = tmp_path / source_run_id
    source_run_dir.mkdir(parents=True)
    _write_json(
        source_run_dir / "manifest.json",
        {
            "run_id": source_run_id,
            "created_at": "2026-03-22T02:00:00Z",
            "mode": "paper",
            "product_id": "BTC-PERP-INTX",
            "strategy_id": "momentum",
        },
    )
    _write_json(
        source_run_dir / "config.json",
        {
            "strategy": {
                "strategy_id": "momentum",
                "lookback_candles": 3,
                "signal_scale": 15.0,
            },
            "risk": {
                "max_abs_position": 0.5,
                "rebalance_threshold": 0.05,
                "min_trade_notional_usdc": 10.0,
                "max_daily_drawdown_usdc": 250.0,
            },
            "simulation": {
                "starting_collateral_usdc": 10000.0,
                "max_leverage": 2.0,
                "slippage_bps": 3.0,
            },
        },
    )
    _write_ndjson(
        source_run_dir / "events.ndjson",
        [
            {
                "event_type": "cycle",
                "cycle_id": "cycle-0001",
                "timestamp": "2026-03-22T02:01:00Z",
                "market": _market_snapshot("2026-03-22T02:01:00Z", (100.0, 104.0, 108.0)),
            },
            {
                "event_type": "cycle",
                "cycle_id": "cycle-0002",
                "timestamp": "2026-03-22T02:02:00Z",
                "market": _market_snapshot("2026-03-22T02:02:00Z", (108.0, 106.0, 102.0)),
            },
        ],
    )
    _write_json(
        source_run_dir / "state.json",
        {
            "run_id": source_run_id,
            "cycle_id": "cycle-0002",
            "mode": "paper",
            "position": {
                "quantity": 0.0,
                "entry_price": None,
                "mark_price": 102.0,
                "collateral_usdc": 10000.0,
                "realized_pnl_usdc": 0.0,
            },
        },
    )

    exit_code = main(
        [
            "experiment",
            "--runs-dir",
            str(tmp_path),
            "--source-run-id",
            source_run_id,
            "--strategy-id",
            "mean_reversion",
        ]
    )

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    experiment_run_dir = tmp_path / "experiments" / payload["run_id"]
    assert payload["source_run_id"] == source_run_id
    assert payload["strategy_id"] == "mean_reversion"
    assert experiment_run_dir.exists()

    manifest = json.loads((experiment_run_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["source_run_id"] == source_run_id
    assert manifest["strategy_id"] == "mean_reversion"
    assert manifest["analysis_path"] == "analysis.json"
    assert manifest["strategy_params"] == {
        "lookback_candles": 3,
        "signal_scale": 15.0,
    }
    assert "generated_at" in manifest

    analysis = json.loads((experiment_run_dir / "analysis.json").read_text(encoding="utf-8"))
    assert analysis["run_id"] == payload["run_id"]
    assert analysis["strategy_id"] == "mean_reversion"
    assert analysis["cycle_count"] == 2
    assert (experiment_run_dir / "events.ndjson").exists()
    assert (experiment_run_dir / "fills.ndjson").exists()
    assert (experiment_run_dir / "positions.ndjson").exists()
    assert (experiment_run_dir / "state.json").exists()


def test_experiment_cli_exits_cleanly_when_source_run_has_no_replay_snapshots(tmp_path) -> None:
    source_run_id = "20260322T020000000000Z_source"
    source_run_dir = tmp_path / source_run_id
    source_run_dir.mkdir(parents=True)
    _write_json(
        source_run_dir / "manifest.json",
        {
            "run_id": source_run_id,
            "created_at": "2026-03-22T02:00:00Z",
            "mode": "paper",
            "product_id": "BTC-PERP-INTX",
        },
    )
    _write_json(
        source_run_dir / "state.json",
        {
            "run_id": source_run_id,
            "cycle_id": "cycle-0001",
            "mode": "paper",
        },
    )
    (source_run_dir / "events.ndjson").write_text("", encoding="utf-8")

    try:
        main(
            [
                "experiment",
                "--runs-dir",
                str(tmp_path),
                "--source-run-id",
                source_run_id,
                "--strategy-id",
                "momentum",
            ]
        )
    except SystemExit as exc:
        assert str(exc) == f"source run has no replayable market snapshots: {source_run_id}"
    else:
        raise AssertionError("expected SystemExit")


def test_compare_experiments_cli_ranks_candidates_for_a_source_run(tmp_path, capsys) -> None:
    source_run_id = "20260322T020000000000Z_source"
    source_run_dir = tmp_path / source_run_id
    source_run_dir.mkdir(parents=True)
    _write_json(
        source_run_dir / "manifest.json",
        {
            "run_id": source_run_id,
            "created_at": "2026-03-22T02:00:00Z",
            "mode": "paper",
            "product_id": "BTC-PERP-INTX",
            "strategy_id": "momentum",
        },
    )
    _write_json(
        source_run_dir / "config.json",
        {
            "simulation": {
                "starting_collateral_usdc": 10000.0,
                "max_leverage": 2.0,
            },
            "strategy": {
                "strategy_id": "momentum",
            },
        },
    )
    _write_json(
        source_run_dir / "state.json",
        {
            "run_id": source_run_id,
            "cycle_id": "cycle-0002",
            "mode": "paper",
            "position": {
                "quantity": 0.0,
                "entry_price": None,
                "mark_price": 102.0,
                "collateral_usdc": 10000.0,
                "realized_pnl_usdc": 50.0,
            },
        },
    )
    _write_ndjson(
        source_run_dir / "events.ndjson",
        [
            {
                "event_type": "cycle",
                "cycle_id": "cycle-0001",
                "timestamp": "2026-03-22T02:01:00Z",
                "execution_summary": {"reason_code": "filled"},
            },
        ],
    )

    experiments_dir = tmp_path / "experiments"
    alpha = experiments_dir / "20260322T030000000000Z_alpha"
    alpha.mkdir(parents=True)
    _write_json(
        alpha / "manifest.json",
        {
            "run_id": alpha.name,
            "mode": "paper",
            "product_id": "BTC-PERP-INTX",
            "strategy_id": "momentum",
            "source_run_id": source_run_id,
            "strategy_params": {"lookback_candles": 3, "signal_scale": 10.0},
        },
    )
    _write_json(
        alpha / "analysis.json",
        {
            "run_id": alpha.name,
            "strategy_id": "momentum",
            "total_pnl_usdc": 90.0,
            "total_return_pct": 0.009,
            "max_drawdown_usdc": 30.0,
            "max_drawdown_pct": 0.003,
            "turnover_usdc": 400.0,
            "fill_count": 3,
            "avg_abs_exposure_pct": 0.10,
            "max_abs_exposure_pct": 0.20,
            "decision_counts": {"filled": 2},
        },
    )

    beta = experiments_dir / "20260322T031000000000Z_beta"
    beta.mkdir(parents=True)
    _write_json(
        beta / "manifest.json",
        {
            "run_id": beta.name,
            "mode": "paper",
            "product_id": "BTC-PERP-INTX",
            "strategy_id": "mean_reversion",
            "source_run_id": source_run_id,
            "strategy_params": {"lookback_candles": 5, "signal_scale": 12.0},
        },
    )
    _write_json(
        beta / "analysis.json",
        {
            "run_id": beta.name,
            "strategy_id": "mean_reversion",
            "total_pnl_usdc": 140.0,
            "total_return_pct": 0.014,
            "max_drawdown_usdc": 20.0,
            "max_drawdown_pct": 0.002,
            "turnover_usdc": 350.0,
            "fill_count": 2,
            "avg_abs_exposure_pct": 0.09,
            "max_abs_exposure_pct": 0.18,
            "decision_counts": {"filled": 2},
        },
    )

    exit_code = main(
        [
            "compare-experiments",
            "--runs-dir",
            str(tmp_path),
            "--source-run-id",
            source_run_id,
        ]
    )

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["source_run_id"] == source_run_id
    assert payload["experiments_count"] == 2
    assert payload["baseline"]["run_id"] == source_run_id
    assert payload["items"][0]["rank"] == 1
    assert payload["items"][0]["run_id"] == beta.name
    assert payload["items"][0]["strategy_id"] == "mean_reversion"
    assert payload["items"][1]["rank"] == 2
    assert payload["items"][1]["run_id"] == alpha.name


def test_compare_experiments_cli_exits_cleanly_when_no_candidates_exist(tmp_path) -> None:
    source_run_id = "20260322T020000000000Z_source"
    source_run_dir = tmp_path / source_run_id
    source_run_dir.mkdir(parents=True)
    _write_json(
        source_run_dir / "manifest.json",
        {
            "run_id": source_run_id,
            "created_at": "2026-03-22T02:00:00Z",
            "mode": "paper",
            "product_id": "BTC-PERP-INTX",
        },
    )
    _write_json(source_run_dir / "state.json", {"run_id": source_run_id})

    try:
        main(
            [
                "compare-experiments",
                "--runs-dir",
                str(tmp_path),
                "--source-run-id",
                source_run_id,
            ]
        )
    except SystemExit as exc:
        assert str(exc) == f"no experiments found for source run: {source_run_id}"
    else:
        raise AssertionError("expected SystemExit")


def test_compare_experiments_cli_prefers_canonical_artifacts_over_stale_analysis_json(
    tmp_path,
    capsys,
) -> None:
    source_run_id = "20260322T020000000000Z_source"
    source_run_dir = tmp_path / source_run_id
    source_run_dir.mkdir(parents=True)
    _write_json(
        source_run_dir / "manifest.json",
        {
            "run_id": source_run_id,
            "created_at": "2026-03-22T02:00:00Z",
            "mode": "paper",
            "product_id": "BTC-PERP-INTX",
            "strategy_id": "momentum",
        },
    )
    _write_json(
        source_run_dir / "config.json",
        {
            "simulation": {
                "starting_collateral_usdc": 10000.0,
                "max_leverage": 2.0,
            }
        },
    )
    _write_json(
        source_run_dir / "state.json",
        {
            "run_id": source_run_id,
            "cycle_id": "cycle-0001",
            "mode": "paper",
            "position": {
                "quantity": 0.0,
                "entry_price": None,
                "mark_price": 100.0,
                "collateral_usdc": 10000.0,
                "realized_pnl_usdc": 0.0,
            },
        },
    )
    _write_ndjson(
        source_run_dir / "events.ndjson",
        [{"cycle_id": "cycle-0001", "timestamp": "2026-03-22T02:01:00Z"}],
    )

    experiment_run = tmp_path / "experiments" / "20260322T030000000000Z_alpha"
    experiment_run.mkdir(parents=True)
    _write_json(
        experiment_run / "manifest.json",
        {
            "run_id": experiment_run.name,
            "mode": "paper",
            "product_id": "BTC-PERP-INTX",
            "strategy_id": "momentum",
            "source_run_id": source_run_id,
            "strategy_params": {"lookback_candles": 3, "signal_scale": 10.0},
        },
    )
    _write_json(
        experiment_run / "config.json",
        {
            "simulation": {
                "starting_collateral_usdc": 10000.0,
                "max_leverage": 2.0,
            },
            "strategy": {
                "strategy_id": "momentum",
            },
        },
    )
    _write_ndjson(
        experiment_run / "positions.ndjson",
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
            }
        ],
    )
    _write_ndjson(
        experiment_run / "events.ndjson",
        [
            {
                "event_type": "cycle",
                "cycle_id": "cycle-0001",
                "timestamp": "2026-03-22T03:01:00Z",
                "execution_summary": {"reason_code": "filled"},
            }
        ],
    )
    _write_json(
        experiment_run / "state.json",
        {
            "run_id": experiment_run.name,
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
    _write_json(
        experiment_run / "analysis.json",
        {
            "run_id": experiment_run.name,
            "strategy_id": "momentum",
            "total_pnl_usdc": 999.0,
            "total_return_pct": 0.999,
            "max_drawdown_usdc": 0.0,
            "max_drawdown_pct": 0.0,
            "turnover_usdc": 0.0,
            "fill_count": 0,
            "avg_abs_exposure_pct": 0.0,
            "max_abs_exposure_pct": 0.0,
            "decision_counts": {},
        },
    )

    exit_code = main(
        [
            "compare-experiments",
            "--runs-dir",
            str(tmp_path),
            "--source-run-id",
            source_run_id,
        ]
    )

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["items"][0]["total_pnl_usdc"] == 25.0
    assert payload["items"][0]["total_return_pct"] == 0.0025


def test_compare_experiments_cli_skips_malformed_candidate_manifests(tmp_path, capsys) -> None:
    source_run_id = "20260322T020000000000Z_source"
    source_run_dir = tmp_path / source_run_id
    source_run_dir.mkdir(parents=True)
    _write_json(
        source_run_dir / "manifest.json",
        {
            "run_id": source_run_id,
            "created_at": "2026-03-22T02:00:00Z",
            "mode": "paper",
            "product_id": "BTC-PERP-INTX",
        },
    )
    _write_json(source_run_dir / "state.json", {"run_id": source_run_id})

    valid_run = tmp_path / "experiments" / "20260322T030000000000Z_valid"
    valid_run.mkdir(parents=True)
    _write_json(
        valid_run / "manifest.json",
        {
            "run_id": valid_run.name,
            "mode": "paper",
            "product_id": "BTC-PERP-INTX",
            "strategy_id": "momentum",
            "source_run_id": source_run_id,
            "strategy_params": {"lookback_candles": 3, "signal_scale": 10.0},
        },
    )
    _write_json(
        valid_run / "analysis.json",
        {
            "run_id": valid_run.name,
            "strategy_id": "momentum",
            "total_pnl_usdc": 90.0,
            "total_return_pct": 0.009,
            "max_drawdown_usdc": 30.0,
            "max_drawdown_pct": 0.003,
            "turnover_usdc": 400.0,
            "fill_count": 3,
            "avg_abs_exposure_pct": 0.10,
            "max_abs_exposure_pct": 0.20,
            "decision_counts": {"filled": 2},
        },
    )

    malformed_run = tmp_path / "experiments" / "20260322T031000000000Z_broken"
    malformed_run.mkdir(parents=True)
    (malformed_run / "manifest.json").write_text("[]", encoding="utf-8")

    exit_code = main(
        [
            "compare-experiments",
            "--runs-dir",
            str(tmp_path),
            "--source-run-id",
            source_run_id,
        ]
    )

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["experiments_count"] == 1
    assert payload["items"][0]["run_id"] == valid_run.name
