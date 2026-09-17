from types import SimpleNamespace

from src.services.monitoring.collector import DockerMetricsCollector


def stats(total: int, previous: int, memory_usage: int, memory_limit: int) -> dict:
    return {"cpu_stats": {"cpu_usage": {"total_usage": total, "percpu_usage": [1]}, "system_cpu_usage": 2000, "online_cpus": 1}, "precpu_stats": {"cpu_usage": {"total_usage": previous}, "system_cpu_usage": 1900}, "memory_stats": {"usage": memory_usage, "limit": memory_limit}}


class Container:
    def __init__(self, name: str, healthy: bool, result: dict):
        self.id, self.name, self.labels, self.result = name, name, {"com.ml-autoscaler.project": "cloud-resource-autoscaling", "com.ml-autoscaler.role": "application", "com.ml-autoscaler.managed": "true"}, result
        self.attrs = {"State": {"Running": True, "Health": {"Status": "healthy" if healthy else "unhealthy"}}}
    def reload(self): pass
    def stats(self, stream: bool): return self.result


class Client:
    def __init__(self, containers): self.containers = SimpleNamespace(list=lambda filters: containers)


class Logs:
    def read_window(self): return {"request_rate_per_second": 2.0, "response_time_ms": 15.0}


def test_collector_filters_unhealthy_and_averages_only_healthy_replicas():
    first = Container("first", True, stats(120, 100, 40, 100))
    second = Container("second", True, stats(140, 100, 60, 100))
    unhealthy = Container("unhealthy", False, stats(900, 100, 99, 100))
    metric = DockerMetricsCollector(Client([first, second, unhealthy]), Logs()).collect()
    assert metric.active_healthy_replica_count == 2
    assert metric.aggregate_cpu_percent == 30.0
    assert metric.aggregate_memory_percent == 50.0
    assert [item.container_name for item in metric.per_container] == ["first", "second"]
