# Performance Reporting

`perpfut` exposes one canonical performance contract for run analysis. The same
payload shape is used by the CLI, the operator API, and the Next.js dashboard.

## What The Analysis Contains

Canonical run analysis includes:

- run identity: `run_id`, `mode`, `product_id`, `strategy_id`
- timing: `started_at`, `ended_at`, `cycle_count`
- PnL and return: `starting_equity_usdc`, `ending_equity_usdc`, `realized_pnl_usdc`, `unrealized_pnl_usdc`, `total_pnl_usdc`, `total_return_pct`
- risk and activity: `max_drawdown_usdc`, `max_drawdown_pct`, `turnover_usdc`, `fill_count`, `trade_count`
- exposure: `avg_abs_exposure_pct`, `max_abs_exposure_pct`
- decision mix: `decision_counts`
- chart series: `equity_series`, `drawdown_series`, `exposure_series`

The canonical payload is derived from run artifacts on demand. It is not stored
in a database and does not depend on in-memory engine state.

`trade_count` is reserved for future order-level reporting. Today it should be
treated as fill-derived activity rather than true exchange-order count, so the
operator-facing surfaces use `fill_count`.

## CLI

Analyze a specific run:

```bash
python3 -m perpfut analyze --run-id 20260322T020000000000Z_demo
```

Analyze the latest paper run:

```bash
python3 -m perpfut analyze --mode paper
```

Analyze the latest live run for a product:

```bash
python3 -m perpfut analyze --mode live --product-id BTC-PERP-INTX
```

CLI output is JSON. The most important fields for a quick read are:

- `total_pnl_usdc`
- `total_return_pct`
- `max_drawdown_pct`
- `turnover_usdc`
- `fill_count`
- `avg_abs_exposure_pct`

If analysis inputs are missing or malformed, the CLI exits with a user-facing
error instead of printing a traceback.

## API

Performance reporting is available through:

- `GET /api/runs/{runId}/analysis`
- `GET /api/dashboard/overview?mode=paper|live`

The dashboard overview includes:

- `latest_run`
- `latest_state`
- `latest_decision`
- `latest_analysis`

Example:

```bash
curl -s http://127.0.0.1:8000/api/runs/20260322T020000000000Z_demo/analysis | jq
```

Use the overview route when you want the latest matching run for a mode. Use the
per-run analysis route when you want a stable drill-down payload.

## UI

The operator console reads the canonical analysis payload in two places:

- `/`
  - top-line performance cards
  - equity curve
  - drawdown chart
  - exposure chart
  - decision-count summary
- `/runs/<run_id>`
  - canonical analysis summary
  - run-level equity, drawdown, and exposure charts
  - decision-count summary alongside raw artifacts

If canonical analysis is unavailable for a run, the UI keeps the artifact pages
readable and shows an explicit reporting fallback instead of failing the whole
view.

## Recommended Review Flow

1. Confirm the run exists with `python3 -m perpfut runs --limit 5`.
2. Inspect final checkpoint state with `python3 -m perpfut state --mode paper`.
3. Analyze the run with `python3 -m perpfut analyze --run-id ...`.
4. Open the dashboard and compare the cards/charts with the CLI output.
5. Use the run detail page for drill-down into fills, events, and decision mix.
