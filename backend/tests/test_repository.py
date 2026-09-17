from datetime import datetime, timezone

from src.models.documents import MetricDocument
from src.repositories.metrics import MetricsRepository


class Cursor(list):
    def sort(self, *_): return self
    def limit(self, count): return Cursor(self[:count])


class Collection:
    def __init__(self): self.items = []
    def create_index(self, *_): pass
    def insert_one(self, value): self.items.append(value)
    def find_one(self, **_): return self.items[-1] if self.items else None
    def find(self, _): return Cursor(reversed(self.items))


def test_metrics_repository_persists_and_reads_metric_documents():
    repository = MetricsRepository(Collection())
    metric = MetricDocument(timestamp=datetime.now(timezone.utc), aggregate_cpu_percent=25, aggregate_memory_percent=30, request_rate_per_second=1, response_time_ms=10, active_healthy_replica_count=1)
    repository.insert(metric)
    assert repository.latest()["aggregate_cpu_percent"] == 25
    assert len(repository.history(10)) == 1
