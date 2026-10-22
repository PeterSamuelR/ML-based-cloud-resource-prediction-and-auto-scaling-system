from datetime import datetime, timedelta, timezone

from src.services.prediction.dataset import FEATURE_COLUMNS, build_future_cpu_dataset, build_live_feature_vector


def metric(timestamp, cpu):
    return {"timestamp": timestamp, "aggregate_cpu_percent": cpu, "aggregate_memory_percent": 20, "request_rate_per_second": 2, "response_time_ms": 10, "active_healthy_replica_count": 1}


def test_dataset_uses_only_past_or_current_features_and_actual_future_cpu_target():
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    metrics = [metric(start + timedelta(seconds=5 * index), float(index)) for index in range(14)]
    dataset = build_future_cpu_dataset(metrics, interval_seconds=5, horizon_seconds=30)
    assert len(dataset.features) == 2
    assert dataset.features.iloc[0]["aggregate_cpu_percent"] == 6
    assert dataset.features.iloc[0]["cpu_previous_sample_percent"] == 5
    assert dataset.features.iloc[0]["cpu_six_samples_ago_percent"] == 0
    assert dataset.targets.iloc[0] == 12
    assert dataset.target_timestamps.iloc[0] == start + timedelta(seconds=60)
    assert "cpu_trend_per_second" in FEATURE_COLUMNS


def test_dataset_rejects_missing_future_observation_at_expected_horizon():
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    metrics = [metric(start + timedelta(seconds=5 * index), float(index)) for index in range(7)]
    metrics.append(metric(start + timedelta(seconds=66), 99))
    assert build_future_cpu_dataset(metrics).features.empty


def test_dataset_accepts_an_actual_target_sample_with_one_interval_of_collection_jitter():
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    metrics = [metric(start + timedelta(seconds=5 * index), float(index)) for index in range(7)]
    metrics.append(metric(start + timedelta(seconds=65), 9))
    dataset = build_future_cpu_dataset(metrics)
    assert len(dataset.features) == 1
    assert dataset.targets.iloc[0] == 9


def test_live_features_use_current_and_past_metrics_without_future_observations():
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    metrics = [metric(start + timedelta(seconds=5 * index), float(index)) for index in range(7)]

    vector = build_live_feature_vector(metrics)

    assert vector is not None
    assert vector.iloc[0]["aggregate_cpu_percent"] == 6
    assert vector.iloc[0]["cpu_previous_sample_percent"] == 5
    assert vector.iloc[0]["cpu_three_samples_ago_percent"] == 3
    assert vector.iloc[0]["cpu_six_samples_ago_percent"] == 0
    assert vector.iloc[0]["cpu_trend_per_second"] == 0.2
    assert vector.iloc[0]["aggregate_cpu_percent"] != 12
