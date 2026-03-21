"""Command-line entrypoints for paper mode and product discovery."""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict
from pathlib import Path

from .config import AppConfig
from .domain import Mode
from .engine import PaperEngine
from .exchange_coinbase import CoinbasePrivateClient, CoinbasePublicClient
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

    live_parser = subparsers.add_parser("live", help="reserved live mode entrypoint")
    live_parser.add_argument("--product-id", default=None)

    return parser


def main(argv: list[str] | None = None) -> int:
    configure_logging()
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "paper":
        return _run_paper(args)
    if args.command == "products":
        return _list_products(args)
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


def _run_live(args: argparse.Namespace) -> int:
    if os.getenv("PERPFUT_ENABLE_LIVE") != "1":
        raise SystemExit("live mode is gated; set PERPFUT_ENABLE_LIVE=1 only after implementation")

    _ = args.product_id
    CoinbasePrivateClient().preview_market_order()
    return 0
