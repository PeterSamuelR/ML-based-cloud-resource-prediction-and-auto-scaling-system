from __future__ import annotations

from datetime import datetime, timezone
from statistics import mean

from docker.models.containers import Container

from src.models.documents import ContainerMetric, MetricDocument

PROJECT_LABELS = {
    "com.ml-autoscaler.project": "cloud-resource-autoscaling",
    "com.ml-autoscaler.role": "application",
    "com.ml-autoscaler.managed": "true",
}


def cpu_percent(stats: dict) -> float:
    current = stats["cpu_stats"]
    previous = stats["precpu_stats"]
    cpu_delta = current["cpu_usage"]["total_usage"] - previous["cpu_usage"]["total_usage"]
    system_delta = current["system_cpu_usage"] - previous["system_cpu_usage"]
    online_cpus = current.get("online_cpus") or len(current["cpu_usage"].get("percpu_usage", [])) or 1
    return round((cpu_delta / system_delta) * online_cpus * 100, 3) if system_delta > 0 and cpu_delta >= 0 else 0.0


def memory_percent(stats: dict) -> float:
    memory = stats["memory_stats"]
    limit = memory.get("limit", 0)
    return round((memory.get("usage", 0) / limit) * 100, 3) if limit else 0.0


class DockerMetricsCollector:
    def __init__(self, docker_client, log_reader):
        self.docker_client = docker_client
        self.log_reader = log_reader

    @staticmethod
    def is_healthy_application(container: Container) -> bool:
        container.reload()
        labels = container.labels or {}
        state = container.attrs.get("State", {})
        return all(labels.get(key) == value for key, value in PROJECT_LABELS.items()) and state.get("Running") and state.get("Health", {}).get("Status") == "healthy"

    def healthy_applications(self) -> list[Container]:
        filters = {"label": [f"{key}={value}" for key, value in PROJECT_LABELS.items()]}
        return [container for container in self.docker_client.containers.list(filters=filters) if self.is_healthy_application(container)]

    def collect(self) -> MetricDocument:
        timestamp = datetime.now(timezone.utc)
        per_container: list[ContainerMetric] = []
        errors: list[str] = []
        try:
            healthy = self.healthy_applications()
        except Exception as error:
            healthy = []
            errors.append(f"Docker discovery failed: {error}")

        for container in healthy:
            try:
                stats = container.stats(stream=False)
                per_container.append(ContainerMetric(
                    container_id=container.id[:12], container_name=container.name,
                    cpu_percent=cpu_percent(stats), memory_percent=memory_percent(stats),
                ))
            except Exception as error:
                errors.append(f"Stats failed for {container.name}: {error}")

        try:
            traffic = self.log_reader.read_window()
        except Exception as error:
            traffic = {"request_rate_per_second": 0.0, "response_time_ms": None}
            errors.append(f"Nginx log read failed: {error}")

        # Do not silently average a partial replica set after a Docker stats failure.
        complete = len(per_container) == len(healthy)
        return MetricDocument(
            timestamp=timestamp,
            per_container=per_container,
            aggregate_cpu_percent=round(mean(item.cpu_percent for item in per_container), 3) if per_container and complete else None,
            aggregate_memory_percent=round(mean(item.memory_percent for item in per_container), 3) if per_container and complete else None,
            request_rate_per_second=traffic["request_rate_per_second"],
            response_time_ms=traffic["response_time_ms"],
            active_healthy_replica_count=len(healthy),
            collection_error="; ".join(errors) if errors else None,
        )
