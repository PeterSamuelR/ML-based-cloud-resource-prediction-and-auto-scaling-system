"""Observed-value validation for Locust → Nginx → apps → monitoring → MongoDB → API."""

from __future__ import annotations

import json
import os
import subprocess
import time
import urllib.request


def run(*arguments: str, environment: dict[str, str] | None = None) -> None:
    completed = subprocess.run(
        arguments, check=False, text=True, encoding="utf-8", errors="replace", env=environment, capture_output=True
    )
    if completed.returncode != 0:
        raise RuntimeError(f"Command failed ({completed.returncode}): {' '.join(arguments)}\n{completed.stdout}{completed.stderr}")


def api(path: str) -> dict:
    with urllib.request.urlopen(f"http://127.0.0.1:8001{path}", timeout=5) as response:
        return json.loads(response.read())


def wait_for_metric() -> dict:
    deadline = time.monotonic() + 75
    while time.monotonic() < deadline:
        try:
            metric = api("/api/metrics/current")
            if metric["active_healthy_replica_count"] >= 2:
                return metric
        except Exception:
            pass
        time.sleep(2)
    raise RuntimeError("Monitoring did not produce the expected healthy-replica/traffic metric in time.")


def observed_traffic_metric() -> dict:
    history = api("/api/metrics/history?limit=20")
    for metric in history["items"]:
        if metric["request_rate_per_second"] > 0 and metric["response_time_ms"] is not None:
            return metric
    raise RuntimeError("No persisted metric captured Locust traffic.")


def main() -> None:
    try:
        run("docker", "compose", "up", "-d", "--build", "--scale", "application=2")
        wait_for_metric()
        environment = os.environ.copy()
        environment.update({"LOCUST_WORKLOAD_SCENARIO": "stable", "LOCUST_WORK_DURATION_MS": "25", "LOCUST_WORK_INTENSITY": "10"})
        run("python", "-m", "locust", "-f", "load-tests/locustfile.py", "--headless", "-u", "2", "-r", "2", "-t", "12s", environment=environment)
        metric = observed_traffic_metric()
        history = api("/api/metrics/history?limit=10")
        containers = api("/api/containers")
        print("Observed metric:")
        print(json.dumps(metric, default=str, indent=2))
        print(f"Observed persisted metric records returned by API: {len(history['items'])}")
        print(f"Observed healthy application containers returned by API: {len(containers['items'])}")
    finally:
        subprocess.run(["docker", "compose", "down", "--remove-orphans", "--volumes"], check=False)


if __name__ == "__main__":
    main()
