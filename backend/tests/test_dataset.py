from datetime import datetime, timedelta, timezone

from src.services.prediction.dataset import build_future_cpu_dataset


def metric(timestamp, cpu):
    return {"timestamp": timestamp, "aggregate_cpu_percent": cpu, "aggregate_memory_percent": 20, "request_rate_per_second": 2, "response_time_ms": 10, "active_healthy_replica_count": 1}


def test_dataset_uses_only_current_features_and_actual_future_cpu_target():
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    metrics = [metric(start + timedelta(seconds=5 * index), float(index)) for index in range(8)]
    dataset = build_future_cpu_dataset(metrics, interval_seconds=5, horizon_seconds=30)
    assert len(dataset.features) == 2
    assert dataset.features.iloc[0]["aggregate_cpu_percent"] == 0
    assert dataset.targets.iloc[0] == 6


def test_dataset_rejects_missing_future_observation_at_expected_horizon():
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    metrics = [metric(start + timedelta(seconds=5 * index), float(index)) for index in range(6)]
    metrics.append(metric(start + timedelta(seconds=65), 99))
    assert build_future_cpu_dataset(metrics).features.empty


def test_dataset_accepts_an_actual_target_sample_with_one_interval_of_collection_jitter():
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    metrics = [metric(start, 1), metric(start + timedelta(seconds=35), 9)]
    dataset = build_future_cpu_dataset(metrics)
    assert len(dataset.features) == 1
    assert dataset.targets.iloc[0] == 9
