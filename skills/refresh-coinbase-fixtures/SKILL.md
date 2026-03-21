# Refresh Coinbase Fixtures

Use this playbook when parser or adapter changes require new Coinbase payloads.

## Rules

- Save raw payloads under `tests/fixtures/coinbase/`
- Prefer real exchange payloads over hand-written mocks
- Record the endpoint and capture date in a nearby README or test docstring

## Follow-Up

- Add contract tests that parse the saved payloads
- Update `docs/coinbase.md` if assumptions changed
