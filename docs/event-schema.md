# Event Schema

Each run writes immutable artifacts under `runs/<timestamp>_<gitsha>/`.

## Files

- `manifest.json`: run metadata
  - `run_id`
  - `created_at`
  - `mode`
  - `product_id`
  - `strategy_id`
  - `git_sha`
  - `resumed_from_run_id`
- `config.json`: effective runtime config
- `events.ndjson`: one high-level event per cycle
- `fills.ndjson`: simulated or live fills
- `positions.ndjson`: post-cycle position snapshots
- `state.json`: latest checkpoint

## Event Fields

Every cycle event should include:

- `run_id`
- `cycle_id`
- `mode`
- `product_id`
- `timestamp`
- `market`
- `signal`
- `target_position`
- `risk_decision`
- `execution_summary`
- `no_trade_reason`
- `order_intent`
- `fill`
- `position`

## Decision Fields

`no_trade_reason` is structured for operator and reporting use:

- `code`
- `message`

`risk_decision` captures the cycle-level risk state:

- `target_before_risk`
- `target_after_risk`
- `current_position`
- `target_notional_usdc`
- `current_notional_usdc`
- `delta_notional_usdc`
- `rebalance_threshold`
- `min_trade_notional_usdc`
- `halted`
- `rebalance_eligible`

`execution_summary` provides the operator-facing cycle outcome:

- `action`
- `reason_code`
- `reason_message`
- `summary`

## Design Rules

- Artifacts are append-only except for `state.json`.
- Favor explicit names over compact encodings.
- Keep fields stable once downstream analysis depends on them.
