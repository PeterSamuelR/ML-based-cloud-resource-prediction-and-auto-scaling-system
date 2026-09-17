from datetime import datetime, timezone

from fastapi.testclient import TestClient

from src.main import app


class Repository:
    def __init__(self): self.metric = {"timestamp": datetime.now(timezone.utc), "per_container": [{"container_name": "app-1"}], "aggregate_cpu_percent": 20, "aggregate_memory_percent": 30, "request_rate_per_second": 1, "response_time_ms": 10, "active_healthy_replica_count": 1, "collection_error": None}
    def latest(self): return self.metric.copy()
    def history(self, _): return [self.metric.copy()]


class DocumentsRepository:
    def __init__(self, items):
        self.items = items
        self.collection = type("Collection", (), {"find_one": lambda _self, query: next((item.copy() for item in items if item["experiment_id"] == query["experiment_id"]), None)})()

    def history(self, _): return [item.copy() for item in self.items]


def test_read_only_metric_endpoints(monkeypatch):
    import src.main
    monkeypatch.setattr(src.main, "metrics_repository", Repository())
    with TestClient(app) as client:
        assert client.get("/api/metrics/current").status_code == 200
        assert client.get("/api/metrics/history").json()["items"]
        assert client.get("/api/status").json()["monitoring"] == "healthy"
        assert client.get("/api/containers").json()["items"][0]["container_name"] == "app-1"


def test_experiment_list_and_csv_export_are_read_only(monkeypatch):
    import src.main
    experiment = {
        "experiment_id": "trial-1", "started_at": datetime.now(timezone.utc), "status": "completed",
        "configuration": {"policy": "predictive"},
        "results": {"metrics": [{"timestamp": datetime.now(timezone.utc), "aggregate_cpu_percent": 20}], "predictions": [], "scaling_events": [], "model_versions": []},
    }
    repositories = {name: DocumentsRepository([]) for name in ("predictions", "scaling_events", "model_versions")}
    repositories["experiments"] = DocumentsRepository([experiment])
    monkeypatch.setattr(src.main, "document_repositories", repositories)
    with TestClient(app) as client:
        assert client.get("/api/experiments").json()["items"][0]["experiment_id"] == "trial-1"
        exported = client.get("/api/experiments/trial-1/export?format=csv")
        assert exported.status_code == 200
        assert "record_type,experiment_id" in exported.text
