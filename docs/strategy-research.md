# Strategy Research Contracts

Research-only multi-sleeve work in `perpfut` now uses an explicit
`StrategyInstanceSpec` contract instead of overloading the single live/paper
`StrategyConfig`.

## Why this exists

Paper and live execution still run one strategy configuration at a time. The
research stack needs more structure:

- multiple instances of the same strategy with different parameters
- explicit asset universes per sleeve
- per-sleeve risk overrides
- stable ids that persist into sleeve and optimizer artifacts

`StrategyInstanceSpec` adds that layer without changing the existing
single-strategy paper/live paths.

## Schema

Strategy-instance specs are encoded as a JSON array of objects:

```json
[
  {
    "strategy_instance_id": "mom-fast-btc",
    "strategy_id": "momentum",
    "universe": ["BTC-PERP-INTX"],
    "strategy_params": {
      "lookback_candles": 10,
      "signal_scale": 20.0
    },
    "risk_overrides": {
      "max_abs_position": 0.3,
      "rebalance_threshold": 0.05
    }
  }
]
```

Required fields:

- `strategy_instance_id`: stable unique id for the sleeve
- `strategy_id`: existing registry-backed strategy id
- `universe`: non-empty list of unique products

Optional fields:

- `strategy_params`
- `risk_overrides`

Allowed `strategy_params` in v1:

- `lookback_candles`
- `signal_scale`

Allowed `risk_overrides` in v1:

- `max_abs_position`
- `max_gross_position`
- `rebalance_threshold`
- `min_trade_notional_usdc`
- `max_daily_drawdown_usdc`

## Validation guarantees

- duplicate `strategy_instance_id` values are rejected
- unknown `strategy_id` values are rejected against the production registry
- duplicate products in `universe` are rejected
- unknown parameter keys are rejected
- numeric overrides must be valid and non-negative

## Backward compatibility

This contract is research-only. Existing `StrategyConfig` behavior remains the
same for paper, live, experiments, and the current backtest suite entrypoints.

The new helper module lives at
`src/perpfut/strategy_instances.py` and exposes:

- `parse_strategy_instance_specs(...)`
- `load_strategy_instance_specs(...)`
- `StrategyInstanceSpec.to_strategy_config(...)`
- `StrategyInstanceSpec.to_risk_config(...)`
