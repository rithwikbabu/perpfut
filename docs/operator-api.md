# Operator API

`perpfut` exposes a local-only operator API for the Next.js dashboard and the
historical research console.

The API is artifact-backed. It does not maintain an in-memory trading or
research state model for the UI; instead it reads the newest valid files under
`runs/` and `runs/backtests/`.

## Runtime

- API host: `127.0.0.1:8000`
- Frontend host: `127.0.0.1:3000`
- Source of truth: run artifacts under `runs/`
- Active paper control state: `runs/control/active_paper.json`
- Paper control log: `runs/control/paper.log`
- Active backtest control state: `runs/backtests/control/active_backtest.json`
- Backtest job logs: `runs/backtests/control/<job_id>.log`

Start the API with:

```bash
python3 -m perpfut api
```

## Contract

All routes are rooted at `/api`.

### Read routes

- `GET /api/health`
- `GET /api/dashboard/overview?mode=paper|live&limit=`
- `GET /api/runs?mode=&limit=`
- `GET /api/runs/{runId}/manifest`
- `GET /api/runs/{runId}/state`
- `GET /api/runs/{runId}/events?limit=`
- `GET /api/runs/{runId}/fills?limit=`
- `GET /api/runs/{runId}/positions?limit=`
- `GET /api/runs/{runId}/analysis`
- `GET /api/paper-runs/active`
- `GET /api/datasets`
- `GET /api/datasets/{datasetId}`
- `GET /api/backtests`
- `GET /api/backtests/{runId}`
- `GET /api/backtests/{runId}/analysis`
- `GET /api/backtests/{runId}/events?limit=`
- `GET /api/backtests/{runId}/fills?limit=`
- `GET /api/backtests/{runId}/positions?limit=`
- `GET /api/backtest-suites`
- `GET /api/backtest-suites/{suiteId}`
- `GET /api/sleeves`
- `GET /api/sleeve-comparisons`
- `GET /api/sleeves/{runId}`
- `GET /api/portfolio-runs`
- `GET /api/portfolio-run-comparisons`
- `GET /api/portfolio-runs/{runId}`
- `GET /api/portfolio-runs/{runId}/analysis`

### Control routes

- `POST /api/paper-runs`
- `POST /api/paper-runs/stop`
- `POST /api/datasets`
- `POST /api/backtests`
- `POST /api/portfolio-runs`

## Paper Requests

Paper-run start requests accept:

```json
{
  "productId": "BTC-PERP-INTX",
  "strategyId": "momentum",
  "iterations": 1440,
  "intervalSeconds": 60,
  "startingCollateralUsdc": 10000
}
```

`strategyId` currently defaults to `momentum` when omitted.

The service allows only one active paper run at a time.

## Dataset Requests

Dataset build requests accept:

```json
{
  "productIds": ["BTC-PERP-INTX", "ETH-PERP-INTX"],
  "start": "2026-03-20T00:00:00+00:00",
  "end": "2026-03-21T00:00:00+00:00",
  "granularity": "ONE_MINUTE"
}
```

Dataset builds are synchronous in v1 and return the dataset summary directly.
Requests must use timezone-aware timestamps.

The returned dataset summary is the cache anchor for all later research:

- `datasetId`
- `fingerprint`
- `source`
- `version`
- `products`
- `start`
- `end`
- `granularity`
- `candleCounts`

## Backtest Requests

Backtest launch requests accept either a cached dataset id:

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

or an inline historical range:

```json
{
  "productIds": ["BTC-PERP-INTX", "ETH-PERP-INTX"],
  "strategyIds": ["momentum", "mean_reversion"],
  "start": "2026-03-20T00:00:00+00:00",
  "end": "2026-03-21T00:00:00+00:00",
  "granularity": "ONE_MINUTE",
  "startingCollateralUsdc": 10000,
  "maxAbsPosition": 0.5,
  "maxGrossPosition": 1.0,
  "maxLeverage": 2.0,
  "slippageBps": 3
}
```

The service currently allows only one active backtest job at a time.

Backtest job progress is surfaced through `active_job` and `latest_job` on the
list routes. The UI should treat these as the canonical status source for:

- current phase
- phase message
- completed runs versus total runs
- progress percentage
- elapsed seconds
- ETA seconds
- terminal error, if any

## Research Stack Requests

The research stack adds two higher-level API domains on top of datasets and
backtests:

1. `sleeves`: strategy-instance studies over one cached dataset
2. `portfolio-runs`: optimizer studies over cached sleeve outputs

### Sleeve routes

- `GET /api/sleeves`
- `GET /api/sleeves?datasetId=<dataset_id>`
- `GET /api/sleeve-comparisons`
- `GET /api/sleeve-comparisons?datasetId=<dataset_id>`
- `GET /api/sleeves/{runId}`

Sleeve list responses are newest-first summaries keyed by dataset and strategy
instance. Sleeve detail responses include:

- `manifest`
- `state`
- canonical `analysis`
- `sleeve_analysis` with per-asset contribution totals

### Portfolio optimizer routes

- `GET /api/portfolio-runs`
- `GET /api/portfolio-runs?datasetId=<dataset_id>`
- `GET /api/portfolio-run-comparisons`
- `GET /api/portfolio-run-comparisons?datasetId=<dataset_id>`
- `GET /api/portfolio-runs/{runId}`
- `GET /api/portfolio-runs/{runId}/analysis`
- `POST /api/portfolio-runs`

