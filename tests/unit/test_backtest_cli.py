import json
from dataclasses import dataclass, field
from types import SimpleNamespace

import pytest

from perpfut.cli import build_parser, main


def test_backtest_run_parser_accepts_repeated_products_and_strategies() -> None:
    parser = build_parser()

    args = parser.parse_args(
        [
            "backtest",
            "run",
            "--product-id",
            "BTC-PERP-INTX",
            "--product-id",
            "ETH-PERP-INTX",
            "--strategy-id",
            "momentum",
            "--strategy-id",
            "mean_reversion",
            "--start",
            "2026-03-20T00:00:00+00:00",
            "--end",
            "2026-03-21T00:00:00+00:00",
        ]
    )

    assert args.command == "backtest"
    assert args.backtest_command == "run"
    assert args.product_ids == ["BTC-PERP-INTX", "ETH-PERP-INTX"]
    assert args.strategy_ids == ["momentum", "mean_reversion"]


def test_backtest_run_parser_accepts_dataset_id_without_products() -> None:
    parser = build_parser()

    args = parser.parse_args(
        [
            "backtest",
            "run",
            "--dataset-id",
            "dataset-1",
            "--strategy-id",
            "momentum",
        ]
    )

    assert args.dataset_id == "dataset-1"
    assert args.product_ids is None


def test_backtest_run_main_prints_suite_payload(monkeypatch, tmp_path, capsys) -> None:
    captured = {}

    class FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

    class FakeBuilder:
        def __init__(self, *, client, base_runs_dir):
            captured["builder"] = {"client": client.__class__.__name__, "base_runs_dir": str(base_runs_dir)}

        def build_dataset(self, *, products, start, end, granularity):
            captured["dataset"] = {
                "products": products,
                "start": start.isoformat(),
                "end": end.isoformat(),
                "granularity": granularity,
            }
            return type("Dataset", (), {"dataset_id": "dataset-1"})()

    @dataclass
    class FakeAnalysis:
        run_id: str = "run-1"
        mode: str = "backtest"
        product_id: str | None = "MULTI_ASSET"
        strategy_id: str | None = "momentum"
        started_at: str | None = None
        ended_at: str | None = None
        date_range_start: str | None = "2026-03-20T00:00:00+00:00"
        date_range_end: str | None = "2026-03-20T01:00:00+00:00"
        sharpe_ratio: float | None = 1.23
        cycle_count: int = 1
        starting_equity_usdc: float = 10000.0
        ending_equity_usdc: float = 10100.0
        realized_pnl_usdc: float = 50.0
        unrealized_pnl_usdc: float = 50.0
        total_pnl_usdc: float = 100.0
        total_return_pct: float = 0.01
        max_drawdown_usdc: float = 10.0
        max_drawdown_pct: float = 0.001
        turnover_usdc: float = 1000.0
        fill_count: int = 2
        trade_count: int = 2
        avg_abs_exposure_pct: float = 0.2
        max_abs_exposure_pct: float = 0.3
        decision_counts: dict[str, int] = field(default_factory=lambda: {"filled": 1})
        equity_series: tuple = ()
        drawdown_series: tuple = ()
        exposure_series: tuple = ()

    fake_item = SimpleNamespace(run_id="run-1", strategy_id="momentum", analysis=FakeAnalysis())
    fake_suite = SimpleNamespace(
        suite_id="suite-1",
        dataset_id="dataset-1",
        run_ids=("run-1",),
        items=(fake_item,),
    )

    class FakeSuiteRunner:
        def __init__(self, *, base_runs_dir, dataset, config, products):
            captured["suite_runner"] = {
                "base_runs_dir": str(base_runs_dir),
                "dataset_id": dataset.dataset_id,
                "products": products,
            }

        def run_suite(self, *, strategy_ids, progress_callback=None):
            captured["strategy_ids"] = strategy_ids
            return fake_suite

    monkeypatch.setattr("perpfut.cli.CoinbasePublicClient", FakeClient)
    monkeypatch.setattr("perpfut.cli.HistoricalDatasetBuilder", FakeBuilder)
    monkeypatch.setattr("perpfut.cli.BacktestSuiteRunner", FakeSuiteRunner)

    exit_code = main(
        [
            "backtest",
            "run",
            "--runs-dir",
            str(tmp_path),
            "--product-id",
            "BTC-PERP-INTX",
            "--strategy-id",
            "momentum",
            "--start",
            "2026-03-20T00:00:00+00:00",
            "--end",
            "2026-03-20T01:00:00+00:00",
        ]
    )

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["suite_id"] == "suite-1"
    assert captured["dataset"]["products"] == ["BTC-PERP-INTX"]


