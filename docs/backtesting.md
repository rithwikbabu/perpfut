# Backtesting

`perpfut` now has a historical research stack that reuses the same strategy
registry and signal code used by paper and live execution. The backtest runner
does not introduce a separate strategy API; it synthesizes the same
`MarketSnapshot` inputs that production strategies already consume.

## Design

The historical stack is bar-based and file-backed.

- Historical source: Coinbase candle history only
- Strategy inputs: the same per-asset `MarketSnapshot` used in paper/live
- Signal timing: bar close at time `t`
- Fill timing: next bar open at time `t+1`
- Output contract: the same canonical analysis payload used by `analyze`,
  operator API responses, and experiment ranking

The research stack is now split into three layers:

1. `dataset`: fetch and cache aligned OHLCV history once
2. `sleeve`: run one strategy instance over one cached dataset and persist
   reusable sleeve outputs
3. `portfolio`: combine cached sleeve return streams with the daily
   mean-variance optimizer

The minute-bar execution layer still sits above the same per-asset signals:

1. Build aligned candle snapshots across all selected products.
2. Evaluate each strategy per asset with the standard registry.
3. Convert normalized targets into shared-capital portfolio allocations.
4. Fill rebalances at the next bar open using the existing simulation model.
5. Persist run artifacts and `analysis.json`.

The optimizer layer is intentionally separate from minute-bar execution:

1. Load cached sleeve artifacts for one dataset.
2. Build daily sleeve return, turnover, and attribution series.
3. Rebalance daily across sleeves with long-only weights and cash residual.
4. Persist optimizer artifacts, weights, diagnostics, and portfolio analysis.

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

The fastest iterative workflow is to build once, then reuse `--dataset-id` in
all later backtests, sleeve studies, and optimizer runs.

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

Run research-only optimizer portfolio studies:

```bash
python3 -m perpfut portfolio run \
  --dataset-id <dataset_id> \
  --strategy-specs strategy_specs.json
```

Inspect optimizer portfolio outputs:

```bash
python3 -m perpfut portfolio list
python3 -m perpfut portfolio show --run-id <run_id>
python3 -m perpfut portfolio compare --dataset-id <dataset_id>
```

`strategy_specs.json` uses the research-only `StrategyInstanceSpec` schema from
[`docs/strategy-research.md`](./strategy-research.md). This lets you evaluate
multiple differently parameterized sleeves without changing the production
strategy registry or paper/live configuration.

Important behavior:

- invalid strategy IDs are rejected before any historical data fetches occur
- identical dataset requests reuse the same cached dataset id instead of
  refetching Coinbase
- `dataset build` and `dataset show` surface clean CLI exits for invalid ranges
  or missing datasets
- backtest suites require at least one executable cycle
- `backtest show` and `backtest compare` surface clean CLI exits for missing or
  invalid artifacts
- `backtest list` skips malformed suite manifests and returns the remaining
  readable suites
- optimizer runs reuse persisted sleeve artifacts and do not refetch Coinbase
  once the dataset and sleeves already exist

## Artifact Layout

Historical research artifacts live under `runs/backtests/`.

