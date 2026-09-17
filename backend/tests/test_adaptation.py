from datetime import datetime, timedelta, timezone

from src.services.adaptation.service import AdaptiveRetrainingService
from src.core.config import load_config
from src.services.prediction.trainer import RandomForestPredictionService


class Cursor(list):
    def sort(self, field, direction):
        def value(item):
            current = item
            for part in field.split("."):
                current = current.get(part, {}) if isinstance(current, dict) else {}
            return current
        return Cursor(sorted(self, key=value, reverse=direction < 0))

    def limit(self, count):
        return Cursor(self[:count])


class Collection:
    def __init__(self, items=None):
        self.items = items or []

    def find(self, _query=None, _projection=None):
        return Cursor(self.items)

    def find_one(self, query=None, sort=None):
        values = self.items
        if query and "status" in query:
            values = [item for item in values if item.get("status") == query["status"]]
        if query and "metadata.retraining_attempted_at" in query:
            values = [item for item in values if item.get("metadata", {}).get("retraining_attempted_at")]
        if not values:
            return None
        if sort:
            return Cursor(values).sort(sort[0][0], sort[0][1])[0]
        return values[0]

    def update_one(self, query, update):
        for item in self.items:
            if item.get("version") != query.get("version"):
                continue
            if "status" in query and item.get("status") != query["status"]:
                continue
            for path, value in update["$set"].items():
                target = item
                parts = path.split(".")
                for part in parts[:-1]:
                    target = target.setdefault(part, {})
                target[parts[-1]] = value
            return


class Versions:
    def __init__(self):
        self.collection = Collection([])

    def insert(self, record):
        self.collection.items.append(record.model_dump() if hasattr(record, "model_dump") else record)


class Metrics:
    def __init__(self, values):
        self.values = values

    def history(self, _limit):
        return list(reversed(self.values))


class ConstantModel:
    def __init__(self, offset=0):
        self.offset = offset

    def predict(self, values):
        return [float(value) + self.offset for value in values["aggregate_cpu_percent"]]


class RetrainingStub:
    def __init__(self, versions):
        self.model_repository = versions
        self.calls = []

    def retrain_recent(self, trigger):
        self.calls.append(trigger)
        return {"outcome": "activated", "version": "candidate-v2"}


def config(minimum=20):
    return {
        "monitoring": {"interval_seconds": 5},
        "prediction": {"horizon_seconds": 30, "minimum_training_samples": 8, "training_fraction": 0.8, "random_forest_estimators": 10, "random_seed": 42},
        "adaptive": {"absolute_error_threshold": 15.0, "consecutive_error_requirement": 3, "minimum_recent_training_samples": minimum, "retraining_cooldown_seconds": 1800, "candidate_validation_required": True},
    }


def error(timestamp, value=20):
    return {"timestamp": timestamp, "evaluated_at": timestamp, "absolute_error": value}


def metrics(count=80):
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return [
        {"timestamp": start + timedelta(seconds=5 * index), "aggregate_cpu_percent": float(index), "aggregate_memory_percent": 30, "request_rate_per_second": 2, "response_time_ms": 10, "active_healthy_replica_count": 1}
        for index in range(count)
    ]


def test_persistent_error_detection_triggers_only_after_required_consecutive_breaches():
    now = datetime(2026, 1, 2, tzinfo=timezone.utc)
    versions = Versions()
    stub = RetrainingStub(versions)
    service = AdaptiveRetrainingService(Collection([error(now - timedelta(seconds=index)) for index in range(3)]), stub, config())

    result = service.evaluate(now)

    assert result["outcome"] == "activated"
    assert len(stub.calls) == 1
    assert len(stub.calls[0]["breaches"]) == 3


