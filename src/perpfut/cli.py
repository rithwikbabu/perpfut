"""Command-line entrypoints for paper mode and product discovery."""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict
from pathlib import Path

from .analysis import analyze_run
from .api.server import run_api_server
from .config import AppConfig
from .domain import Mode
from .engine import PaperEngine
from .experiment import run_experiment
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
    if args.command == "reconcile":
        return _run_reconcile(args)
    if args.command == "preflight":
        return _run_preflight(args)
    if args.command == "api":
        return _run_api(args)
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


def _validate_strategy_config(config: AppConfig) -> None:
    try:
        validate_strategy_id(config.strategy.strategy_id)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
