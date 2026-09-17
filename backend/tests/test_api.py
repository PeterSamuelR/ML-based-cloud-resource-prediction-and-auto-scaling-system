from datetime import datetime, timezone

from fastapi.testclient import TestClient

from src.main import app


class Repository:
    def __init__(self): self.metric = {"timestamp": datetime.now(timezone.utc), "per_container": [{"container_name": "app-1"}], "aggregate_cpu_percent": 20, "aggregate_memory_percent": 30, "request_rate_per_second": 1, "response_time_ms": 10, "active_healthy_replica_count": 1, "collection_error": None}
    def latest(self): return self.metric.copy()
    def history(self, _): return [self.metric.copy()]


def test_read_only_metric_endpoints(monkeypatch):
    import src.main
    monkeypatch.setattr(src.main, "metrics_repository", Repository())
    with TestClient(app) as client:
        assert client.get("/api/metrics/current").status_code == 200
        assert client.get("/api/metrics/history").json()["items"]
        assert client.get("/api/status").json()["monitoring"] == "healthy"
        assert client.get("/api/containers").json()["items"][0]["container_name"] == "app-1"
