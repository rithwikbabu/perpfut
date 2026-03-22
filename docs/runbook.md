# Runbook

## Paper Mode

1. Install the repo: `python3 -m pip install -e '.[dev]'`
2. Run checks: `python3 -m pytest` and `python3 -m ruff check .`
3. Run paper preflight: `python3 -m perpfut preflight --mode paper`
4. Run a short paper smoke test: `python3 -m perpfut paper --iterations 1 --interval-seconds 0`
5. Inspect artifacts:
   - `python3 -m perpfut runs --limit 5`
   - `python3 -m perpfut state --mode paper`
6. Inspect canonical performance:
   - `python3 -m perpfut analyze --mode paper`
   - `curl -s http://127.0.0.1:8000/api/dashboard/overview?mode=paper | jq '.latest_analysis'`
   - open `http://127.0.0.1:3000` for the overview and `/runs/<run_id>` for drill-down

## Live Mode

Required environment:

- `PERPFUT_ENABLE_LIVE=1`
- `COINBASE_API_KEY_ID`
- `COINBASE_API_KEY_SECRET`
- `COINBASE_INTX_PORTFOLIO_UUID`

Live sequence:

1. Confirm issue/PR sequence is fully merged through Step 6.
2. Run read-only reconcile: `python3 -m perpfut reconcile --portfolio-uuid "$COINBASE_INTX_PORTFOLIO_UUID"`
3. Run live preflight with preview only:
   `python3 -m perpfut preflight --mode live --portfolio-uuid "$COINBASE_INTX_PORTFOLIO_UUID" --preview-quantity 0.001`
   Live preflight intentionally exits non-zero if `--preview-quantity` is omitted.
4. Inspect latest live checkpoint if resuming:
   `python3 -m perpfut state --mode live`
5. Run one live cycle first:
   `python3 -m perpfut live --portfolio-uuid "$COINBASE_INTX_PORTFOLIO_UUID" --iterations 1`

## Halt / Recovery

- If live preflight fails, do not start `perpfut live`.
- On restart, the engine loads the latest matching live checkpoint, reconciles against Coinbase before trading, and logs `resume_mismatch` if local checkpoint notional differs from exchange truth.
- Review `events.ndjson` for `halt`, `resume_loaded`, `resume_mismatch`, `order_preview`, `order_submit`, and `order_fill` before continuing.

## Reporting Notes

- CLI, API, and UI now share the same canonical run analysis payload.
- If a run is older or incomplete and cannot be analyzed, the dashboard still keeps artifact views readable and shows a reporting fallback instead of crashing.
- See `docs/performance-reporting.md` for the full reporting contract and operator workflow.
