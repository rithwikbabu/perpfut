# Operator API

`perpfut` exposes a local-only operator API for the Next.js dashboard.

The current dashboard is monitor-first. Read routes are already consumed by the
UI, while the paper-run control routes are available for the next frontend step.

## Runtime

- API host: `127.0.0.1:8000`
- Frontend host: `127.0.0.1:3000`
- Source of truth: run artifacts under `runs/`
- Active paper control state: `runs/control/active_paper.json`
- Paper control log: `runs/control/paper.log`

Start the API with:

```bash
python3 -m perpfut api
```

## Contract

All routes are rooted at `/api`.

### Read routes

- `GET /api/health`
- `GET /api/dashboard/overview?mode=paper|live&limit=`
- `GET /api/runs?mode=&limit=`
- `GET /api/runs/{runId}/manifest`
- `GET /api/runs/{runId}/state`
- `GET /api/runs/{runId}/events?limit=`
- `GET /api/runs/{runId}/fills?limit=`
- `GET /api/runs/{runId}/positions?limit=`
- `GET /api/paper-runs/active`

### Control routes

- `POST /api/paper-runs`
- `POST /api/paper-runs/stop`

Start requests accept:

```json
{
  "productId": "BTC-PERP-INTX",
  "iterations": 1440,
  "intervalSeconds": 60,
  "startingCollateralUsdc": 10000
}
```

The service allows only one active paper run at a time.

## Design Notes

- The API does not maintain in-memory trading state for the UI.
- Dashboard responses are derived from the newest readable artifact files.
- Paper runs are launched by spawning `python3 -m perpfut paper ...`.
- Stop requests send `SIGTERM`, then escalate to `SIGKILL` after 5 seconds.
- Process metadata writes are atomic and protected by a local control lock.
- Live mode remains read-only in the UI. There are no live-trading control routes.

## Frontend Expectations

- Poll every 2 seconds.
- Treat missing latest runs as an empty state, not an error.
- Treat `409` on `POST /api/paper-runs` as "paper run already active".
- Treat `500` on control routes as operator-visible failures that should not be retried blindly.
- Use `/api/dashboard/overview` for the landing page and `/api/runs/{runId}/...` for drill-down views.
