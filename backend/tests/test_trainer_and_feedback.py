from datetime import datetime, timedelta, timezone

import joblib

from src.services.prediction.feedback import evaluate_due_predictions, observed_sampling_tolerance
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
    now = datetime.now(timezone.utc)
    start = now - timedelta(seconds=5 * 99)
    values = [metric(start + timedelta(seconds=5 * index), float(index * 2)) for index in range(100)]
    config = {"monitoring": {"interval_seconds": 5}, "prediction": {"horizon_seconds": 30, "minimum_training_samples": 8, "recent_training_samples": 60, "training_fraction": 0.8, "random_forest_estimators": 10, "random_seed": 42, "random_forest_tuning": {"n_estimators": [5, 10], "max_depth": [None], "min_samples_leaf": [1, 2], "cv_splits": 3}}}
    versions = Versions()
    service = RandomForestPredictionService(Metrics(values), versions, config, str(tmp_path))

    record = service.train_if_needed()

    assert record is not None
    assert record["metadata"]["mae"] >= 0
    assert record["metadata"]["rmse"] >= 0
    assert record["metadata"]["purged_training_samples"] > 0
    assert record["metadata"]["max_training_target_timestamp"] < record["metadata"]["validation_start_timestamp"]
    assert record["metadata"]["feature_definition_version"] == "aggregate_cpu_features_v2_temporal"
    assert record["metadata"]["tuning"]["method"] == "purged_expanding_window_time_series_cv_mae"
    assert (now - record["metadata"]["training_window"]["end_timestamp"]).total_seconds() < 45
    assert versions.records[0].status == "active"
    prediction = service.predict(values[-1])
    assert prediction is not None
    assert prediction.target_timestamp - prediction.timestamp == timedelta(seconds=30)
    assert prediction.predicted_aggregate_cpu_percent >= 0


def test_initial_training_does_not_learn_from_stale_monitoring_history(tmp_path):
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    values = [metric(start + timedelta(seconds=5 * index), float(index)) for index in range(200)]
    config = {"monitoring": {"interval_seconds": 5}, "prediction": {"horizon_seconds": 30, "minimum_training_samples": 8, "recent_training_samples": 60, "training_fraction": 0.8, "random_forest_estimators": 10, "random_seed": 42, "random_forest_tuning": {"n_estimators": [5], "max_depth": [None], "min_samples_leaf": [1], "cv_splits": 3}}}
    service = RandomForestPredictionService(Metrics(values), Versions(), config, str(tmp_path))

    assert service.train_if_needed() is None
    assert service.model is None


def test_valid_model_older_than_refresh_interval_keeps_generating_fresh_forecasts(tmp_path):
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    values = [metric(start + timedelta(seconds=5 * index), float(index * 2)) for index in range(100)]
    config = {"monitoring": {"interval_seconds": 5}, "prediction": {"horizon_seconds": 30, "refresh_interval_seconds": 300}}
    service = RandomForestPredictionService(Metrics(values), Versions(), config, str(tmp_path))
    class FixedModel:
        def predict(self, features):
            assert features.iloc[0]["aggregate_cpu_percent"] == 198.0
            return [82.4]

    service.model, service.version = FixedModel(), "older-valid-model"
    service.feature_columns = ["aggregate_cpu_percent"]
    service.training_window_end = datetime.now(timezone.utc) - timedelta(minutes=11)

    forecast = service.predict(values[-1])

    assert forecast is not None
    assert forecast.predicted_aggregate_cpu_percent == 82.4
    assert forecast.model_version == "older-valid-model"
    assert forecast.target_timestamp - forecast.timestamp == timedelta(seconds=30)


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


def test_feedback_tolerance_tracks_real_collection_cadence_but_is_bounded():
    previous = datetime(2026, 1, 1, tzinfo=timezone.utc)

    tolerance = observed_sampling_tolerance(
        previous, previous + timedelta(seconds=12, milliseconds=400), 5, 15
    )
    capped = observed_sampling_tolerance(
        previous, previous + timedelta(seconds=40), 5, 15
    )

    assert tolerance == 13
    assert capped == 15


def test_service_picks_up_a_model_version_activated_by_another_process(tmp_path):
    artifact = tmp_path / "rf-v2.joblib"
    joblib.dump({"model": "loaded-model", "version": "rf-v2", "feature_columns": ["aggregate_cpu_percent"]}, artifact)

    class ActiveCollection:
        def find_one(self, *_args, **_kwargs):
            return {"version": "rf-v2", "metadata": {"artifact": str(artifact), "training_window": {"end_timestamp": datetime.now(timezone.utc)}}}

    versions = type("Versions", (), {"collection": ActiveCollection()})()
    config = {"monitoring": {"interval_seconds": 5}, "prediction": {"horizon_seconds": 30}}
    service = RandomForestPredictionService(Metrics([]), versions, config, str(tmp_path))
    service.model, service.version = "old-model", "rf-v1"

    assert service.refresh_active_model_if_changed() is True
    assert service.version == "rf-v2"
    assert service.model == "loaded-model"
    assert service.refresh_active_model_if_changed() is False