```text
runs/
└── backtests/
    ├── datasets/
    │   └── <dataset_id>/
    │       ├── manifest.json
    │       ├── BTC-PERP-INTX.json
    │       ├── ETH-PERP-INTX.json
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
    ├── sleeves/
    │   └── <run_id>/
    │       ├── manifest.json
    │       ├── analysis.json
    │       ├── sleeve_analysis.json
    │       ├── events.ndjson
    │       ├── fills.ndjson
    │       ├── positions.ndjson
    │       └── state.json
    ├── portfolio-runs/
    │   └── <run_id>/
    │       ├── manifest.json
    │       ├── config.json
    │       ├── state.json
    │       ├── analysis.json
    │       ├── weights.ndjson
    │       ├── diagnostics.ndjson
    │       └── contributions.json
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
- `datasets/<dataset_id>/manifest.json`: dataset identity, fingerprint, source,
  coverage, and candle counts
- `datasets/<dataset_id>/.cache/`: internal aligned-window caches used to
  accelerate repeated runs
- `runs/<run_id>/`: one strategy run over one dataset
- `sleeves/<run_id>/`: one research sleeve with reusable daily return,
  exposure, turnover, and per-asset attribution outputs embedded in
  `analysis.json` and `sleeve_analysis.json`
- `portfolio-runs/<run_id>/`: one optimizer portfolio run over cached sleeve
  outputs
- `suites/<suite_id>/`: suite manifest linking multiple strategy runs
- `control/`: local API job orchestration metadata and logs

Backtest run events are portfolio-oriented:

- `events.ndjson` includes an aggregate execution summary plus `asset_decisions`
- `fills.ndjson` stores per-asset fills within the multi-asset portfolio cycle
- `positions.ndjson` stores the aggregate portfolio and per-asset positions
- `state.json` is the latest portfolio checkpoint

Sleeve and optimizer artifacts are research-oriented:

- `sleeve_analysis.json`: sleeve daily return, turnover, drawdown, exposure,
  and per-asset contribution series
- `weights.ndjson`: optimizer weights by strategy instance and day
- `diagnostics.ndjson`: optimizer expected returns, covariance snapshot, and
  constraint status for each rebalance date
- `contributions.json`: per-strategy contribution totals and daily series

## Research Workflow

The canonical fast-iteration loop is:

1. Build or reuse a dataset once.
2. Run one or more backtest suites to validate raw strategy behavior.
3. Convert promising strategy ideas into explicit `StrategyInstanceSpec`
   sleeves.
4. Run optimizer portfolio research across cached sleeve outputs.
5. Compare portfolio runs by dataset, Sharpe, drawdown, turnover, and lineup.

That flow is documented end-to-end in
[`docs/research-workflow.md`](./research-workflow.md).

## Operator API

Historical research routes are rooted at `/api`.

- `GET /api/datasets`
- `POST /api/datasets`
- `GET /api/datasets/{datasetId}`
- `GET /api/backtests`
- `POST /api/backtests`
- `GET /api/backtests/{runId}`
- `GET /api/backtests/{runId}/analysis`
- `GET /api/backtests/{runId}/events?limit=`
- `GET /api/backtests/{runId}/positions?limit=`
- `GET /api/backtests/{runId}/fills?limit=`
- `GET /api/backtest-suites`
- `GET /api/backtest-suites/{suiteId}`
- `GET /api/sleeves`
- `GET /api/sleeve-comparisons`
- `GET /api/sleeves/{runId}`
- `GET /api/portfolio-runs`
- `POST /api/portfolio-runs`
- `GET /api/portfolio-runs/{runId}`
- `GET /api/portfolio-runs/{runId}/analysis`
- `GET /api/portfolio-run-comparisons`

`POST /api/datasets` is synchronous in v1: it builds or reuses a cached dataset
and returns the dataset summary in the same response.

`POST /api/backtests` launches one local background backtest job at a time and
returns job metadata. Job status is surfaced through the `active_job` and
`latest_job` fields on the list routes.

The list endpoints are intentionally split:

- `/api/datasets` returns cached dataset summaries
- `/api/backtests` returns completed backtest runs, the current `active_job`,
  and the most recent terminal `latest_job`
- `/api/backtest-suites` returns completed suite manifests, the current
  `active_job`, and the most recent terminal `latest_job`
- `/api/backtest-suites/{suiteId}` returns the ranked suite comparison payload
- `/api/sleeves` returns strategy sleeve summaries, optionally filtered by
  `datasetId`
- `/api/sleeve-comparisons` returns the sleeve leaderboard for one dataset
- `/api/portfolio-runs` returns optimizer portfolio run summaries, optionally
  filtered by `datasetId`
- `/api/portfolio-run-comparisons` returns the optimizer leaderboard for one
  dataset

## Constraints

This is still a bar-based MVP.

- No intrabar simulation
- No order-book replay
- No funding-rate modeling inside the backtest engine
- No database; datasets, runs, suites, sleeves, portfolio runs, and jobs are
  all artifact-backed
- Multi-asset allocation exists only in backtests for now; live and paper
  remain single-asset execution paths
- Multi-strategy optimizer research is still research-only; there is no
  multi-strategy paper/live allocator yet
