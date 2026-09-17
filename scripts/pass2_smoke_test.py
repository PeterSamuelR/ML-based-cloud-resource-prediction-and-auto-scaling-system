"""Observed-value Pass 2 validation: training, feedback, and safe scaling."""

from __future__ import annotations

import json
import os
import subprocess
import time
import urllib.request


def command(*arguments: str, environment: dict[str, str] | None = None) -> str:
    completed = subprocess.run(arguments, check=False, capture_output=True, text=True, encoding="utf-8", errors="replace", env=environment)
    if completed.returncode:
        raise RuntimeError(f"{' '.join(arguments)} failed:\n{completed.stdout}{completed.stderr}")
    return completed.stdout


def api(path: str) -> dict:
    with urllib.request.urlopen(f"http://127.0.0.1:8001{path}", timeout=5) as response:
        return json.loads(response.read())


def wait_for(path: str, predicate, timeout: int = 150) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            value = api(path)
            if predicate(value):
                return value
        except Exception:
            pass
        time.sleep(5)
    raise RuntimeError(f"Timed out waiting for {path}.")


def main() -> None:
    environment = os.environ.copy()
    environment.update({"AUTOSCALING_POLICY": "predictive"})
    try:
        command("docker", "compose", "up", "-d", "--build", "--scale", "application=1", environment=environment)
        wait_for("/api/metrics/current", lambda metric: metric["active_healthy_replica_count"] >= 1)
        workload_environment = os.environ.copy()
        workload_environment.update({"LOCUST_WORKLOAD_SCENARIO": "stable", "LOCUST_WORK_DURATION_MS": "150", "LOCUST_WORK_INTENSITY": "100", "LOCUST_WAIT_MIN_SECONDS": "0.01", "LOCUST_WAIT_MAX_SECONDS": "0.03"})
        command("python", "-m", "locust", "-f", "load-tests/locustfile.py", "--headless", "-u", "8", "-r", "4", "-t", "95s", environment=workload_environment)
        model = wait_for("/api/models", lambda response: bool(response["items"]))["items"][0]
        predictions = wait_for("/api/predictions", lambda response: any(item.get("absolute_error") is not None for item in response["items"]))
        events = wait_for("/api/scaling/events", lambda response: bool(response["items"]))
        print("Measured model metadata:")
        print(json.dumps(model, default=str, indent=2))
        print("Measured evaluated prediction:")
        print(json.dumps(next(item for item in predictions["items"] if item.get("absolute_error") is not None), default=str, indent=2))
        print("Observed scaling event:")
        print(json.dumps(events["items"][0], default=str, indent=2))
    finally:
        subprocess.run(["docker", "compose", "down", "--remove-orphans", "--volumes"], check=False)


if __name__ == "__main__":
    main()
