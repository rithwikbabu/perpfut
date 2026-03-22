# AGENTS.md

Start here before editing code.

## Mission

Build a lean, AI-friendly execution engine for Coinbase perpetual futures.
The current scope is intentionally narrow:

- Single process
- Single product
- Paper mode first
- REST only
- Market-order execution only when live mode is added

Do not turn the repo into a generic trading framework unless the user asks for it.

## Safe Defaults

- Default mode is `paper`.
- Treat live trading as disabled unless `MODE=live` and `PERPFUT_ENABLE_LIVE=1`.
- Keep Coinbase-specific logic in `src/perpfut/exchange_coinbase.py`.
- Keep pure trading logic in `src/perpfut/signal_momentum.py`, `src/perpfut/risk.py`, and `src/perpfut/sim.py`.
- Keep orchestration in `src/perpfut/engine.py`.
- Keep artifacts append-only under `runs/`.

## Commands

- Install: `python3 -m pip install -e '.[dev]'`
- Tests: `python3 -m pytest`
- Lint: `python3 -m ruff check .`
- Run operator API: `python3 -m perpfut api`
- Frontend install: `cd apps/web && npm ci`
- Frontend lint: `cd apps/web && npm run lint`
- Frontend build: `cd apps/web && npm run build`
- Paper smoke test: `python3 -m perpfut paper --iterations 1`
- Discover Coinbase perps: `python3 -m perpfut products --limit 10`

## Repo Map

- `README.md`: human-facing overview and quick start.
- `docs/architecture.md`: runtime design and boundaries.
- `docs/coinbase.md`: exchange assumptions, endpoints, and auth notes.
- `docs/trading-contract.md`: strategy, risk, and execution invariants.
- `docs/event-schema.md`: artifact contract.
- `docs/operator-api.md`: local operator API routes and frontend contract.
- `skills/`: repo-local playbooks for repeatable agent tasks.
- `tests/fixtures/coinbase/`: saved Coinbase payloads for parser tests.

## Editing Rules

- Preserve the single-product assumption unless explicitly asked to widen scope.
- Update docs when you change contracts, artifact fields, or live-trading behavior.
- Add or update tests whenever you change signal, sizing, risk, parsing, or state transitions.
- Prefer adding fixtures over mocking opaque Coinbase payloads inline.
- Do not add WebSocket code to v1 unless the user asks for it.

## Live Mode Gate

Before implementing or enabling live trading, require all of the following:

- JWT auth provider with short-lived request-scoped tokens
- Order preview path
- Position reconciliation from Coinbase state
- Kill switch path
- Tests for response normalization and order intent generation
