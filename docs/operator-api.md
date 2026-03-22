# Operator API

`perpfut` exposes a local-only operator API for the Next.js dashboard.

The current dashboard is monitor-first. Read routes are already consumed by the
UI, while the paper-run control routes are available for the next frontend step.

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

### Control routes

- `POST /api/paper-runs`
- `POST /api/paper-runs/stop`
- `POST /api/datasets`
- `POST /api/backtests`

Start requests accept:

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

### Dashboard Overview Shape

`GET /api/dashboard/overview` now returns:

- `latest_run`: newest readable run matching the requested mode
- `latest_state`: raw latest checkpoint payload for the run
- `latest_decision`: normalized operator-facing decision summary derived from the latest checkpoint
- `latest_analysis`: canonical performance summary derived from the run artifacts
- `recent_events`, `recent_fills`, `recent_positions`: newest-first artifact rows

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

`GET /api/runs/{runId}/analysis` returns the same canonical analysis payload used by
`latest_analysis`, including:

- run identity: `run_id`, `mode`, `product_id`, `strategy_id`
- timing: `started_at`, `ended_at`, `cycle_count`
- pnl and return: `starting_equity_usdc`, `ending_equity_usdc`, `realized_pnl_usdc`, `unrealized_pnl_usdc`, `total_pnl_usdc`, `total_return_pct`
- risk and activity: `max_drawdown_usdc`, `max_drawdown_pct`, `turnover_usdc`, `fill_count`, `trade_count`
- exposure and decisions: `avg_abs_exposure_pct`, `max_abs_exposure_pct`, `decision_counts`
- chart series: `equity_series`, `drawdown_series`, `exposure_series`

### Backtest API Shape

`GET /api/datasets` returns:

- `items`: newest-first cached datasets with fingerprint, source, coverage, and candle counts
- `count`

`GET /api/datasets/{datasetId}` returns:

- dataset identity: `datasetId`, `createdAt`, `fingerprint`, `source`, `version`
- coverage: `products`, `start`, `end`, `granularity`
- counts: `candleCounts`

`GET /api/backtests` returns:

- `items`: newest-first completed backtest runs with canonical metrics
- `count`: number of returned runs
- `active_job`: the current in-flight backtest job, or `null`

`GET /api/backtests/{runId}` returns:

- `manifest`
- `state`
- `analysis`

`GET /api/backtest-suites` returns:

- `items`: newest-first suite manifests
- `count`
- `active_job`

`GET /api/backtest-suites/{suiteId}` returns:

- suite identity: `suite_id`, `created_at`, `dataset_id`
- suite scope: `products`, `strategies`, `run_ids`
- ranking metadata: `ranking_policy`
- ranked items with canonical performance metrics per run

## Design Notes

- The API does not maintain in-memory trading state for the UI.
- Dashboard responses are derived from the newest readable artifact files.
- Paper runs are launched by spawning `python3 -m perpfut paper ...`.
- Dataset builds are handled synchronously inside the API process in v1.
- Backtest suites are launched by spawning `python3 -m perpfut backtest run ...`.
- Stop requests send `SIGTERM`, then escalate to `SIGKILL` after 5 seconds.
- Process metadata writes are atomic and protected by a local control lock.
- Backtest jobs persist status to `runs/backtests/control/jobs/<job_id>.json`.
- Live mode remains read-only in the UI. There are no live-trading control routes.

## Frontend Expectations

- Poll every 2 seconds.
- Treat missing latest runs as an empty state, not an error.
- Treat `409` on `POST /api/paper-runs` as "paper run already active".
- Treat `409` on `POST /api/backtests` as "backtest job already active".
- Treat `500` on control routes as operator-visible failures that should not be retried blindly.
- Use `/api/dashboard/overview` for the landing page and `/api/runs/{runId}/...` for drill-down views.
- Use `/api/backtests` and `/api/backtest-suites/...` for the backtest console.
