# Event Schema

Each run writes immutable artifacts under `runs/<timestamp>_<gitsha>/`.

## Files

- `manifest.json`: run metadata
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
- `order_intent`
- `fill`
- `position`

## Design Rules

- Artifacts are append-only except for `state.json`.
- Favor explicit names over compact encodings.
- Keep fields stable once downstream analysis depends on them.