`POST /api/portfolio-runs` accepts:

```json
{
  "datasetId": "20260322T120000000000Z",
  "startingCapitalUsdc": 10000,
  "lookbackDays": 60,
  "maxStrategyWeight": 0.4,
  "covarianceShrinkage": 0.1,
  "ridgePenalty": 0.001,
  "turnoverCostBps": 2.0,
  "strategyInstances": [
    {
      "strategyInstanceId": "mom-fast",
      "strategyId": "momentum",
      "universe": ["BTC-PERP-INTX", "ETH-PERP-INTX"],
      "strategyParams": {
        "lookback_candles": 10,
        "signal_scale": 20.0
      },
      "riskOverrides": {
        "max_abs_position": 0.3
      }
    }
  ]
}
```

The top-level API request uses camelCase field names. The nested
`strategyParams` and `riskOverrides` objects keep the snake_case keys from the
research-only `StrategyInstanceSpec` contract.

Portfolio detail responses include:

- `manifest`
- `config`
- `state`
- `analysis`
- `weights`
- `diagnostics`
- `contributions`

These routes are what power the frontend optimizer views for:

- run list and selection
- Sharpe, return, drawdown, and turnover summaries
- daily weight history
- per-strategy contribution attribution

## Dashboard Overview Shape

`GET /api/dashboard/overview` returns:

- `latest_run`: newest readable run matching the requested mode
- `latest_state`: raw latest checkpoint payload for the run
- `latest_decision`: normalized operator-facing decision summary derived from
  the latest checkpoint
- `latest_analysis`: canonical performance summary derived from the run
  artifacts
- `recent_events`, `recent_fills`, `recent_positions`: newest-first artifact
  rows

`latest_decision` contains:

- `cycle_id`
- `mode`
- `product_id`
- `signal`
- `risk_decision`
- `execution_summary`
- `no_trade_reason`
- `order_intent`
- `fill`

The nested decision objects use the same field names written into run artifacts.

`GET /api/runs/{runId}/analysis` returns the same canonical analysis payload
used by `latest_analysis`, including:

- run identity: `run_id`, `mode`, `product_id`, `strategy_id`
- timing: `started_at`, `ended_at`, `cycle_count`
- pnl and return: `starting_equity_usdc`, `ending_equity_usdc`,
  `realized_pnl_usdc`, `unrealized_pnl_usdc`, `total_pnl_usdc`,
  `total_return_pct`
- risk and activity: `max_drawdown_usdc`, `max_drawdown_pct`, `turnover_usdc`,
  `fill_count`, `trade_count`
- exposure and decisions: `avg_abs_exposure_pct`, `max_abs_exposure_pct`,
  `decision_counts`
- chart series: `equity_series`, `drawdown_series`, `exposure_series`

## Backtest and Research Response Shape

`GET /api/datasets` returns:

- `items`: newest-first cached datasets with fingerprint, source, coverage, and
  candle counts
- `count`

`GET /api/backtests` returns:

- `items`: newest-first completed backtest runs with canonical metrics
- `count`
- `active_job`: the current in-flight backtest job, or `null`
- `latest_job`: the most recent terminal backtest job, or `null`

`GET /api/backtest-suites` returns:

- `items`: newest-first suite manifests
- `count`
- `active_job`
- `latest_job`

`GET /api/backtest-suites/{suiteId}` returns:

- suite identity: `suite_id`, `created_at`, `dataset_id`
- suite scope: `products`, `strategies`, `run_ids`
- ranking metadata: `ranking_policy`
- date coverage: `date_range_start`, `date_range_end`
- summary risk metric: `sharpe_ratio`
- ranked items with canonical performance metrics per run

`GET /api/sleeve-comparisons` returns:

- `dataset_id`
- `ranking_policy`
- ranked sleeve items with return, drawdown, turnover, exposure, and per-asset
  contribution totals

`GET /api/portfolio-run-comparisons` returns:

- `dataset_id`
- `ranking_policy`
- ranked optimizer runs with Sharpe, return, drawdown, turnover, gross-weight,
  and strategy-lineup metadata

## Design Notes

- The API does not maintain in-memory trading state for the UI.
- Dashboard responses are derived from the newest readable artifact files.
- Paper runs are launched by spawning `python3 -m perpfut paper ...`.
- Dataset builds are handled synchronously inside the API process in v1.
- Backtest suites are launched by spawning `python3 -m perpfut backtest run ...`.
- Optimizer portfolio runs are executed inline inside the API process in v1.
- Stop requests send `SIGTERM`, then escalate to `SIGKILL` after 5 seconds.
- Process metadata writes are atomic and protected by a local control lock.
- Backtest jobs persist status to `runs/backtests/control/jobs/<job_id>.json`.
- Live mode remains read-only in the UI. There are no live-trading control
  routes.

## Frontend Expectations

- Poll every 2 seconds.
- Treat missing latest runs as an empty state, not an error.
- Treat `409` on `POST /api/paper-runs` as "paper run already active".
- Treat `409` on `POST /api/backtests` as "backtest job already active".
- Treat `500` on control routes as operator-visible failures that should not be
  retried blindly.
- Use `/api/dashboard/overview` for the landing page and `/api/runs/{runId}/...`
  for drill-down views.
- Use `/api/datasets`, `/api/backtests`, `/api/backtest-suites`,
  `/api/sleeves`, and `/api/portfolio-runs` for the research console.
