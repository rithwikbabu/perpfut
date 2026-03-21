# Add Signal

Use this playbook when modifying or adding a strategy signal.

## Rules

- Keep the strategy pure.
- Accept candles, return a normalized target position.
- Do not add Coinbase-specific response parsing to strategy code.
- Add or update unit tests for target scaling and clipping behavior.

## Files

- Strategy logic: `src/perpfut/signal_momentum.py`
- Trading invariants: `docs/trading-contract.md`
- Tests: `tests/unit/`