def test_backtest_run_main_can_load_cached_dataset_by_id(monkeypatch, tmp_path, capsys) -> None:
    captured = {}

    class FakeBuilder:
        def __init__(self, *, client, base_runs_dir):
            captured["builder"] = {"base_runs_dir": str(base_runs_dir), "client": client.__class__.__name__}

        def load_dataset(self, dataset_id):
            captured["dataset_id"] = dataset_id
            return type("Dataset", (), {"dataset_id": dataset_id, "products": ("BTC-PERP-INTX", "ETH-PERP-INTX")})()

    @dataclass
    class FakeAnalysis:
        run_id: str = "run-1"
        mode: str = "backtest"
        product_id: str | None = "MULTI_ASSET"
        strategy_id: str | None = "momentum"
        started_at: str | None = None
        ended_at: str | None = None
        date_range_start: str | None = None
        date_range_end: str | None = None
        sharpe_ratio: float | None = None
        cycle_count: int = 1
        starting_equity_usdc: float = 10000.0
        ending_equity_usdc: float = 10100.0
        realized_pnl_usdc: float = 50.0
        unrealized_pnl_usdc: float = 50.0
        total_pnl_usdc: float = 100.0
        total_return_pct: float = 0.01
        max_drawdown_usdc: float = 10.0
        max_drawdown_pct: float = 0.001
        turnover_usdc: float = 1000.0
        fill_count: int = 1
        trade_count: int = 1
        avg_abs_exposure_pct: float = 0.1
        max_abs_exposure_pct: float = 0.2
        decision_counts: dict[str, int] = field(default_factory=lambda: {"filled": 1})
        equity_series: tuple = ()
        drawdown_series: tuple = ()
        exposure_series: tuple = ()

    fake_item = SimpleNamespace(run_id="run-1", strategy_id="momentum", analysis=FakeAnalysis())
    fake_suite = SimpleNamespace(suite_id="suite-1", dataset_id="dataset-1", run_ids=("run-1",), items=(fake_item,))

    class FakeSuiteRunner:
        def __init__(self, *, base_runs_dir, dataset, config, products):
            captured["suite_runner"] = {
                "dataset_id": dataset.dataset_id,
                "products": products,
            }

        def run_suite(self, *, strategy_ids, progress_callback=None):
            captured["strategy_ids"] = strategy_ids
            return fake_suite

    monkeypatch.setattr("perpfut.cli.HistoricalDatasetBuilder", FakeBuilder)
    monkeypatch.setattr("perpfut.cli.BacktestSuiteRunner", FakeSuiteRunner)

    exit_code = main(
        [
            "backtest",
            "run",
            "--runs-dir",
            str(tmp_path),
            "--dataset-id",
            "dataset-1",
            "--strategy-id",
            "momentum",
        ]
    )

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["dataset_id"] == "dataset-1"
    assert captured["dataset_id"] == "dataset-1"
    assert captured["suite_runner"]["products"] == ["BTC-PERP-INTX", "ETH-PERP-INTX"]


def test_backtest_show_and_compare_commands_read_artifacts(tmp_path, capsys) -> None:
    suites_dir = tmp_path / "backtests" / "suites" / "suite-1"
    runs_dir = tmp_path / "backtests" / "runs" / "run-1"
    suites_dir.mkdir(parents=True)
    runs_dir.mkdir(parents=True)
    (suites_dir / "manifest.json").write_text(
        json.dumps(
            {
                "suite_id": "suite-1",
                "dataset_id": "dataset-1",
                "run_ids": ["run-1"],
                "strategies": ["momentum"],
            }
        ),
        encoding="utf-8",
    )
    (runs_dir / "manifest.json").write_text(
        json.dumps({"run_id": "run-1", "mode": "backtest", "strategy_id": "momentum"}),
        encoding="utf-8",
    )
    (runs_dir / "state.json").write_text(
        json.dumps({"run_id": "run-1", "cycle_id": "cycle-0001"}),
        encoding="utf-8",
    )
    (runs_dir / "analysis.json").write_text(
        json.dumps(
            {
                "run_id": "run-1",
                "strategy_id": "momentum",
                "total_pnl_usdc": 50.0,
                "total_return_pct": 0.01,
                "max_drawdown_usdc": 5.0,
                "max_drawdown_pct": 0.001,
                "turnover_usdc": 100.0,
                "fill_count": 1,
                "avg_abs_exposure_pct": 0.1,
                "max_abs_exposure_pct": 0.2,
                "decision_counts": {"filled": 1},
            }
        ),
        encoding="utf-8",
    )

    show_exit_code = main(["backtest", "show", "--runs-dir", str(tmp_path), "--run-id", "run-1"])
    show_payload = json.loads(capsys.readouterr().out)

    compare_exit_code = main(["backtest", "compare", "--runs-dir", str(tmp_path), "--suite-id", "suite-1"])
    compare_payload = json.loads(capsys.readouterr().out)

    assert show_exit_code == 0
    assert compare_exit_code == 0
    assert show_payload["analysis"]["run_id"] == "run-1"
    assert compare_payload["suite_id"] == "suite-1"
    assert compare_payload["items"][0]["run_id"] == "run-1"


