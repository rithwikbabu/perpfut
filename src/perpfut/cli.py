"""Command-line entrypoints for paper mode and product discovery."""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict, replace
from datetime import datetime
from pathlib import Path

from .analysis import analyze_run
from .api.server import run_api_server
from .backtest_data import (
    HistoricalDatasetBuilder,
    list_dataset_summaries,
    load_dataset_summary,
)
from .backtest_progress import BacktestProgressReporter, BacktestProgressUpdate
from .backtest_history import compare_backtest_suite, list_backtest_suites, load_backtest_run
from .backtest_suite import BacktestSuiteRunner
from .config import AppConfig
from .domain import Mode
from .engine import PaperEngine
from .experiment import run_experiment
from .experiment import compare_experiments
from .exchange_coinbase import CoinbasePrivateClient, CoinbasePublicClient
from .live_execution import LiveExecutor
from .preflight import run_preflight
from .run_history import find_latest_run, load_run_manifest, load_run_state, summarize_runs
from .strategy_registry import validate_strategy_id
from .telemetry import ArtifactStore, configure_logging


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="perpfut")
    subparsers = parser.add_subparsers(dest="command")

    paper_parser = subparsers.add_parser("paper", help="run the paper trading loop")
    paper_parser.add_argument("--product-id", default=None)
    paper_parser.add_argument("--iterations", type=int, default=None)
    paper_parser.add_argument("--interval-seconds", type=int, default=None)
    paper_parser.add_argument("--runs-dir", type=Path, default=None)

    products_parser = subparsers.add_parser("products", help="list Coinbase perpetual products")
    products_parser.add_argument("--limit", type=int, default=10)

    runs_parser = subparsers.add_parser("runs", help="list recent run artifacts")
    runs_parser.add_argument("--limit", type=int, default=10)
    runs_parser.add_argument("--runs-dir", type=Path, default=None)

    state_parser = subparsers.add_parser("state", help="show the latest or named run state")
    state_parser.add_argument("--run-id", default=None)
    state_parser.add_argument("--runs-dir", type=Path, default=None)
    state_parser.add_argument("--mode", choices=["paper", "live"], default="live")
    state_parser.add_argument("--product-id", default=None)

    analyze_parser = subparsers.add_parser("analyze", help="analyze a run's performance artifacts")
    analyze_parser.add_argument("--run-id", default=None)
    analyze_parser.add_argument("--runs-dir", type=Path, default=None)
    analyze_parser.add_argument("--mode", choices=["paper", "live"], default="paper")
    analyze_parser.add_argument("--product-id", default=None)

    experiment_parser = subparsers.add_parser(
        "experiment",
        help="replay a source run through a selected strategy configuration",
    )
    experiment_parser.add_argument("--source-run-id", required=True)
    experiment_parser.add_argument("--strategy-id", required=True)
    experiment_parser.add_argument("--lookback-candles", type=int, default=None)
    experiment_parser.add_argument("--signal-scale", type=float, default=None)
    experiment_parser.add_argument("--runs-dir", type=Path, default=None)

    compare_experiments_parser = subparsers.add_parser(
        "compare-experiments",
        help="rank experiment outputs for a single source run",
    )
    compare_experiments_parser.add_argument("--source-run-id", required=True)
    compare_experiments_parser.add_argument("--runs-dir", type=Path, default=None)

    reconcile_parser = subparsers.add_parser(
        "reconcile",
        help="fetch and normalize read-only INTX portfolio state",
    )
    reconcile_parser.add_argument("--portfolio-uuid", default=None)
    reconcile_parser.add_argument("--product-id", default=None)
    reconcile_parser.add_argument("--fills-limit", type=int, default=50)

    live_parser = subparsers.add_parser("live", help="reserved live mode entrypoint")
    live_parser.add_argument("--product-id", default=None)
    live_parser.add_argument("--portfolio-uuid", default=None)
    live_parser.add_argument("--iterations", type=int, default=None)
    live_parser.add_argument("--interval-seconds", type=int, default=None)
    live_parser.add_argument("--runs-dir", type=Path, default=None)

    preflight_parser = subparsers.add_parser("preflight", help="run readiness checks")
    preflight_parser.add_argument("--mode", choices=["paper", "live"], required=True)
    preflight_parser.add_argument("--product-id", default=None)
    preflight_parser.add_argument("--portfolio-uuid", default=None)
    preflight_parser.add_argument("--runs-dir", type=Path, default=None)
    preflight_parser.add_argument("--preview-quantity", type=float, default=None)

    api_parser = subparsers.add_parser("api", help="run the local operator API service")
    api_parser.add_argument("--host", default="127.0.0.1")
    api_parser.add_argument("--port", type=int, default=8000)

    dataset_parser = subparsers.add_parser("dataset", help="build and inspect cached historical datasets")
    dataset_subparsers = dataset_parser.add_subparsers(dest="dataset_command")

    dataset_build_parser = dataset_subparsers.add_parser("build", help="build or reuse a cached dataset")
    dataset_build_parser.add_argument("--product-id", action="append", dest="product_ids", required=True)
    dataset_build_parser.add_argument("--start", required=True)
    dataset_build_parser.add_argument("--end", required=True)
    dataset_build_parser.add_argument("--granularity", default="ONE_MINUTE", choices=["ONE_MINUTE"])
    dataset_build_parser.add_argument("--runs-dir", type=Path, default=None)

    dataset_list_parser = dataset_subparsers.add_parser("list", help="list cached datasets")
    dataset_list_parser.add_argument("--limit", type=int, default=10)
    dataset_list_parser.add_argument("--runs-dir", type=Path, default=None)

    dataset_show_parser = dataset_subparsers.add_parser("show", help="show one cached dataset")
    dataset_show_parser.add_argument("--dataset-id", required=True)
    dataset_show_parser.add_argument("--runs-dir", type=Path, default=None)

    backtest_parser = subparsers.add_parser("backtest", help="run and inspect historical backtests")
    backtest_subparsers = backtest_parser.add_subparsers(dest="backtest_command")

    backtest_run_parser = backtest_subparsers.add_parser("run", help="launch a historical backtest suite")
    backtest_run_parser.add_argument("--dataset-id", default=None)
    backtest_run_parser.add_argument("--product-id", action="append", dest="product_ids", default=None)
    backtest_run_parser.add_argument("--strategy-id", action="append", dest="strategy_ids", required=True)
    backtest_run_parser.add_argument("--start", default=None)
    backtest_run_parser.add_argument("--end", default=None)
    backtest_run_parser.add_argument("--granularity", default="ONE_MINUTE", choices=["ONE_MINUTE"])
    backtest_run_parser.add_argument("--runs-dir", type=Path, default=None)
    backtest_run_parser.add_argument("--lookback-candles", type=int, default=None)
    backtest_run_parser.add_argument("--signal-scale", type=float, default=None)
    backtest_run_parser.add_argument("--starting-collateral-usdc", type=float, default=None)
    backtest_run_parser.add_argument("--max-abs-position", type=float, default=None)
    backtest_run_parser.add_argument("--max-gross-position", type=float, default=None)
    backtest_run_parser.add_argument("--max-leverage", type=float, default=None)
    backtest_run_parser.add_argument("--slippage-bps", type=float, default=None)

    backtest_list_parser = backtest_subparsers.add_parser("list", help="list recent backtest suites")
    backtest_list_parser.add_argument("--limit", type=int, default=10)
    backtest_list_parser.add_argument("--runs-dir", type=Path, default=None)

    backtest_show_parser = backtest_subparsers.add_parser("show", help="show a backtest run")
    backtest_show_parser.add_argument("--run-id", required=True)
    backtest_show_parser.add_argument("--runs-dir", type=Path, default=None)

    backtest_compare_parser = backtest_subparsers.add_parser(
        "compare",
        help="compare the ranked runs inside a backtest suite",
    )
    backtest_compare_parser.add_argument("--suite-id", required=True)
    backtest_compare_parser.add_argument("--runs-dir", type=Path, default=None)

    return parser


