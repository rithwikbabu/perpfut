# Architecture

## Goal

Validate the full loop for one Coinbase perpetual futures product:

1. fetch market data
2. compute a continuous target position
3. size the rebalance
4. simulate or execute the order
5. reconcile state
6. write artifacts

## Runtime Shape

The runtime is a single-process polling loop.

- `exchange_coinbase.py` fetches Coinbase market data and will later own private
  auth plus live order routing.
- `signal_momentum.py` converts candles into a normalized target position.
- `risk.py` clips targets, enforces drawdown limits, and decides whether a trade
  is worth sending.
- `sim.py` turns an order intent into a fill and updates position state.
- `engine.py` orchestrates the cycle.
- `telemetry.py` writes append-only artifacts under `runs/`.

## Boundaries

Keep these boundaries strict:

- Domain logic must not know about HTTP, JWTs, or Coinbase response shapes.
- Exchange code must not own trading decisions.
- Telemetry must write facts, not derived business logic.

## Modes

- `paper`: public Coinbase market data plus internal fill simulator
- `live`: reserved for a later gated implementation

## Near-Term Build Order

1. Keep paper mode stable.
2. Add Coinbase private auth and response normalization.
3. Add live order preview plus market IOC placement.
4. Add reconciliation from Coinbase portfolio and position endpoints.
