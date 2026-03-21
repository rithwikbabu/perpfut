# perpfut

`perpfut` is a lean, AI-first repository for building a Coinbase perpetual futures
execution engine.

The current scaffold is intentionally narrow:

- one product at a time
- one polling loop
- paper trading first
- REST-only Coinbase integration
- append-only run artifacts for debugging and agent context

## Current Status

This repository is scaffolded for fast iteration. The paper path is runnable,
while live Coinbase execution is still a gated next step.

## Repo Layout

```text
.
├── AGENTS.md
├── README.md
├── pyproject.toml
├── docs/
├── runs/
├── skills/
├── src/perpfut/
└── tests/
```

## Quick Start

```bash
python3 -m pip install -e '.[dev]'
python3 -m pytest
python3 -m perpfut products --limit 5
python3 -m perpfut paper --iterations 1
```

## Design Principles

- Keep pure trading logic separate from exchange adapters.
- Keep runtime artifacts append-only and easy to inspect.
- Prefer typed boundaries and small modules over flexible abstractions.
- Optimize for AI agent readability before extensibility.

## Next Steps

1. Flesh out Coinbase private auth and live execution behind the existing gate.
2. Save real Coinbase payloads into `tests/fixtures/coinbase/`.
3. Add parser contract tests for INTX portfolio and position endpoints.
4. Add a kill switch and explicit reconciliation before each live cycle.

## Operator Docs

- Runbook: `docs/runbook.md`
- MVP readiness gates: `docs/mvp-readiness.md`
