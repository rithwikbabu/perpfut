import json

from perpfut.cli import build_parser, main


def test_api_parser_defaults() -> None:
    parser = build_parser()

    args = parser.parse_args(["api"])

    assert args.command == "api"
    assert args.host == "127.0.0.1"
    assert args.port == 8000


def test_api_main_invokes_server(monkeypatch) -> None:
    captured = {}

    def fake_run_api_server(*, host: str, port: int) -> None:
        captured["host"] = host
        captured["port"] = port

    monkeypatch.setattr("perpfut.cli.run_api_server", fake_run_api_server)

    exit_code = main(["api", "--host", "127.0.0.1", "--port", "9000"])

    assert exit_code == 0
    assert captured == {"host": "127.0.0.1", "port": 9000}


def test_analyze_parser_defaults() -> None:
    parser = build_parser()

    args = parser.parse_args(["analyze"])

    assert args.command == "analyze"
    assert args.run_id is None
    assert args.mode == "paper"


def test_analyze_main_prints_run_analysis(monkeypatch, tmp_path, capsys) -> None:
    run_id = "20260322T020000000000Z_beta"
    run_dir = tmp_path / run_id
    run_dir.mkdir(parents=True)
    (run_dir / "manifest.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "created_at": "2026-03-21T01:00:00Z",
                "mode": "paper",
                "product_id": "BTC-PERP-INTX",
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "config.json").write_text(
        json.dumps(
            {
                "simulation": {
                    "starting_collateral_usdc": 10_000.0,
                    "max_leverage": 2.0,
                },
                "strategy": {
                    "strategy_id": "momentum",
                },
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "state.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "cycle_id": "cycle-0001",
                "mode": "paper",
                "position": {
                    "collateral_usdc": 10_000.0,
                    "realized_pnl_usdc": 20.0,
                    "quantity": 0.25,
                    "entry_price": 100.0,
                    "mark_price": 102.0,
                },
                "execution_summary": {
                    "reason_code": "filled",
                },
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "events.ndjson").write_text(
        json.dumps(
            {
                "cycle_id": "cycle-0001",
                "timestamp": "2026-03-21T01:00:00Z",
                "execution_summary": {
                    "reason_code": "filled",
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (run_dir / "fills.ndjson").write_text(
        json.dumps({"fill_id": "fill-1", "price": 102.0, "quantity": 0.25}) + "\n",
        encoding="utf-8",
    )
    (run_dir / "positions.ndjson").write_text(
        json.dumps(
            {
                "cycle_id": "cycle-0001",
                "position": {
                    "collateral_usdc": 10_000.0,
                    "realized_pnl_usdc": 20.0,
                    "quantity": 0.25,
                    "entry_price": 100.0,
                    "mark_price": 102.0,
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )

    exit_code = main(["analyze", "--runs-dir", str(tmp_path), "--run-id", run_id])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["run_id"] == run_id
    assert payload["strategy_id"] == "momentum"
    assert payload["fill_count"] == 1
    assert payload["decision_counts"] == {"filled": 1}


def test_analyze_main_exits_cleanly_when_state_is_missing(tmp_path) -> None:
    run_id = "20260322T020000000000Z_beta"
    run_dir = tmp_path / run_id
    run_dir.mkdir(parents=True)
    (run_dir / "manifest.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "created_at": "2026-03-21T01:00:00Z",
                "mode": "paper",
                "product_id": "BTC-PERP-INTX",
            }
        ),
        encoding="utf-8",
    )

    try:
        main(["analyze", "--runs-dir", str(tmp_path), "--run-id", run_id])
    except SystemExit as exc:
        assert str(exc) == f"analysis inputs not found for run: {run_id}"
    else:
        raise AssertionError("expected SystemExit")


def test_analyze_main_exits_cleanly_when_ndjson_shape_is_invalid(tmp_path) -> None:
    run_id = "20260322T020000000000Z_beta"
    run_dir = tmp_path / run_id
    run_dir.mkdir(parents=True)
    (run_dir / "manifest.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "created_at": "2026-03-21T01:00:00Z",
                "mode": "paper",
                "product_id": "BTC-PERP-INTX",
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "state.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "cycle_id": "cycle-0001",
                "mode": "paper",
                "position": {
                    "collateral_usdc": 10_000.0,
                    "realized_pnl_usdc": 0.0,
                    "quantity": 0.0,
                    "entry_price": 100.0,
                    "mark_price": 100.0,
                },
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "events.ndjson").write_text("[]\n", encoding="utf-8")

    try:
        main(["analyze", "--runs-dir", str(tmp_path), "--run-id", run_id])
    except SystemExit as exc:
        assert str(exc) == f"invalid analysis inputs for run: {run_id}"
    else:
        raise AssertionError("expected SystemExit")


def test_analyze_main_exits_cleanly_when_state_json_shape_is_invalid(tmp_path) -> None:
    run_id = "20260322T020000000000Z_beta"
    run_dir = tmp_path / run_id
    run_dir.mkdir(parents=True)
    (run_dir / "manifest.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "created_at": "2026-03-21T01:00:00Z",
                "mode": "paper",
                "product_id": "BTC-PERP-INTX",
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "state.json").write_text("[1]\n", encoding="utf-8")

    try:
        main(["analyze", "--runs-dir", str(tmp_path), "--run-id", run_id])
    except SystemExit as exc:
        assert str(exc) == f"invalid analysis inputs for run: {run_id}"
    else:
        raise AssertionError("expected SystemExit")
