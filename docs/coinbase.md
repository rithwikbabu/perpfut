# Coinbase Notes

This repo is scoped around Coinbase Advanced Trade and its INTX perpetuals path.

## Public Endpoints Used Now

- `GET /market/products`
- `GET /market/products/{product_id}/candles`
- `GET /market/products/{product_id}/ticker`

The public endpoints are cached for 1 second unless `cache-control: no-cache` is
set.

The repo keeps raw public fixtures for products, candles, and ticker responses
under `tests/fixtures/coinbase/`. Parsing logic should be validated against
those saved payloads before public adapter changes are merged.

## Private Endpoints Planned Next

- `POST /orders`
- `POST /orders/preview`
- `GET /orders/historical/fills`
- `GET /orders/historical/{order_id}`
- `GET /orders/historical/batch`
- `POST /orders/batch_cancel`
- `GET /intx/portfolio`
- `GET /intx/positions`
- `GET /intx/balances`
- `POST /intx/allocate`

## Important Constraints

- Coinbase perpetuals are region-gated and require onboarding.
- INTX perpetuals use a dedicated portfolio and USDC margin.
- Coinbase documents a 10 USDC minimum order notional for perps.
- Coinbase documents leverage up to 10x.
- The Advanced Trade sandbox is mocked and static, so internal paper trading is
  still necessary.

## Auth Notes

- Coinbase App APIs require CDP secret API keys.
- Coinbase App authentication for Advanced Trade currently requires ECDSA keys.
- JWTs are request-scoped and expire after 2 minutes.
- The repo should eventually own a dedicated token provider abstraction rather
  than scattering JWT construction across the codebase.
- Required env vars for read-only INTX access are `COINBASE_API_KEY_ID`,
  `COINBASE_API_KEY_SECRET`, and `COINBASE_INTX_PORTFOLIO_UUID`.

## INTX Fields Worth Logging

When live mode is added, prefer exchange-reported values where available:

- `unrealized_pnl`
- `aggregated_pnl`
- `mark_price`
- `liquidation_price`
- `buying_power`
- `total_balance`

The repo now includes a read-only `reconcile` CLI path that should remain safe:
it authenticates, fetches INTX portfolio summary, balances, positions, and fills,
then prints normalized exchange truth without placing or previewing orders.

The live path remains intentionally narrow:

- explicit env gate via `PERPFUT_ENABLE_LIVE=1`
- one cycle by default unless `--iterations` is passed
- preview before submit
- market IOC orders only
- batch cancel only for halt/recovery paths
