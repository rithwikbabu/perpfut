# MVP Readiness

## Definition of Done

The MVP is ready for its first narrowly supervised live deployment when all of the
following are true:

- Step 1 through Step 6 are merged on `main`
- `tests` GitHub Action is required on PRs and passing
- `python3 -m pytest` passes locally
- `python3 -m ruff check .` passes locally
- `python3 -m perpfut preflight --mode paper` succeeds
- `python3 -m perpfut preflight --mode live --preview-quantity 0.001` succeeds with real credentials
- `python3 -m perpfut live --iterations 1` succeeds in a supervised session

## Deliberate Non-Goals

- No WebSocket ingestion
- No multi-asset portfolio support
- No advanced order types beyond market IOC
- No limit-order routing or smart execution
- No distributed services

## Open Risks

- Coinbase private fixtures are still doc-shaped, not captured from a real credentialed account
- Preflight cannot validate onboarding or account permissions beyond API behavior
- Paper fill quality is simpler than real exchange microstructure
- Funding and margin edge cases still depend on exchange-reported truth
