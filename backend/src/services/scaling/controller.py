from __future__ import annotations

import os
import time
import uuid
from datetime import datetime, timezone

import docker

from src.models.documents import ScalingEventDocument
from src.services.monitoring.collector import PROJECT_LABELS


class ScalingController:
    """Bounded Docker control that delegates scale-in membership order to Nginx controller."""

    def __init__(self, docker_client, events_repository, config: dict):
        self.client = docker_client
        self.events_repository = events_repository
        self.config = config
        self.last_change_at = 0.0

    def healthy_replicas(self):
        filters = {"label": [f"{key}={value}" for key, value in PROJECT_LABELS.items()]}
        replicas = []
        for container in self.client.containers.list(filters=filters):
            container.reload()
            state = container.attrs.get("State", {})
            if state.get("Running") and state.get("Health", {}).get("Status") == "healthy":
                replicas.append(container)
        return sorted(replicas, key=lambda item: item.name)

    def desired_action(self, observed_cpu: float, policy: str) -> tuple[str, str]:
        section = self.config["reactive"] if policy == "reactive" else self.config["predictive"]
        out_key = "scale_out_cpu_threshold" if policy == "reactive" else "scale_out_predicted_cpu_threshold"
        in_key = "scale_in_cpu_threshold" if policy == "reactive" else "scale_in_predicted_cpu_threshold"
        if observed_cpu >= section[out_key]:
            return "scale_out", f"{policy} CPU value {observed_cpu:.3f} meets scale-out threshold {section[out_key]:.3f}"
        if observed_cpu <= section[in_key]:
            return "scale_in", f"{policy} CPU value {observed_cpu:.3f} meets scale-in threshold {section[in_key]:.3f}"
        return "none", f"{policy} CPU value {observed_cpu:.3f} is within thresholds"

    def execute(self, observed_cpu: float | None, policy: str, model_version: str | None = None) -> ScalingEventDocument | None:
        if observed_cpu is None:
            return None
        if time.monotonic() - self.last_change_at < self.config["scaling"]["cooldown_seconds"]:
            return None
        replicas = self.healthy_replicas()
        before = len(replicas)
        action, reason = self.desired_action(observed_cpu, policy)
        minimum, maximum = self.config["scaling"]["min_replicas"], self.config["scaling"]["max_replicas"]
        if action == "scale_out" and before < maximum:
            try:
                container = self.client.containers.run(os.getenv("APPLICATION_IMAGE", "cloud-resource-autoscaling-app:phase3"), detach=True, name=f"autoscaled-app-{uuid.uuid4().hex[:8]}", labels=PROJECT_LABELS, network=os.getenv("APPLICATION_NETWORK", "cloud-resource-autoscaling-network"))
                deadline = time.monotonic() + 45
                while time.monotonic() < deadline:
                    container.reload()
                    if container.attrs.get("State", {}).get("Health", {}).get("Status") == "healthy":
                        self._sync_membership()
                        self.last_change_at = time.monotonic()
                        event = ScalingEventDocument(timestamp=datetime.now(timezone.utc), policy=policy, action=action, reason=reason, replica_count_before=before, replica_count_after=before + 1, model_version=model_version)
                        self.events_repository.insert(event)
                        return event
                    time.sleep(1)
                container.remove(force=True)
                raise RuntimeError("New application replica did not become healthy within 45 seconds.")
            except Exception as error:
                event = ScalingEventDocument(timestamp=datetime.now(timezone.utc), policy=policy, action=action, reason=f"{reason}; failed: {error}", replica_count_before=before, replica_count_after=before, status="failed", model_version=model_version)
                self.events_repository.insert(event)
                return event
        if action == "scale_in" and before > minimum:
            target = replicas[0]
            try:
                self._safe_remove(target.id)
                self.last_change_at = time.monotonic()
                event = ScalingEventDocument(timestamp=datetime.now(timezone.utc), policy=policy, action=action, reason=reason, replica_count_before=before, replica_count_after=before - 1, model_version=model_version)
                self.events_repository.insert(event)
                return event
            except Exception as error:
                event = ScalingEventDocument(timestamp=datetime.now(timezone.utc), policy=policy, action=action, reason=f"{reason}; failed: {error}", replica_count_before=before, replica_count_after=before, status="failed", model_version=model_version)
                self.events_repository.insert(event)
                return event
        return None

    def _membership_container(self):
        controllers = self.client.containers.list(filters={"label": "com.docker.compose.service=membership-controller"})
        if len(controllers) != 1:
            raise RuntimeError("Expected exactly one membership controller.")
        return controllers[0]

    def _sync_membership(self) -> None:
        result = self._membership_container().exec_run(["python", "controller.py", "sync"])
        if result.exit_code != 0:
            raise RuntimeError(result.output.decode(errors="replace"))

    def _safe_remove(self, container_id: str) -> None:
        result = self._membership_container().exec_run(["python", "controller.py", "remove", container_id])
        if result.exit_code != 0:
            raise RuntimeError(result.output.decode(errors="replace"))
