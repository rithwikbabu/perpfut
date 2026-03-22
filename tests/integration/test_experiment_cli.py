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