def main(argv: list[str] | None = None) -> int:
    configure_logging()
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "paper":
        return _run_paper(args)
    if args.command == "products":
        return _list_products(args)
    if args.command == "runs":
        return _list_runs(args)
    if args.command == "state":
        return _show_state(args)
    if args.command == "analyze":
        return _run_analyze(args)
    if args.command == "experiment":
        return _run_experiment(args)
    if args.command == "compare-experiments":
        return _run_compare_experiments(args)
    if args.command == "reconcile":
        return _run_reconcile(args)
    if args.command == "preflight":
        return _run_preflight(args)
    if args.command == "api":
        return _run_api(args)
    if args.command == "dataset":
        return _run_dataset(args)
    if args.command == "backtest":
        return _run_backtest(args)
    if args.command == "live":
        return _run_live(args)

    parser.print_help()
    return 1


def _run_paper(args: argparse.Namespace) -> int:
    config = AppConfig.from_env().with_overrides(
        mode=Mode.PAPER,
        product_id=args.product_id,
        iterations=args.iterations,
        interval_seconds=args.interval_seconds,
        runs_dir=args.runs_dir,
    )
    _validate_strategy_config(config)
    artifact_store = ArtifactStore.create(config.runtime.runs_dir)
    artifact_store.write_metadata(config)

    with CoinbasePublicClient() as client:
        engine = PaperEngine(
            config=config,
            market_data=client,
            artifact_store=artifact_store,
        )
        engine.run()
    return 0


