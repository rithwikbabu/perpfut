from fastapi.testclient import TestClient

from perpfut.api import create_app
from perpfut.api.process_manager import PaperRunConflictError, PaperRunStartError, PaperRunStateError
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


def test_active_paper_route_returns_status(monkeypatch) -> None:
    class ActiveManager(StubManager):
        def status(self) -> PaperRunStatusResponse:
            return PaperRunStatusResponse(
                active=True,
                pid=9876,
                started_at="2026-03-22T00:00:00+00:00",
                run_id="paper-123",
                product_id="BTC-PERP-INTX",
                iterations=12,
                interval_seconds=60,
                starting_collateral_usdc=15000,
                log_path="runs/control/paper.log",
            )

    monkeypatch.setattr("perpfut.api.routers.paper_runs.get_paper_process_manager", lambda: ActiveManager())
    client = TestClient(create_app())

    response = client.get("/api/paper-runs/active")

    assert response.status_code == 200
    assert response.json()["active"] is True
    assert response.json()["run_id"] == "paper-123"


def test_start_paper_route_maps_conflict_to_409(monkeypatch) -> None:
    class ConflictManager(StubManager):
        def start(self, request):
            raise PaperRunConflictError("a paper run is already active")

    monkeypatch.setattr("perpfut.api.routers.paper_runs.get_paper_process_manager", lambda: ConflictManager())
    client = TestClient(create_app())

    response = client.post(
        "/api/paper-runs",
        json={
            "productId": "BTC-PERP-INTX",
            "iterations": 12,
            "intervalSeconds": 60,
            "startingCollateralUsdc": 15000,
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "a paper run is already active"


def test_start_paper_route_maps_failures_to_500(monkeypatch) -> None:
    class FailedStartManager(StubManager):
        def start(self, request):
            raise PaperRunStartError("paper process exited immediately")

    monkeypatch.setattr("perpfut.api.routers.paper_runs.get_paper_process_manager", lambda: FailedStartManager())
    client = TestClient(create_app())

    response = client.post(
        "/api/paper-runs",
        json={
            "productId": "BTC-PERP-INTX",
            "iterations": 12,
            "intervalSeconds": 60,
            "startingCollateralUsdc": 15000,
        },
    )

    assert response.status_code == 500
    assert response.json()["detail"] == "paper process exited immediately"


def test_active_paper_route_maps_state_errors_to_500(monkeypatch) -> None:
    class BrokenStateManager(StubManager):
        def status(self) -> PaperRunStatusResponse:
            raise PaperRunStateError("paper run metadata is corrupted")

    monkeypatch.setattr("perpfut.api.routers.paper_runs.get_paper_process_manager", lambda: BrokenStateManager())
    client = TestClient(create_app())

    response = client.get("/api/paper-runs/active")

    assert response.status_code == 500
    assert response.json()["detail"] == "paper run metadata is corrupted"


def test_start_paper_route_validates_payload(monkeypatch) -> None:
    monkeypatch.setattr("perpfut.api.routers.paper_runs.get_paper_process_manager", lambda: StubManager())
    client = TestClient(create_app())

    response = client.post(
        "/api/paper-runs",
        json={
            "productId": "BTC-PERP-INTX",
            "iterations": 0,
            "intervalSeconds": 60,
            "startingCollateralUsdc": -1,
        },
    )

    assert response.status_code == 422
