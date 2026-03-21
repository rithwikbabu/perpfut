# Coinbase Notes

This repo is scoped around Coinbase Advanced Trade and its INTX perpetuals path.

## Public Endpoints Used Now

- `GET /market/products`
- `GET /market/products/{product_id}/candles`
- `GET /market/products/{product_id}/ticker`

The public endpoints are cached for 1 second unless `cache-control: no-cache` is
set.

The repo keeps real public payload fixtures under `tests/fixtures/coinbase/` and
expects public parsing to be covered by fixture-backed tests rather than only
live network calls.

Current normalization assumptions for the public adapter:

- product discovery reads the `products` list from the response root
- candle payloads may arrive newest-first and are sorted oldest-first locally
- ticker parsing uses the first trade for `last_price` and `as_of`
- missing numeric or timestamp fields should raise exchange-specific parse errors

## Private Endpoints Planned Next

- `POST /orders`
- `POST /orders/preview`
- `GET /orders/historical/fills`
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
- Advanced Trade SDK usage requires ECDSA keys.
- JWTs are request-scoped and expire after 2 minutes.
- The repo should eventually own a dedicated token provider abstraction rather
  than scattering JWT construction across the codebase.

## INTX Fields Worth Logging

When live mode is added, prefer exchange-reported values where available:

- `unrealized_pnl`
- `aggregated_pnl`
- `mark_price`
- `liquidation_price`
- `buying_power`
- `total_balance`
