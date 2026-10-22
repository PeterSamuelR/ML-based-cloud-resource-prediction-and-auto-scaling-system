from datetime import datetime, timedelta, timezone

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


class PredictionStateRepository(DocumentsRepository):
    class Collection:
        def __init__(self, items): self.items = items
        def find_one(self, query=None, sort=None):
            matches = self.items
            if query and "status" in query:
                matches = [item for item in matches if item.get("status") == query["status"]]
            return sorted(matches, key=lambda item: item.get("timestamp", item.get("created_at")), reverse=True)[0] if matches else None

    def __init__(self, items):
        super().__init__(items)
        self.collection = self.Collection(items)


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


def test_current_prediction_reports_freshness_and_never_calls_old_rows_live(monkeypatch):
    import src.main
    now = datetime.now(timezone.utc)
    training_end = now - timedelta(minutes=11)
    prediction = {
        "timestamp": now, "target_timestamp": now, "predicted_aggregate_cpu_percent": 33.0,
        "model_version": "rf-current", "actual_aggregate_cpu_percent": None,
    }
    model = {
        "version": "rf-current", "status": "active", "created_at": training_end,
        "metadata": {"training_window": {"end_timestamp": training_end}},
    }
    repositories = {
        "predictions": PredictionStateRepository([prediction]),
        "model_versions": PredictionStateRepository([model]),
        "scaling_events": DocumentsRepository([]),
        "experiments": DocumentsRepository([]),
    }
    monkeypatch.setattr(src.main, "document_repositories", repositories)
    with TestClient(app) as client:
        live = client.get("/api/predictions/current").json()
        assert live["status"] == "live"
        assert live["prediction"]["model_version"] == "rf-current"
        assert live["age_seconds"] < 2
        assert live["prediction_age_seconds"] < 2
        assert live["active_model_version"] == "rf-current"
        assert live["model_training_timestamp"] is not None
        assert live["model_age_seconds"] >= 660

        prediction["timestamp"] = now.replace(year=now.year - 1)
        stale = client.get("/api/predictions/current").json()
        assert stale["status"] == "stale"
        assert stale["reason"] == "prediction_record_is_too_old"


def test_current_prediction_reports_unavailable_without_a_model_or_prediction(monkeypatch):
    import src.main
    now = datetime.now(timezone.utc)
    model = {"version": "rf-current", "status": "active", "created_at": now, "metadata": {}}
    repositories = {
        "predictions": PredictionStateRepository([]),
        "model_versions": PredictionStateRepository([]),
        "scaling_events": DocumentsRepository([]),
        "experiments": DocumentsRepository([]),
    }
    monkeypatch.setattr(src.main, "document_repositories", repositories)
    with TestClient(app) as client:
        response = client.get("/api/predictions/current").json()
        assert response["status"] == "unavailable"
        assert response["reason"] == "no_active_model"

        repositories["model_versions"] = PredictionStateRepository([model])
        response = client.get("/api/predictions/current").json()
        assert response["status"] == "unavailable"
        assert response["reason"] == "no_prediction_record"
