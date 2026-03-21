# Trading Contract

## Scope

The repo currently assumes a single perpetual futures instrument, such as
`BTC-PERP-INTX`.

## Signal Contract

- Strategies output `target_position` in `[-1.0, 1.0]`.
- `-1.0` means max short, `0.0` means flat, `1.0` means max long.
- Risk controls may clip that range further.

## Position Contract

- Paper mode stores signed `quantity` in base units.
- Positive quantity is long.
- Negative quantity is short.
- Position notional is `quantity * mark_price`.

## Rebalance Contract

- The engine computes a target notional from target position and risk limits.
- The engine trades only if the delta clears both:
  - minimum notional threshold
  - rebalance threshold

## Live Contract

When live mode is implemented, every cycle must:

1. fetch exchange truth
2. compute target
3. preview order
4. place order only if risk checks pass
5. reconcile fills and positions
6. write artifacts
