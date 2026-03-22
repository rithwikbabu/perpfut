# Backtesting

`perpfut` now has a historical backtesting system that reuses the same
strategy registry and signal code used by paper and live execution. The
backtest runner does not introduce a separate strategy API; it synthesizes the
same `MarketSnapshot` inputs that production strategies already consume.

## Design

Backtests are bar-based and file-backed.

- Historical source: Coinbase candle history only
- Strategy inputs: the same per-asset `MarketSnapshot` used in paper/live
- Signal timing: bar close at time `t`
- Fill timing: next bar open at time `t+1`
- Portfolio model: shared-capital, multi-asset allocator for backtests only
- Output contract: the same canonical analysis payload used by `analyze`,
  operator API responses, and experiment ranking

The backtest portfolio layer sits above per-asset signals:

1. Build aligned candle snapshots across all selected products.
2. Evaluate each strategy per asset with the standard registry.
3. Convert normalized targets into shared-capital portfolio allocations.
4. Fill rebalances at the next bar open using the existing simulation model.
5. Persist run artifacts and `analysis.json`.

## CLI

Build or reuse a cached dataset:

```bash
python3 -m perpfut dataset build \
  --product-id BTC-PERP-INTX \
  --product-id ETH-PERP-INTX \
  --start 2026-03-20T00:00:00+00:00 \
  --end 2026-03-21T00:00:00+00:00 \
  --granularity ONE_MINUTE
```

Inspect cached datasets:

```bash
python3 -m perpfut dataset list
python3 -m perpfut dataset show --dataset-id <dataset_id>
```

Launch a backtest suite from a dataset definition:

```bash
python3 -m perpfut backtest run \
  --product-id BTC-PERP-INTX \
  --product-id ETH-PERP-INTX \
  --strategy-id momentum \
  --strategy-id mean_reversion \
  --start 2026-03-20T00:00:00+00:00 \
  --end 2026-03-21T00:00:00+00:00 \
  --granularity ONE_MINUTE \
  --starting-collateral-usdc 10000 \
  --max-abs-position 0.5 \
  --max-gross-position 1.0 \
  --max-leverage 2.0 \
  --slippage-bps 3
```

Launch a backtest suite from an already-built dataset:

```bash
python3 -m perpfut backtest run \
  --dataset-id <dataset_id> \
  --strategy-id momentum \
  --strategy-id mean_reversion
```

Inspect backtest outputs:

```bash
python3 -m perpfut backtest list
python3 -m perpfut backtest show --run-id <run_id>
python3 -m perpfut backtest compare --suite-id <suite_id>
```

Important behavior:

- invalid strategy IDs are rejected before any historical data fetches occur
- identical dataset requests reuse the same cached dataset id instead of refetching Coinbase
- `dataset build`/`dataset show` surface clean CLI exits for invalid ranges or missing datasets
- backtest suites require at least one executable cycle
- `backtest show` and `backtest compare` surface clean CLI exits for missing or
  invalid artifacts
- `backtest list` skips malformed suite manifests and returns the remaining
  readable suites

## Artifact Layout

Backtest artifacts live under `runs/backtests/`.

```text
runs/
└── backtests/
    ├── datasets/
    │   └── <dataset_id>/
    │       ├── manifest.json
    │       ├── BTC-PERP-INTX.json
    │       └── ETH-PERP-INTX.json
    │       └── .cache/
    │           └── aligned_windows_lookback_<n>_<product_hash>.json
    ├── runs/
    │   └── <run_id>/
    │       ├── manifest.json
    │       ├── analysis.json
    │       ├── events.ndjson
    │       ├── fills.ndjson
    │       ├── positions.ndjson
    │       └── state.json
    ├── suites/
    │   └── <suite_id>/
    │       └── manifest.json
    └── control/
        ├── active_backtest.json
        ├── active_backtest.lock
        ├── <job_id>.log
        └── jobs/
            └── <job_id>.json
```

Artifacts mean:

- `datasets/<dataset_id>/`: persisted historical candle inputs for reuse
- `datasets/<dataset_id>/manifest.json`: dataset identity, fingerprint, source, coverage, and candle counts
- `datasets/<dataset_id>/.cache/`: internal aligned-window caches used to accelerate repeated runs
- `runs/<run_id>/`: one strategy run over one dataset
- `suites/<suite_id>/`: suite manifest linking multiple strategy runs
- `control/`: local API job orchestration metadata and logs

Backtest run events are portfolio-oriented:

- `events.ndjson` includes an aggregate execution summary plus `asset_decisions`
- `fills.ndjson` stores per-asset fills within the multi-asset portfolio cycle
- `positions.ndjson` stores the aggregate portfolio and per-asset positions
- `state.json` is the latest portfolio checkpoint

## Operator API

Backtest routes are rooted at `/api`.

- `GET /api/backtests`
- `GET /api/datasets`
- `POST /api/datasets`
- `GET /api/datasets/{datasetId}`
- `POST /api/backtests`
- `GET /api/backtests/{runId}`
- `GET /api/backtests/{runId}/analysis`
- `GET /api/backtests/{runId}/events?limit=`
- `GET /api/backtests/{runId}/positions?limit=`
- `GET /api/backtests/{runId}/fills?limit=`
- `GET /api/backtest-suites`
- `GET /api/backtest-suites/{suiteId}`

`POST /api/datasets` is synchronous in v1: it builds or reuses a cached dataset
and returns the dataset summary in the same response.

`POST /api/backtests` launches one local background backtest job at a time and
returns job metadata. Job status is surfaced through the `active_job` field on
the list routes.

Example dataset build request:

```json
{
  "productIds": ["BTC-PERP-INTX", "ETH-PERP-INTX"],
  "start": "2026-03-20T00:00:00+00:00",
  "end": "2026-03-21T00:00:00+00:00",
  "granularity": "ONE_MINUTE"
}
```

Example request:

```json
{
  "datasetId": "20260322T120000000000Z",
  "strategyIds": ["momentum", "mean_reversion"],
  "startingCollateralUsdc": 10000,
  "maxAbsPosition": 0.5,
  "maxGrossPosition": 1.0,
  "maxLeverage": 2.0,
  "slippageBps": 3
}
```

The list endpoints are intentionally split:

- `/api/datasets` returns cached dataset summaries
- `/api/backtests` returns completed backtest runs, the current `active_job`,
  and the most recent terminal `latest_job`
- `/api/backtest-suites` returns completed suite manifests, the current
  `active_job`, and the most recent terminal `latest_job`
- `/api/backtest-suites/{suiteId}` returns the ranked suite comparison payload

## Constraints

This is still a bar-based MVP.

- No intrabar simulation
- No order-book replay
- No funding-rate modeling inside the backtest engine
- No database; datasets, runs, suites, and jobs are all artifact-backed
- Multi-asset allocation exists only in backtests for now; live and paper remain
  single-asset execution paths
