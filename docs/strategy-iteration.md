# Strategy Iteration

`perpfut` now supports a narrow offline strategy-iteration loop on top of the
same artifact and reporting contracts used by normal paper runs.

## Workflow

1. Produce a source run with recorded cycle markets.

```bash
python3 -m perpfut paper --iterations 30 --interval-seconds 60
```

2. Create one or more experiment replays from that source run.

```bash
python3 -m perpfut experiment \
  --source-run-id 20260322T020000000000Z_source \
  --strategy-id momentum
```

```bash
python3 -m perpfut experiment \
  --source-run-id 20260322T020000000000Z_source \
  --strategy-id mean_reversion \
  --lookback-candles 30 \
  --signal-scale 20
```

3. Rank the experiment outputs tied to the same source run.

```bash
python3 -m perpfut compare-experiments \
  --source-run-id 20260322T020000000000Z_source
```

The comparison command returns JSON with:

- `source_run_id`
- `baseline`
- `ranking_policy`
- `experiments_count`
- ranked `items`

Ranking is deterministic and currently uses:

- `total_return_pct` descending
- `max_drawdown_pct` ascending
- `turnover_usdc` ascending
- `fill_count` ascending
- `run_id` ascending

This keeps the sort tied directly to the canonical analysis contract instead of
introducing a separate opaque score.

## Artifact Layout

Experiments live under:

```text
runs/
└── experiments/
    └── <timestamp>_<gitsha>/
```

Each experiment directory contains:

- `manifest.json`
- `config.json`
- `events.ndjson`
- `fills.ndjson`
- `positions.ndjson`
- `state.json`
- `analysis.json`

The manifest includes the source run identity and strategy parameters used for
the replay. `analysis.json` is persisted using the same canonical analysis shape
as `perpfut analyze`.

## Recommended Review Flow

1. Start with one source run and keep it fixed while comparing candidates.
2. Replay strategy variants with only a few parameter changes at a time.
3. Use `compare-experiments` to rank candidates quickly.
4. Use `analyze` on the winning experiment if you need the full canonical
   payload.
5. Inspect the experiment artifacts directly when a candidate behaves
   unexpectedly.
