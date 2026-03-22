from fastapi.testclient import TestClient

from perpfut.api import create_app
from perpfut.api.schemas import PaperRunStatusResponse


class StubManager:
    def __init__(self):
        self.started = None
        self.stopped = False

    def status(self) -> PaperRunStatusResponse:
        return PaperRunStatusResponse(active=False)

    def start(self, request):
        self.started = request
        return PaperRunStatusResponse(
            active=True,
            pid=4321,
            started_at="2026-03-22T00:00:00+00:00",
            run_id=None,
            product_id=request.product_id,
            iterations=request.iterations,
            interval_seconds=request.interval_seconds,
            starting_collateral_usdc=request.starting_collateral_usdc,
            log_path="runs/control/paper.log",
        )

    def stop(self) -> PaperRunStatusResponse:
        self.stopped = True
        return PaperRunStatusResponse(active=False)


def test_start_and_stop_paper_routes(monkeypatch) -> None:
    manager = StubManager()
    monkeypatch.setattr("perpfut.api.routers.paper_runs.get_paper_process_manager", lambda: manager)
    client = TestClient(create_app())

    start_response = client.post(
        "/api/paper-runs",
        json={
            "productId": "BTC-PERP-INTX",
            "iterations": 12,
            "intervalSeconds": 60,
            "startingCollateralUsdc": 15000,
        },
    )
    stop_response = client.post("/api/paper-runs/stop")

    assert start_response.status_code == 201
    assert start_response.json()["active"] is True
    assert start_response.json()["product_id"] == "BTC-PERP-INTX"
    assert manager.started is not None

    assert stop_response.status_code == 200
    assert stop_response.json()["active"] is False
    assert manager.stopped is True