def test_no_trigger_for_insufficient_or_nonpersistent_errors():
    now = datetime(2026, 1, 2, tzinfo=timezone.utc)
    stub = RetrainingStub(Versions())
    insufficient = AdaptiveRetrainingService(Collection([error(now)]), stub, config()).evaluate(now)
    nonpersistent = AdaptiveRetrainingService(Collection([error(now), error(now - timedelta(seconds=1)), error(now - timedelta(seconds=2), 10)]), stub, config()).evaluate(now)

    assert insufficient["reason"] == "insufficient_evaluated_predictions"
    assert nonpersistent["reason"] == "error_threshold_not_persistent"
    assert not stub.calls


def test_retraining_cooldown_and_new_error_requirement_prevent_repeat_loops():
    now = datetime(2026, 1, 2, tzinfo=timezone.utc)
    versions = Versions()
    versions.collection.items.append({"version": "old-candidate", "metadata": {"retraining_attempted_at": now - timedelta(seconds=30)}})
    stub = RetrainingStub(versions)
    errors = [error(now - timedelta(seconds=index)) for index in range(3)]
    result = AdaptiveRetrainingService(Collection(errors), stub, config()).evaluate(now)

    assert result["reason"] == "retraining_cooldown"
    assert not stub.calls

    versions.collection.items[0]["metadata"]["retraining_attempted_at"] = now
    repeated = AdaptiveRetrainingService(Collection(errors), stub, config()).evaluate(now + timedelta(seconds=1900))
    assert repeated["reason"] == "no_new_errors_since_last_attempt"


def test_recent_sample_requirement_blocks_candidate_training(tmp_path):
    service = RandomForestPredictionService(Metrics(metrics(20)), Versions(), config(minimum=20), str(tmp_path))
    service.model, service.version = ConstantModel(), "active-v1"

    result = service.retrain_recent({"breaches": []})

    assert result["outcome"] == "insufficient_samples"


def test_candidate_rejection_preserves_active_version(tmp_path):
    versions = Versions()
    versions.collection.items.append({"version": "active-v1", "status": "active", "metadata": {}})
    service = RandomForestPredictionService(Metrics(metrics()), versions, config(), str(tmp_path))
    service.model, service.version = ConstantModel(offset=6), "active-v1"

    result = service.retrain_recent({"breaches": []})

    assert result["outcome"] == "rejected"
    assert versions.collection.find_one({"status": "active"})["version"] == "active-v1"
    assert versions.collection.items[-1]["status"] == "rejected"
    assert versions.collection.items[-1]["metadata"]["validation"]["passed"] is False


def test_successful_candidate_validation_activates_and_tracks_versions(tmp_path):
    versions = Versions()
    versions.collection.items.append({"version": "active-v1", "status": "active", "metadata": {}})
    service = RandomForestPredictionService(Metrics(metrics()), versions, config(), str(tmp_path))
    service.model, service.version = ConstantModel(offset=-100), "active-v1"

    result = service.retrain_recent({"breaches": [{"absolute_error": 20}]})

    assert result["outcome"] == "activated"
    assert result["previous_version"] == "active-v1"
    assert service.version == result["version"]
    assert versions.collection.find_one({"status": "active"})["version"] == result["version"]
    assert any(record["status"] == "superseded" for record in versions.collection.items)
    active = versions.collection.find_one({"status": "active"})
    assert active["metadata"]["training_window"]["valid_samples"] == 20
    assert active["metadata"]["feature_definition_version"] == "aggregate_cpu_features_v1"


def test_adaptive_policy_configuration_is_loaded(monkeypatch, tmp_path):
    config_directory = tmp_path / "config"
    config_directory.mkdir()
    source = __import__("pathlib").Path(__file__).parents[2] / "config"
    for name in ("default.yaml", "reactive.yaml", "predictive.yaml", "adaptive.yaml"):
        (config_directory / name).write_text((source / name).read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setenv("CONFIG_DIRECTORY", str(config_directory))
    monkeypatch.setenv("AUTOSCALING_POLICY", "adaptive_predictive")

    loaded = load_config()

    assert loaded["selected_policy"] == "adaptive_predictive"
    assert loaded["policy"] == "adaptive_predictive"