def _list_products(args: argparse.Namespace) -> int:
    with CoinbasePublicClient() as client:
        products = client.list_perpetual_products(limit=args.limit)
    print(json.dumps([asdict(product) for product in products], indent=2, sort_keys=True))
    return 0


def _list_runs(args: argparse.Namespace) -> int:
    runs_dir = args.runs_dir or AppConfig.from_env().runtime.runs_dir
    print(json.dumps(summarize_runs(runs_dir, limit=args.limit), indent=2, sort_keys=True))
    return 0


def _show_state(args: argparse.Namespace) -> int:
    runs_dir = args.runs_dir or AppConfig.from_env().runtime.runs_dir
    if args.run_id:
        run_dir = runs_dir / args.run_id
    else:
        run_dir = find_latest_run(
            runs_dir,
            mode=args.mode,
            product_id=args.product_id,
            require_state=True,
        )
        if run_dir is None:
            raise SystemExit("no runs found")
    print(json.dumps(load_run_state(run_dir), indent=2, sort_keys=True))
    return 0


def _run_analyze(args: argparse.Namespace) -> int:
    config = AppConfig.from_env().with_overrides(runs_dir=args.runs_dir)
    if args.run_id:
        run_dir = config.runtime.runs_dir / args.run_id
        if not run_dir.exists():
            raise SystemExit(f"run not found: {args.run_id}")
    else:
        run_dir = find_latest_run(
            config.runtime.runs_dir,
            mode=args.mode,
            product_id=args.product_id,
            require_state=True,
        )
        if run_dir is None:
            raise SystemExit("no runs found")
    try:
        analysis = analyze_run(run_dir)
    except FileNotFoundError as exc:
        raise SystemExit(f"analysis inputs not found for run: {run_dir.name}") from exc
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        raise SystemExit(f"invalid analysis inputs for run: {run_dir.name}") from exc
    print(json.dumps(asdict(analysis), indent=2, sort_keys=True))
    return 0


