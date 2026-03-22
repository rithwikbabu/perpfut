import json
from pathlib import Path

from fastapi.testclient import TestClient

from perpfut.api import create_app


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_ndjson(path: Path, items: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(item) for item in items) + "\n", encoding="utf-8")


def _make_run(
    runs_dir: Path,
    run_id: str,
    *,
    mode: str,
    include_state: bool = True,
) -> None:
    run_dir = runs_dir / run_id
    run_dir.mkdir(parents=True)
    _write_json(
        run_dir / "manifest.json",
        {
            "run_id": run_id,
            "created_at": f"{run_id}-created",
            "mode": mode,
            "product_id": "BTC-PERP-INTX",
            "resumed_from_run_id": None,
        },
    )
    if include_state:
        _write_json(
            run_dir / "state.json",
            {
                "run_id": run_id,
                "cycle_id": "cycle-0002",
                "mode": mode,
                "product_id": "BTC-PERP-INTX",
                "equity_usdc": 10_100.0,
                "current_position_notional_usdc": 4_200.0,
                "signal": {
                    "strategy": "momentum",
                    "raw_value": 0.12,
                    "target_position": 0.25,
                },
                "risk_decision": {
                    "target_before_risk": 0.25,
                    "target_after_risk": 0.25,
                    "current_position": 0.1,
                    "target_notional_usdc": 5_000.0,
                    "current_notional_usdc": 2_000.0,
                    "delta_notional_usdc": 3_000.0,
                    "rebalance_threshold": 0.1,
                    "min_trade_notional_usdc": 10.0,
                    "halted": False,
                    "rebalance_eligible": True,
                },
                "execution_summary": {
                    "action": "filled",
                    "reason_code": "filled",
                    "reason_message": "Cycle placed and filled a rebalance order.",
                    "summary": "Filled a rebalance order toward the target position.",
                },
                "no_trade_reason": None,
                "order_intent": {
                    "product_id": "BTC-PERP-INTX",
                    "side": "BUY",
                },
                "fill": {
                    "product_id": "BTC-PERP-INTX",
                    "side": "BUY",
                },
            },
        )
    _write_ndjson(
        run_dir / "events.ndjson",
        [
            {"event_type": "cycle", "sequence": 1},
            {"event_type": "cycle", "sequence": 2},
        ],
    )
    _write_ndjson(
        run_dir / "fills.ndjson",
        [
            {"fill_id": "fill-1", "price": 100.0},
            {"fill_id": "fill-2", "price": 101.0},
        ],
    )
    _write_ndjson(
        run_dir / "positions.ndjson",
        [
            {"position": {"quantity": 0.1}},
            {"position": {"quantity": 0.2}},
        ],
    )


def test_runs_endpoint_filters_and_orders_latest_runs(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("RUNS_DIR", str(tmp_path))
    _make_run(tmp_path, "20260322T010000000000Z_alpha", mode="paper")
    _make_run(tmp_path, "20260322T020000000000Z_beta", mode="live")
    _make_run(tmp_path, "20260322T030000000000Z_gamma", mode="paper")
    client = TestClient(create_app())

    response = client.get("/api/runs", params={"mode": "paper", "limit": 1})

    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 1
    assert payload["items"][0]["run_id"] == "20260322T030000000000Z_gamma"


def test_dashboard_overview_uses_latest_matching_run_and_newest_first_lists(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("RUNS_DIR", str(tmp_path))
    _make_run(tmp_path, "20260322T010000000000Z_alpha", mode="live")
    _make_run(tmp_path, "20260322T020000000000Z_beta", mode="paper")
    client = TestClient(create_app())

    response = client.get("/api/dashboard/overview", params={"mode": "paper", "limit": 1})

    assert response.status_code == 200
    payload = response.json()
    assert payload["latest_run"]["run_id"] == "20260322T020000000000Z_beta"
    assert payload["latest_state"]["equity_usdc"] == 10_100.0
    assert payload["latest_decision"]["cycle_id"] == "cycle-0002"
    assert payload["latest_decision"]["execution_summary"]["reason_code"] == "filled"
    assert payload["latest_decision"]["risk_decision"]["rebalance_eligible"] is True
    assert payload["recent_events"][0]["sequence"] == 2
    assert payload["recent_fills"][0]["fill_id"] == "fill-2"
    assert payload["recent_positions"][0]["position"]["quantity"] == 0.2


def test_dashboard_overview_exposes_latest_decision_for_live_runs(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("RUNS_DIR", str(tmp_path))
    _make_run(tmp_path, "20260322T020000000000Z_beta", mode="live")
    client = TestClient(create_app())

    response = client.get("/api/dashboard/overview", params={"mode": "live", "limit": 1})

    assert response.status_code == 200
    payload = response.json()
    assert payload["latest_run"]["mode"] == "live"
    assert payload["latest_decision"]["mode"] == "live"
    assert payload["latest_decision"]["signal"]["target_position"] == 0.25


def test_run_artifact_endpoints_wrap_documents_and_lists(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("RUNS_DIR", str(tmp_path))
    run_id = "20260322T020000000000Z_beta"
    _make_run(tmp_path, run_id, mode="paper")
    client = TestClient(create_app())

    state_response = client.get(f"/api/runs/{run_id}/state")
    events_response = client.get(f"/api/runs/{run_id}/events", params={"limit": 1})

    assert state_response.status_code == 200
    assert state_response.json()["run_id"] == run_id
    assert state_response.json()["data"]["equity_usdc"] == 10_100.0

    assert events_response.status_code == 200
    assert events_response.json()["run_id"] == run_id
    assert events_response.json()["count"] == 1
    assert events_response.json()["items"][0]["sequence"] == 2


def test_missing_state_returns_not_found(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("RUNS_DIR", str(tmp_path))
    run_id = "20260322T020000000000Z_beta"
    _make_run(tmp_path, run_id, mode="paper", include_state=False)
    client = TestClient(create_app())

    response = client.get(f"/api/runs/{run_id}/state")

    assert response.status_code == 404
    assert "state.json" in response.json()["detail"]
