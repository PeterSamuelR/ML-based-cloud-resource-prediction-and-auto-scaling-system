from datetime import datetime, timedelta, timezone

from src.services.prediction.feedback import evaluate_due_predictions
from src.services.prediction.trainer import RandomForestPredictionService


def metric(timestamp, cpu):
    return {"timestamp": timestamp, "aggregate_cpu_percent": cpu, "aggregate_memory_percent": 30, "request_rate_per_second": 2, "response_time_ms": 10, "active_healthy_replica_count": 1}


class Metrics:
    def __init__(self, values): self.values = values
    def history(self, _): return list(reversed(self.values))


class Versions:
    def __init__(self):
        self.records = []
        self.collection = type("Collection", (), {"find_one": lambda *_args, **_kwargs: None})()
    def insert(self, record): self.records.append(record)


def test_random_forest_trains_chronologically_and_persists_measured_metrics(tmp_path):
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    values = [metric(start + timedelta(seconds=5 * index), float(index * 2)) for index in range(20)]
    config = {"monitoring": {"interval_seconds": 5}, "prediction": {"horizon_seconds": 30, "minimum_training_samples": 8, "training_fraction": 0.8, "random_forest_estimators": 10, "random_seed": 42}}
    versions = Versions()
    service = RandomForestPredictionService(Metrics(values), versions, config, str(tmp_path))

    record = service.train_if_needed()

    assert record is not None
    assert record["metadata"]["mae"] >= 0
    assert record["metadata"]["rmse"] >= 0
    assert versions.records[0].status == "active"
    prediction = service.predict(values[-1])
    assert prediction is not None
    assert prediction.target_timestamp - prediction.timestamp == timedelta(seconds=30)


class Collection:
    def __init__(self, item): self.item, self.updated = item, None
    def find(self, _): return [self.item]
    def update_one(self, _, update): self.updated = update["$set"]


def test_feedback_attaches_actual_cpu_only_at_the_prediction_target_time():
    target = datetime.now(timezone.utc)
    collection = Collection({"_id": "prediction", "target_timestamp": target, "predicted_aggregate_cpu_percent": 40, "actual_aggregate_cpu_percent": None})
    updated = evaluate_due_predictions(collection, {"timestamp": target, "aggregate_cpu_percent": 55})
    assert updated == 1
    assert collection.updated["absolute_error"] == 15


def test_feedback_accepts_mongodb_naive_timestamp_values():
    target = datetime.now(timezone.utc).replace(tzinfo=None)
    collection = Collection({"_id": "prediction", "target_timestamp": target, "predicted_aggregate_cpu_percent": 20, "actual_aggregate_cpu_percent": None})
    assert evaluate_due_predictions(collection, {"timestamp": target.replace(tzinfo=timezone.utc), "aggregate_cpu_percent": 25}) == 1


def test_feedback_accepts_the_first_observation_within_a_monitoring_interval_after_target():
    target = datetime.now(timezone.utc)
    collection = Collection({"_id": "prediction", "target_timestamp": target, "predicted_aggregate_cpu_percent": 20, "actual_aggregate_cpu_percent": None})

    updated = evaluate_due_predictions(
        collection,
        {"timestamp": target + timedelta(seconds=4), "aggregate_cpu_percent": 25},
        tolerance_seconds=5,
    )

    assert updated == 1
    assert collection.updated["absolute_error"] == 5
