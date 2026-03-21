# Run Paper

Use this playbook when validating the repo without touching live trading.

## Steps

1. Install the package in editable mode: `python3 -m pip install -e '.[dev]'`
2. Run tests: `python3 -m pytest`
3. Run a short paper loop: `python3 -m perpfut paper --iterations 1`
4. Inspect the newest directory under `runs/`

## Expected Output

- a completed test run
- a new run directory with manifest, config, events, fills, positions, and state
