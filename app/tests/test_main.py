from fastapi.testclient import TestClient

from src.main import MAX_WORK_DURATION_MS, MAX_WORK_INTENSITY, app

client = TestClient(app)


def test_root_confirms_application_is_running() -> None:
    response = client.get("/")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "running"
    assert isinstance(payload["instance_id"], str)
    assert payload["instance_id"]
    assert "timestamp" in payload
    assert float(response.headers["X-Process-Time-Ms"]) >= 0


def test_health_is_suitable_for_health_checks() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}
    assert float(response.headers["X-Process-Time-Ms"]) >= 0


def test_work_returns_expected_response_structure() -> None:
    response = client.get("/work", params={"duration_ms": 5, "intensity": 2})

    assert response.status_code == 200
    payload = response.json()
    assert payload["instance_id"]
    assert payload["requested_workload"] == {"duration_ms": 5, "intensity": 2}
    assert "timestamp" in payload
    assert payload["actual_execution_duration_ms"] > 0
    assert float(response.headers["X-Process-Time-Ms"]) >= 0


def test_work_rejects_invalid_workload_values() -> None:
    assert client.get("/work", params={"duration_ms": 0}).status_code == 422
    assert client.get("/work", params={"intensity": 0}).status_code == 422
    assert client.get("/work", params={"duration_ms": "not-a-number"}).status_code == 422


def test_work_rejects_values_above_the_safety_bounds() -> None:
    assert client.get("/work", params={"duration_ms": MAX_WORK_DURATION_MS + 1}).status_code == 422
    assert client.get("/work", params={"intensity": MAX_WORK_INTENSITY + 1}).status_code == 422
