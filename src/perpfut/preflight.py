"""Preflight checks for paper and live operating readiness."""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .config import AppConfig


@dataclass(frozen=True, slots=True)
class PreflightCheck:
    name: str
    ok: bool
    detail: str


@dataclass(frozen=True, slots=True)
class PreflightReport:
    mode: str
    product_id: str
    portfolio_uuid: str | None
    ready: bool
    checks: tuple[PreflightCheck, ...]


class PublicCheckClient(Protocol):
    def fetch_market(self, product_id: str, *, candle_limit: int):
        ...


class PrivateCheckClient(Protocol):
    def reconcile_intx_portfolio(
        self,
        *,
        portfolio_uuid: str,
        product_id: str | None = None,
        fills_limit: int = 50,
    ):
        ...

    def preview_market_order(
        self,
        *,
        portfolio_uuid: str,
        product_id: str,
        side: str,
        quantity: float,
        client_order_id: str,
    ):
        ...


def run_preflight(
    *,
    config: AppConfig,
    mode: str,
    public_client: PublicCheckClient | None = None,
    private_client: PrivateCheckClient | None = None,
    portfolio_uuid: str | None = None,
    preview_quantity: float | None = None,
) -> PreflightReport:
    checks: list[PreflightCheck] = []
    checks.append(_check_runs_dir(config.runtime.runs_dir))

    if public_client is not None:
        checks.append(_check_public_market_data(public_client, config.runtime.product_id))

    if mode == "live":
        checks.append(
            PreflightCheck(
                name="live_gate_env",
                ok=os.getenv("PERPFUT_ENABLE_LIVE") == "1",
                detail="PERPFUT_ENABLE_LIVE must be set to 1 before live trading",
            )
        )
        checks.append(
            PreflightCheck(
                name="api_key_id",
                ok=bool(config.coinbase.api_key_id),
                detail="COINBASE_API_KEY_ID is required",
            )
        )
        checks.append(
            PreflightCheck(
                name="api_key_secret",
                ok=bool(config.coinbase.api_key_secret),
                detail="COINBASE_API_KEY_SECRET is required",
            )
        )
        checks.append(
            PreflightCheck(
                name="portfolio_uuid",
                ok=bool(portfolio_uuid),
                detail="A portfolio UUID is required for INTX live mode",
            )
        )
        if private_client is None:
            checks.append(
                PreflightCheck(
                    name="private_reconcile",
                    ok=False,
                    detail="a private Coinbase client is required for live preflight",
                )
            )
            checks.append(
                PreflightCheck(
                    name="order_preview",
                    ok=False,
                    detail="a private Coinbase client is required for live preflight",
                )
            )
        elif portfolio_uuid:
            checks.append(_check_private_reconcile(private_client, portfolio_uuid, config.runtime.product_id))
            if preview_quantity is None:
                checks.append(
                    PreflightCheck(
                        name="order_preview",
                        ok=False,
                        detail="pass --preview-quantity to validate the live order preview path",
                    )
                )
            else:
                checks.append(
                    _check_preview(
                        private_client,
                        portfolio_uuid=portfolio_uuid,
                        product_id=config.runtime.product_id,
                        quantity=preview_quantity,
                    )
                )

    return PreflightReport(
        mode=mode,
        product_id=config.runtime.product_id,
        portfolio_uuid=portfolio_uuid,
        ready=all(check.ok for check in checks),
        checks=tuple(checks),
    )


def _check_runs_dir(runs_dir: Path) -> PreflightCheck:
    try:
        runs_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=runs_dir, prefix=".preflight-"):
            pass
    except OSError as exc:
        return PreflightCheck(name="runs_dir", ok=False, detail=str(exc))
    return PreflightCheck(name="runs_dir", ok=True, detail=f"writable: {runs_dir}")


def _check_public_market_data(public_client: PublicCheckClient, product_id: str) -> PreflightCheck:
    try:
        market = public_client.fetch_market(product_id, candle_limit=5)
    except Exception as exc:  # pragma: no cover - defensive wrapper
        return PreflightCheck(name="public_market_data", ok=False, detail=str(exc))
    return PreflightCheck(
        name="public_market_data",
        ok=True,
        detail=f"last_price={market.last_price}",
    )


def _check_private_reconcile(
    private_client: PrivateCheckClient,
    portfolio_uuid: str,
    product_id: str,
) -> PreflightCheck:
    try:
        snapshot = private_client.reconcile_intx_portfolio(
            portfolio_uuid=portfolio_uuid,
            product_id=product_id,
            fills_limit=10,
        )
    except Exception as exc:  # pragma: no cover - defensive wrapper
        return PreflightCheck(name="private_reconcile", ok=False, detail=str(exc))
    detail = f"as_of={snapshot.as_of.isoformat()}"
    return PreflightCheck(name="private_reconcile", ok=True, detail=detail)


def _check_preview(
    private_client: PrivateCheckClient,
    *,
    portfolio_uuid: str,
    product_id: str,
    quantity: float,
) -> PreflightCheck:
    try:
        preview = private_client.preview_market_order(
            portfolio_uuid=portfolio_uuid,
            product_id=product_id,
            side="BUY",
            quantity=quantity,
            client_order_id="preflight-preview",
        )
    except Exception as exc:  # pragma: no cover - defensive wrapper
        return PreflightCheck(name="order_preview", ok=False, detail=str(exc))
    if preview.errs:
        return PreflightCheck(name="order_preview", ok=False, detail="; ".join(preview.errs))
    return PreflightCheck(name="order_preview", ok=True, detail=f"preview_id={preview.preview_id}")
