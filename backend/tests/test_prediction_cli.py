from datetime import datetime, timedelta, timezone

from src.services.prediction.cli import materialize


def test_materialize_persists_real_horizon_labeled_samples_idempotently():
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    metrics = [
        {
            "timestamp": start + timedelta(seconds=index * 5),
            "aggregate_cpu_percent": float(index),
            "aggregate_memory_percent": 20.0,
            "request_rate_per_second": 3.0,
            "response_time_ms": 10.0,
            "active_healthy_replica_count": 1,
        }
        for index in range(14)
    ]

    class MetricsRepository:
        def history(self, limit):
            assert limit == 100
            return list(reversed(metrics))

    class SampleRepository:
        def upsert_many(self, rows):
            self.rows = rows
            return len(rows)

    config = {
        "monitoring": {"interval_seconds": 5},
        "prediction": {"horizon_seconds": 30, "training_history_limit": 100},
    }
    samples = SampleRepository()

    result = materialize(config, MetricsRepository(), samples)

    assert result["raw_metrics_read"] == 14
    assert result["valid_labeled_samples"] == 2
    assert result["upserts"] == 2
    assert samples.rows[0]["timestamp"] == start + timedelta(seconds=30)
    assert samples.rows[0]["target_timestamp"] == start + timedelta(seconds=60)
    assert samples.rows[0]["target_cpu_30s"] == 12.0
