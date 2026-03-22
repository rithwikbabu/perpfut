# Research Workflow

This document describes the intended fast-iteration loop for the historical
research stack.

The goal is to avoid repeatedly downloading the same market data or rerunning
minute-bar execution when you only want to compare sleeve lineups or optimizer
settings.

## The Three Layers

### 1. Dataset

Datasets are the reusable historical market-data base.

They are fingerprinted by:

- source
- product set
- start timestamp
- end timestamp
- granularity
- dataset version

Build or reuse one dataset first:

```bash
python3 -m perpfut dataset build \
  --product-id BTC-PERP-INTX \
  --product-id ETH-PERP-INTX \
  --start 2026-01-01T00:00:00+00:00 \
  --end 2026-03-01T00:00:00+00:00 \
  --granularity ONE_MINUTE
```

Then inspect it:

```bash
python3 -m perpfut dataset list
python3 -m perpfut dataset show --dataset-id <dataset_id>
```

Use that `dataset_id` everywhere else.

### 2. Sleeve

A sleeve is one research strategy instance over one cached dataset.

Sleeves are defined by `StrategyInstanceSpec`, which adds:

- stable `strategy_instance_id`
- existing `strategy_id`
- asset universe
- strategy params
- per-sleeve risk overrides

This is the layer where you compare multiple variants of the same production
strategy code without changing the production execution interfaces.

Strategy instance specs live in JSON. See
[`docs/strategy-research.md`](./strategy-research.md) for the schema.

### 3. Portfolio Optimizer

The optimizer sits above sleeves and consumes cached sleeve daily return
streams.

V1 behavior:

- daily rebalance
- long-only strategy weights
- cash residual allowed
- max weight per strategy
- rolling lookback on sleeve daily returns
- shrinkage and ridge regularization for covariance stability

This means optimizer experiments are much faster than rerunning raw minute-bar
backtests for every lineup change.

## Recommended Loop

1. Build or reuse a dataset.
2. Run a backtest suite to sanity-check strategy behavior on that dataset.
3. Promote the promising strategy ideas into explicit sleeve specs.
4. Run one or more optimizer portfolios on top of those cached sleeves.
5. Compare optimizer runs on Sharpe, drawdown, turnover, and contribution mix.

## CLI Walkthrough

### Build the dataset once

```bash
python3 -m perpfut dataset build \
  --product-id BTC-PERP-INTX \
  --product-id ETH-PERP-INTX \
  --start 2026-01-01T00:00:00+00:00 \
  --end 2026-03-01T00:00:00+00:00
```

### Validate raw strategy behavior

```bash
python3 -m perpfut backtest run \
  --dataset-id <dataset_id> \
  --strategy-id momentum \
  --strategy-id mean_reversion
```

### Define sleeve specs

Example `strategy_specs.json`:

```json
[
  {
    "strategy_instance_id": "mom-fast",
    "strategy_id": "momentum",
    "universe": ["BTC-PERP-INTX", "ETH-PERP-INTX"],
    "strategy_params": {
      "lookback_candles": 10,
      "signal_scale": 18.0
    },
    "risk_overrides": {
      "max_abs_position": 0.3
    }
  },
  {
    "strategy_instance_id": "mr-slow",
    "strategy_id": "mean_reversion",
    "universe": ["BTC-PERP-INTX", "ETH-PERP-INTX"],
    "strategy_params": {
      "lookback_candles": 40,
      "signal_scale": 8.0
    },
    "risk_overrides": {
      "max_abs_position": 0.2
    }
  }
]
```

### Run optimizer research

```bash
python3 -m perpfut portfolio run \
  --dataset-id <dataset_id> \
  --strategy-specs strategy_specs.json
```

### Compare optimizer runs

```bash
python3 -m perpfut portfolio list --dataset-id <dataset_id>
python3 -m perpfut portfolio compare --dataset-id <dataset_id>
python3 -m perpfut portfolio show --run-id <run_id>
```

## Frontend Walkthrough

The backtests console now has three research sections:

- `Datasets`
- `Strategy Sleeves`
- `Portfolio Optimizer`

Recommended UI flow:

1. Build or select a cached dataset in `Datasets`.
2. Use that dataset context to inspect sleeves in `Strategy Sleeves`.
3. Inspect optimizer runs and rankings in `Portfolio Optimizer`.
4. Open a backtest run detail page when you need full minute-bar execution
   context.

The selected dataset acts as the scoping key for sleeves and optimizer runs in
the UI.

## Artifact Lineage

The lineage should always be read as:

```text
dataset -> backtest run / sleeve -> portfolio optimizer run
```

More concretely:

- one `dataset_id` can feed many backtest suites
- one `dataset_id` can feed many sleeves
- one optimizer run references one dataset and a lineup of sleeves

When something looks wrong in optimizer results, debug in this order:

1. dataset coverage and candle counts
2. sleeve-level return and attribution behavior
3. optimizer weights and diagnostics

## When To Rebuild Data

Rebuild or build a new dataset when:

- the product set changes
- the time window changes
- the granularity changes
- the dataset schema/version changes

Do not rebuild when:

- you are only changing sleeve parameters
- you are only changing optimizer lookback or constraints
- you are only comparing lineups on the same historical range

That is the core speed principle in this stack.