def _run_experiment(args: argparse.Namespace) -> int:
    config = AppConfig.from_env().with_overrides(runs_dir=args.runs_dir)
    try:
        artifact_store = run_experiment(
            base_runs_dir=config.runtime.runs_dir,
            source_run_id=args.source_run_id,
            strategy_id=args.strategy_id,
            lookback_candles=args.lookback_candles,
            signal_scale=args.signal_scale,
        )
    except FileNotFoundError as exc:
        raise SystemExit(str(exc)) from exc
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        raise SystemExit(str(exc)) from exc

    print(
        json.dumps(
            {
                "analysis_path": str(artifact_store.run_dir / "analysis.json"),
                "run_id": artifact_store.run_id,
                "source_run_id": args.source_run_id,
                "strategy_id": args.strategy_id,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def _run_compare_experiments(args: argparse.Namespace) -> int:
    config = AppConfig.from_env().with_overrides(runs_dir=args.runs_dir)
    try:
        report = compare_experiments(
            base_runs_dir=config.runtime.runs_dir,
            source_run_id=args.source_run_id,
        )
    except FileNotFoundError as exc:
        raise SystemExit(str(exc)) from exc
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        raise SystemExit(str(exc)) from exc

    print(json.dumps(asdict(report), indent=2, sort_keys=True))
    return 0


def _run_reconcile(args: argparse.Namespace) -> int:
    config = AppConfig.from_env()
    portfolio_uuid = args.portfolio_uuid or config.coinbase.intx_portfolio_uuid
    if not portfolio_uuid:
        raise SystemExit("set COINBASE_INTX_PORTFOLIO_UUID or pass --portfolio-uuid")
    if not config.coinbase.api_key_id or not config.coinbase.api_key_secret:
        raise SystemExit("set COINBASE_API_KEY_ID and COINBASE_API_KEY_SECRET")

    product_id = args.product_id or config.runtime.product_id
    with CoinbasePrivateClient(
        api_key_id=config.coinbase.api_key_id,
        api_key_secret=config.coinbase.api_key_secret,
    ) as client:
        snapshot = client.reconcile_intx_portfolio(
            portfolio_uuid=portfolio_uuid,
            product_id=product_id,
            fills_limit=args.fills_limit,
        )

    print(json.dumps(asdict(snapshot), indent=2, sort_keys=True, default=str))
    return 0


def _run_preflight(args: argparse.Namespace) -> int:
    config = AppConfig.from_env().with_overrides(
        product_id=args.product_id,
        runs_dir=args.runs_dir,
    )
    _validate_strategy_config(config)
    portfolio_uuid = args.portfolio_uuid or config.coinbase.intx_portfolio_uuid

    with CoinbasePublicClient() as public_client:
        if args.mode == "live" and config.coinbase.api_key_id and config.coinbase.api_key_secret:
            with CoinbasePrivateClient(
                api_key_id=config.coinbase.api_key_id,
                api_key_secret=config.coinbase.api_key_secret,
            ) as private_client:
                report = run_preflight(
                    config=config,
                    mode=args.mode,
                    public_client=public_client,
                    private_client=private_client,
                    portfolio_uuid=portfolio_uuid,
                    preview_quantity=args.preview_quantity,
                )
        else:
            report = run_preflight(
                config=config,
                mode=args.mode,
                public_client=public_client,
                portfolio_uuid=portfolio_uuid,
                preview_quantity=args.preview_quantity,
            )

    print(json.dumps(asdict(report), indent=2, sort_keys=True))
    return 0 if report.ready else 1


def _run_live(args: argparse.Namespace) -> int:
    if os.getenv("PERPFUT_ENABLE_LIVE") != "1":
        raise SystemExit("live mode is gated; set PERPFUT_ENABLE_LIVE=1 only after implementation")

    config = AppConfig.from_env().with_overrides(
        mode=Mode.LIVE,
        product_id=args.product_id,
        iterations=args.iterations if args.iterations is not None else 1,
        interval_seconds=args.interval_seconds,
        runs_dir=args.runs_dir,
    )
    _validate_strategy_config(config)
    portfolio_uuid = args.portfolio_uuid or config.coinbase.intx_portfolio_uuid
    if not portfolio_uuid:
        raise SystemExit("set COINBASE_INTX_PORTFOLIO_UUID or pass --portfolio-uuid")
    if not config.coinbase.api_key_id or not config.coinbase.api_key_secret:
        raise SystemExit("set COINBASE_API_KEY_ID and COINBASE_API_KEY_SECRET")

    resume_run = find_latest_run(
        config.runtime.runs_dir,
        mode="live",
        product_id=config.runtime.product_id,
        require_state=True,
    )
    resume_state = load_run_state(resume_run) if resume_run is not None else None
    resumed_from_run_id = load_run_manifest(resume_run).get("run_id") if resume_run is not None else None

    artifact_store = ArtifactStore.create(
        config.runtime.runs_dir,
        resumed_from_run_id=resumed_from_run_id,
    )
    artifact_store.write_metadata(config)

    with CoinbasePublicClient() as market_data, CoinbasePrivateClient(
        api_key_id=config.coinbase.api_key_id,
        api_key_secret=config.coinbase.api_key_secret,
    ) as trading_client:
        executor = LiveExecutor(
            config=config,
            market_data=market_data,
            trading_client=trading_client,
            artifact_store=artifact_store,
            portfolio_uuid=portfolio_uuid,
            resume_state=resume_state,
        )
        executor.run()

    return 0


def _run_api(args: argparse.Namespace) -> int:
    run_api_server(host=args.host, port=args.port)
    return 0


def _run_dataset(args: argparse.Namespace) -> int:
    if args.dataset_command == "build":
        return _build_dataset_command(args)
    if args.dataset_command == "list":
        return _list_datasets_command(args)
    if args.dataset_command == "show":
        return _show_dataset_command(args)
    raise SystemExit("choose one of: build, list, show")


def _run_backtest(args: argparse.Namespace) -> int:
    if args.backtest_command == "run":
        return _run_backtest_suite(args)
    if args.backtest_command == "list":
        return _list_backtest_suites(args)
    if args.backtest_command == "show":
        return _show_backtest_run(args)
    if args.backtest_command == "compare":
        return _compare_backtest_suite(args)
    raise SystemExit("choose one of: run, list, show, compare")


def _run_backtest_suite(args: argparse.Namespace) -> int:
    config = _build_backtest_config(args)
    _validate_strategy_ids(args.strategy_ids)
    progress = BacktestProgressReporter.from_env()
    total_runs = len(args.strategy_ids)
    try:
        dataset, selected_products = _resolve_backtest_dataset(
            args,
            config=config,
            progress=progress,
            total_runs=total_runs,
        )
        suite = BacktestSuiteRunner(
            base_runs_dir=config.runtime.runs_dir,
            dataset=dataset,
            config=config,
            products=selected_products,
        ).run_suite(
            strategy_ids=args.strategy_ids,
            progress_callback=(
                (lambda snapshot: progress.emit(
                    BacktestProgressUpdate(
                        phase=snapshot.phase,
                        phase_message=snapshot.phase_message,
                        total_runs=snapshot.total_runs,
                        completed_runs=snapshot.completed_runs,
                    )
                ))
                if progress is not None
                else None
            ),
        )
        if progress is not None:
            progress.emit(
                BacktestProgressUpdate(
                    phase="finalizing",
                    phase_message="Writing final suite metadata and response payload.",
                    total_runs=total_runs,
                    completed_runs=total_runs,
                )
            )
        print(
            json.dumps(
                {
                    "suite_id": suite.suite_id,
                    "dataset_id": suite.dataset_id,
                    "run_ids": list(suite.run_ids),
                    "items": [
                        {
                            "run_id": item.run_id,
                            "strategy_id": item.strategy_id,
                            "analysis": asdict(item.analysis),
                        }
                        for item in suite.items
                    ],
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0
    except Exception as exc:
        message = f"backtest run failed: {exc}"
        if progress is not None:
            progress.emit(
                BacktestProgressUpdate(
                    phase="failed",
                    phase_message=message,
                    total_runs=total_runs,
                    error=message,
                )
            )
        print(message, file=sys.stderr)
        return 1


def _build_dataset_command(args: argparse.Namespace) -> int:
    runs_dir = args.runs_dir or AppConfig.from_env().runtime.runs_dir
    start = _parse_iso8601(args.start, field_name="start")
    end = _parse_iso8601(args.end, field_name="end")
    try:
        with CoinbasePublicClient() as client:
            builder = HistoricalDatasetBuilder(client=client, base_runs_dir=runs_dir)
            dataset = builder.build_dataset(
                products=args.product_ids,
                start=start,
                end=end,
                granularity=args.granularity,
            )
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    payload = load_dataset_summary(runs_dir, dataset_id=dataset.dataset_id)
    print(json.dumps(asdict(payload), indent=2, sort_keys=True))
    return 0


def _list_datasets_command(args: argparse.Namespace) -> int:
    runs_dir = args.runs_dir or AppConfig.from_env().runtime.runs_dir
    payload = [asdict(item) for item in list_dataset_summaries(runs_dir, limit=args.limit)]
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


def _show_dataset_command(args: argparse.Namespace) -> int:
    runs_dir = args.runs_dir or AppConfig.from_env().runtime.runs_dir
    try:
        payload = load_dataset_summary(runs_dir, dataset_id=args.dataset_id)
    except FileNotFoundError as exc:
        raise SystemExit(str(exc)) from exc
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        raise SystemExit(f"invalid dataset artifacts for: {args.dataset_id}") from exc
    print(json.dumps(asdict(payload), indent=2, sort_keys=True))
    return 0


def _list_backtest_suites(args: argparse.Namespace) -> int:
    runs_dir = args.runs_dir or AppConfig.from_env().runtime.runs_dir
    try:
        suites = list_backtest_suites(runs_dir, limit=args.limit)
    except FileNotFoundError as exc:
        raise SystemExit(str(exc)) from exc
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        raise SystemExit(f"invalid backtest suite artifacts in: {runs_dir}") from exc
    print(json.dumps([asdict(item) for item in suites], indent=2, sort_keys=True))
    return 0


def _show_backtest_run(args: argparse.Namespace) -> int:
    runs_dir = args.runs_dir or AppConfig.from_env().runtime.runs_dir
    try:
        payload = load_backtest_run(runs_dir, run_id=args.run_id)
    except FileNotFoundError as exc:
        raise SystemExit(str(exc)) from exc
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        raise SystemExit(f"invalid backtest run artifacts for: {args.run_id}") from exc
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


def _compare_backtest_suite(args: argparse.Namespace) -> int:
    runs_dir = args.runs_dir or AppConfig.from_env().runtime.runs_dir
    try:
        payload = compare_backtest_suite(runs_dir, suite_id=args.suite_id)
    except FileNotFoundError as exc:
        raise SystemExit(str(exc)) from exc
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        raise SystemExit(f"invalid backtest suite artifacts for: {args.suite_id}") from exc
    print(json.dumps(asdict(payload), indent=2, sort_keys=True))
    return 0


def _build_backtest_config(args: argparse.Namespace) -> AppConfig:
    config = AppConfig.from_env().with_overrides(runs_dir=args.runs_dir)
    if args.lookback_candles is not None:
        config = replace(config, strategy=replace(config.strategy, lookback_candles=args.lookback_candles))
    if args.signal_scale is not None:
        config = replace(config, strategy=replace(config.strategy, signal_scale=args.signal_scale))
    if args.starting_collateral_usdc is not None:
        config = replace(
            config,
            simulation=replace(
                config.simulation,
                starting_collateral_usdc=args.starting_collateral_usdc,
            ),
        )
    if args.max_abs_position is not None or args.max_gross_position is not None:
        config = replace(
            config,
            risk=replace(
                config.risk,
                max_abs_position=(
                    args.max_abs_position if args.max_abs_position is not None else config.risk.max_abs_position
                ),
                max_gross_position=(
                    args.max_gross_position
                    if args.max_gross_position is not None
                    else config.risk.max_gross_position
                ),
            ),
        )
    if args.max_leverage is not None or args.slippage_bps is not None:
        config = replace(
            config,
            simulation=replace(
                config.simulation,
                max_leverage=args.max_leverage if args.max_leverage is not None else config.simulation.max_leverage,
                slippage_bps=args.slippage_bps if args.slippage_bps is not None else config.simulation.slippage_bps,
            ),
        )
    return config


def _resolve_backtest_dataset(
    args: argparse.Namespace,
    *,
    config: AppConfig,
    progress: BacktestProgressReporter | None,
    total_runs: int,
):
    if args.dataset_id:
        builder = HistoricalDatasetBuilder(client=_UnusedHistoricalClient(), base_runs_dir=config.runtime.runs_dir)
        dataset = builder.load_dataset(args.dataset_id)
        selected_products = args.product_ids or list(dataset.products)
        return dataset, selected_products

    if not args.product_ids or args.start is None or args.end is None:
        raise SystemExit("backtest run requires either --dataset-id or --product-id with --start/--end")
    start = _parse_iso8601(args.start, field_name="start")
    end = _parse_iso8601(args.end, field_name="end")
    if progress is not None:
        progress.emit(
            BacktestProgressUpdate(
                phase="building_dataset",
                phase_message=f"Fetching Coinbase candles for {len(args.product_ids)} products.",
                total_runs=total_runs,
                completed_runs=0,
            )
        )
    with CoinbasePublicClient() as client:
        builder = HistoricalDatasetBuilder(
            client=client,
            base_runs_dir=config.runtime.runs_dir,
        )
        dataset = builder.build_dataset(
            products=args.product_ids,
            start=start,
            end=end,
            granularity=args.granularity,
        )
    return dataset, args.product_ids


def _parse_iso8601(value: str, *, field_name: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise SystemExit(f"invalid {field_name} datetime: {value}") from exc
    if parsed.tzinfo is None:
        raise SystemExit(f"{field_name} datetime must include a timezone: {value}")
    return parsed


def _validate_strategy_config(config: AppConfig) -> None:
    try:
        validate_strategy_id(config.strategy.strategy_id)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc


def _validate_strategy_ids(strategy_ids: list[str]) -> None:
    for strategy_id in strategy_ids:
        try:
            validate_strategy_id(strategy_id)
        except ValueError as exc:
            raise SystemExit(str(exc)) from exc


class _UnusedHistoricalClient:
    def fetch_historical_candles(self, *_args, **_kwargs):
        raise AssertionError("historical client should not be used when loading a cached dataset")
