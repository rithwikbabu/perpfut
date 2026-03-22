from fastapi.testclient import TestClient

from perpfut.api import create_app


def test_health_endpoint_reports_service_metadata() -> None:
    client = TestClient(create_app())

    response = client.get("/api/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["service"] == "perpfut-api"
    assert payload["version"] == "0.1.0"
    assert payload["time_utc"]


def test_openapi_describes_health_route() -> None:
    client = TestClient(create_app())

    response = client.get("/api/openapi.json")

    assert response.status_code == 200
    payload = response.json()
    assert "/api/health" in payload["paths"]
