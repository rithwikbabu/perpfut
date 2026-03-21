# Investigate Failure

Use this playbook when a paper or live cycle behaves unexpectedly.

## Steps

1. Read the newest run directory in `runs/`
2. Compare `events.ndjson`, `fills.ndjson`, `positions.ndjson`, and `state.json`
3. Isolate whether the issue came from market data, signal generation, risk
   gating, or fill/state transition logic
4. Add a regression test before changing code

## Hints

- Paper-mode issues usually reproduce well with fixture-backed tests
- Keep telemetry changes backward compatible when possible
