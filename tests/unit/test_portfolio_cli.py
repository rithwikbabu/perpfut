import json
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

from perpfut.cli import build_parser, main


def test_portfolio_run_parser_accepts_strategy_specs_and_dataset() -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "portfolio",
            "run",
            "--dataset-id",
            "dataset-1",
            "--strategy-specs",
            "specs.json",
        ]
    )

    assert args.command == "portfolio"
    assert args.portfolio_command == "run"
    assert args.dataset_id == "dataset-1"
    assert args.strategy_specs == Path("specs.json")


def test_portfolio_run_main_prints_result(monkeypatch, tmp_path, capsys) -> None:
    specs_path = tmp_path / "specs.json"
    specs_path.write_text(
        json.dumps(
            [
                {
                    "strategy_instance_id": "mom-a",
                    "strategy_id": "momentum",
                    "universe": ["BTC-PERP-INTX"],
                }
            ]
        ),
        encoding="utf-8",
    )

    class FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

    class FakeBuilder:
        def __init__(self, *, client, base_runs_dir):
            self.base_runs_dir = base_runs_dir

        def load_dataset(self, dataset_id):
            return SimpleNamespace(dataset_id=dataset_id)

    @dataclass
    class FakeAnalysis:
        dataset_id: str = "dataset-1"
        total_return_pct: float = 0.01

    def fake_run_portfolio_research(**kwargs):
        return SimpleNamespace(
            run_id="portfolio-run-1",
            sleeve_run_ids=("sleeve-run-1",),
            analysis=FakeAnalysis(),
        )

    monkeypatch.setattr("perpfut.cli.CoinbasePublicClient", FakeClient)
    monkeypatch.setattr("perpfut.cli.HistoricalDatasetBuilder", FakeBuilder)
    monkeypatch.setattr("perpfut.cli.run_portfolio_research", fake_run_portfolio_research)

    exit_code = main(
        [
            "portfolio",
            "run",
            "--runs-dir",
            str(tmp_path),
            "--dataset-id",
            "dataset-1",
            "--strategy-specs",
            str(specs_path),
        ]
    )

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["run_id"] == "portfolio-run-1"
    assert payload["dataset_id"] == "dataset-1"
    assert payload["sleeve_run_ids"] == ["sleeve-run-1"]


def test_portfolio_show_and_compare_commands_read_artifacts(tmp_path, capsys) -> None:
    run_dir = tmp_path / "backtests" / "portfolio-runs" / "portfolio-run-1"
    run_dir.mkdir(parents=True)
    for filename, payload in {
        "manifest.json": {"run_id": "portfolio-run-1", "dataset_id": "dataset-1"},
        "config.json": {"optimizer": {"lookback_days": 60}},
        "state.json": {"run_id": "portfolio-run-1"},
        "analysis.json": {
            "run_id": "portfolio-run-1",
            "dataset_id": "dataset-1",
            "dataset_fingerprint": "fp-1",
            "dataset_source": "coinbase",
            "dataset_version": "1",
            "date_range_start": "2026-03-20T00:00:00+00:00",
            "date_range_end": "2026-03-21T00:00:00+00:00",
            "created_at": "2026-03-21T00:00:00+00:00",
            "starting_capital_usdc": 10000.0,
            "ending_equity_usdc": 10100.0,
            "total_pnl_usdc": 100.0,
            "total_return_pct": 0.01,
            "sharpe_ratio": 1.2,
            "max_drawdown_usdc": 10.0,
            "max_drawdown_pct": 0.001,
            "total_turnover_usdc": 500.0,
            "transaction_cost_total_usdc": 5.0,
            "avg_gross_weight": 0.5,
            "max_gross_weight": 0.8,
            "strategy_instance_ids": ["mom-a"],
            "sleeve_run_ids": ["sleeve-run-1"],
            "equity_series": [{"label": "2026-03-20", "value": 10100.0}],
            "drawdown_series": [{"label": "2026-03-20", "value": 0.0}],
            "gross_return_series": [{"label": "2026-03-20", "value": 0.01}],
            "net_return_series": [{"label": "2026-03-20", "value": 0.01}],
            "turnover_series_usdc": [{"label": "2026-03-20", "value": 500.0}],
            "transaction_cost_series_usdc": [{"label": "2026-03-20", "value": 5.0}],
            "gross_weight_series": [{"label": "2026-03-20", "value": 0.5}],
            "contribution_totals_usdc": {"mom-a": 100.0},
        },
        "contributions.json": {
            "items": [],
            "transaction_cost_total_usdc": 5.0,
            "transaction_cost_series_usdc": [],
        },
    }.items():
        (run_dir / filename).write_text(json.dumps(payload), encoding="utf-8")
    (run_dir / "weights.ndjson").write_text(
        json.dumps({"date": "2026-03-20", "weights": {"mom-a": 0.5}, "cash_weight": 0.5, "turnover": 0.5, "gross_weight": 0.5}) + "\n",
        encoding="utf-8",
    )
    (run_dir / "diagnostics.ndjson").write_text(
        json.dumps({"date": "2026-03-20", "expected_returns": {"mom-a": 0.01}, "covariance_matrix": {"mom-a": {"mom-a": 0.001}}, "constraint_status": "optimized"}) + "\n",
        encoding="utf-8",
    )

    assert main(["portfolio", "show", "--runs-dir", str(tmp_path), "--run-id", "portfolio-run-1"]) == 0
    show_payload = json.loads(capsys.readouterr().out)
    assert show_payload["analysis"]["run_id"] == "portfolio-run-1"

    assert main(["portfolio", "compare", "--runs-dir", str(tmp_path)]) == 0
    compare_payload = json.loads(capsys.readouterr().out)
    assert compare_payload["items"][0]["run_id"] == "portfolio-run-1"