def test_dataset_commands_build_list_and_show(monkeypatch, tmp_path, capsys) -> None:
    captured = {}

    class FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

    class FakeBuilder:
        def __init__(self, *, client, base_runs_dir):
            captured["base_runs_dir"] = str(base_runs_dir)

        def build_dataset(self, *, products, start, end, granularity):
            captured["build"] = {
                "products": products,
                "start": start.isoformat(),
                "end": end.isoformat(),
                "granularity": granularity,
            }
            return type("Dataset", (), {"dataset_id": "dataset-1"})()

    @dataclass
    class FakeDatasetSummary:
        dataset_id: str = "dataset-1"
        created_at: str = "2026-03-20T00:00:00+00:00"
        fingerprint: str = "fp-1"
        source: str = "coinbase"
        version: str = "1"
        products: tuple[str, ...] = ("BTC-PERP-INTX",)
        start: str = "2026-03-20T00:00:00+00:00"
        end: str = "2026-03-21T00:00:00+00:00"
        granularity: str = "ONE_MINUTE"
        candle_counts: dict[str, int] = field(default_factory=lambda: {"BTC-PERP-INTX": 1440})

    summary = FakeDatasetSummary()

    monkeypatch.setattr("perpfut.cli.CoinbasePublicClient", FakeClient)
    monkeypatch.setattr("perpfut.cli.HistoricalDatasetBuilder", FakeBuilder)
    monkeypatch.setattr("perpfut.cli.load_dataset_summary", lambda *_args, **_kwargs: summary)
    monkeypatch.setattr("perpfut.cli.list_dataset_summaries", lambda *_args, **_kwargs: [summary])

    assert main(
        [
            "dataset",
            "build",
            "--runs-dir",
            str(tmp_path),
            "--product-id",
            "BTC-PERP-INTX",
            "--start",
            "2026-03-20T00:00:00+00:00",
            "--end",
            "2026-03-21T00:00:00+00:00",
        ]
    ) == 0
    build_payload = json.loads(capsys.readouterr().out)
    assert build_payload["dataset_id"] == "dataset-1"

    assert main(["dataset", "list", "--runs-dir", str(tmp_path)]) == 0
    list_payload = json.loads(capsys.readouterr().out)
    assert list_payload[0]["fingerprint"] == "fp-1"

    assert main(["dataset", "show", "--runs-dir", str(tmp_path), "--dataset-id", "dataset-1"]) == 0
    show_payload = json.loads(capsys.readouterr().out)
    assert show_payload["dataset_id"] == "dataset-1"


def test_backtest_run_rejects_invalid_strategy_before_dataset_build(monkeypatch, tmp_path) -> None:
    class ExplodingClient:
        def __enter__(self):
            raise AssertionError("coinbase client should not be constructed for an invalid strategy")

        def __exit__(self, *_args):
            return None

    class ExplodingBuilder:
        def __init__(self, *, client, base_runs_dir):
            raise AssertionError("dataset builder should not be constructed for an invalid strategy")

    monkeypatch.setattr("perpfut.cli.CoinbasePublicClient", ExplodingClient)
    monkeypatch.setattr("perpfut.cli.HistoricalDatasetBuilder", ExplodingBuilder)

    with pytest.raises(SystemExit, match="unknown strategy_id 'nope'"):
        main(
            [
                "backtest",
                "run",
                "--runs-dir",
                str(tmp_path),
                "--product-id",
                "BTC-PERP-INTX",
                "--strategy-id",
                "nope",
                "--start",
                "2026-03-20T00:00:00+00:00",
                "--end",
                "2026-03-20T01:00:00+00:00",
            ]
        )


def test_backtest_show_missing_run_raises_system_exit(tmp_path) -> None:
    with pytest.raises(SystemExit, match="backtest run not found: missing"):
        main(["backtest", "show", "--runs-dir", str(tmp_path), "--run-id", "missing"])


def test_backtest_compare_missing_suite_raises_system_exit(tmp_path) -> None:
    with pytest.raises(SystemExit, match="backtest suite not found: missing"):
        main(["backtest", "compare", "--runs-dir", str(tmp_path), "--suite-id", "missing"])


def test_backtest_list_skips_malformed_suite_manifests(tmp_path, capsys) -> None:
    valid_suite_dir = tmp_path / "backtests" / "suites" / "suite-valid"
    valid_suite_dir.mkdir(parents=True)
    (valid_suite_dir / "manifest.json").write_text(
        json.dumps(
            {
                "suite_id": "suite-valid",
                "dataset_id": "dataset-1",
                "date_range_start": None,
                "date_range_end": None,
                "sharpe_ratio": None,
                "run_ids": ["run-1"],
                "strategies": ["momentum"],
                "products": ["BTC-PERP-INTX"],
            }
        ),
        encoding="utf-8",
    )
    malformed_suite_dir = tmp_path / "backtests" / "suites" / "suite-bad"
    malformed_suite_dir.mkdir(parents=True)
    (malformed_suite_dir / "manifest.json").write_text("{not-json", encoding="utf-8")

    exit_code = main(["backtest", "list", "--runs-dir", str(tmp_path)])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload == [
        {
            "created_at": None,
            "dataset_id": "dataset-1",
            "date_range_end": None,
            "date_range_start": None,
            "products": ["BTC-PERP-INTX"],
            "run_ids": ["run-1"],
            "sharpe_ratio": None,
            "strategies": ["momentum"],
            "suite_id": "suite-valid",
        }
    ]
