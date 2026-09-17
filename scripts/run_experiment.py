"""Run one recorded, bounded Locust experiment against the local Compose environment.

This runner records observations; it does not infer performance improvements. Run
each compared policy from equivalent declared starting conditions as required by
docs/experiment-protocol.md.
"""

from __future__ import annotations

import argparse
import base64
import csv
import json
import os
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen

import yaml


API = "http://127.0.0.1:8001"
SCENARIOS = ("stable", "gradual_increase", "sudden_spike", "sudden_drop", "periodic", "changing_workload")
POLICIES = ("reactive", "predictive", "adaptive_predictive")


def now() -> datetime:
    return datetime.now(timezone.utc)


def request(path: str) -> dict:
    with urlopen(f"{API}{path}", timeout=10) as response:
        return json.loads(response.read())


def command(arguments: list[str], environment: dict[str, str] | None = None) -> None:
    completed = subprocess.run(arguments, env=environment, text=True, capture_output=True)
    if completed.returncode:
        raise RuntimeError(f"Command failed: {' '.join(arguments)}\n{completed.stdout}\n{completed.stderr}")


def timestamp(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value.replace("Z", "+00:00")) if value else None


def in_window(items: list[dict], start: datetime, end: datetime, field: str = "timestamp") -> list[dict]:
    return [item for item in items if (item_time := timestamp(item.get(field))) and start <= item_time <= end]


def mean(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 3) if values else None


def summarize(metrics: list[dict], predictions: list[dict], scaling_events: list[dict], models: list[dict]) -> dict:
    errors = [float(item["absolute_error"]) for item in predictions if item.get("absolute_error") is not None]
    response_times = [float(item["response_time_ms"]) for item in metrics if item.get("response_time_ms") is not None]
    return {
        "metric_count": len(metrics), "prediction_count": len(predictions), "evaluated_prediction_count": len(errors),
        "mean_aggregate_cpu_percent": mean([float(item["aggregate_cpu_percent"]) for item in metrics if item.get("aggregate_cpu_percent") is not None]),
        "mean_aggregate_memory_percent": mean([float(item["aggregate_memory_percent"]) for item in metrics if item.get("aggregate_memory_percent") is not None]),
        "mean_request_rate_per_second": mean([float(item.get("request_rate_per_second", 0)) for item in metrics]),
        "mean_response_time_ms": mean(response_times),
        "prediction_mae": mean(errors),
        "prediction_rmse": round((sum(value * value for value in errors) / len(errors)) ** 0.5, 3) if errors else None,
        "scaling_event_count": len(scaling_events),
        "scale_out_count": sum(item.get("action") == "scale_out" for item in scaling_events),
        "scale_in_count": sum(item.get("action") == "scale_in" for item in scaling_events),
        "adaptation_attempt_count": sum(bool(item.get("metadata", {}).get("retraining_attempted_at")) for item in models),
    }


def config_snapshot() -> dict:
    root = Path(__file__).resolve().parents[1]
    default = yaml.safe_load((root / "config" / "default.yaml").read_text(encoding="utf-8"))
    reactive = yaml.safe_load((root / "config" / "reactive.yaml").read_text(encoding="utf-8"))
    predictive = yaml.safe_load((root / "config" / "predictive.yaml").read_text(encoding="utf-8"))
    return {"default": default, "reactive": reactive, "predictive": predictive}


def save_exports(experiment_id: str, directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for extension in ("json", "csv"):
        with urlopen(f"{API}/api/experiments/{experiment_id}/export?format={extension}", timeout=15) as response:
            (directory / f"{experiment_id}.{extension}").write_bytes(response.read())


def run_trial(arguments: argparse.Namespace) -> dict:
    environment = os.environ.copy()
    environment["AUTOSCALING_POLICY"] = arguments.policy
    command(["docker", "compose", "up", "-d", "--build", "--scale", f"application={arguments.initial_replicas}"], environment)
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        try:
            status = request("/api/status")
            if status["monitoring"] == "healthy" and status["active_healthy_replica_count"] == arguments.initial_replicas:
                break
        except Exception:
            pass
        time.sleep(2)
    else:
        raise RuntimeError("The requested equivalent starting replica state was not observed.")

    experiment_id = f"experiment-{uuid.uuid4().hex[:12]}"
    start = now()
    locust_environment = environment | {
        "LOCUST_WORKLOAD_SCENARIO": arguments.scenario,
        "LOCUST_WORK_DURATION_MS": str(arguments.work_duration_ms),
        "LOCUST_WORK_INTENSITY": str(arguments.work_intensity),
        "LOCUST_PHASE_SECONDS": str(arguments.phase_seconds),
        "LOCUST_WAIT_MIN_SECONDS": str(arguments.wait_min_seconds),
        "LOCUST_WAIT_MAX_SECONDS": str(arguments.wait_max_seconds),
    }
    command([sys.executable, "-m", "locust", "-f", "load-tests/locustfile.py", "--headless", "-u", str(arguments.users), "-r", str(arguments.spawn_rate), "-t", f"{arguments.duration_seconds}s"], locust_environment)
    time.sleep(30 + 5 + 3)  # Allow the locked horizon and one monitor sample for feedback.
    end = now()

    metrics = in_window(request("/api/metrics/history?limit=1000")["items"], start, end)
    predictions = in_window(request("/api/predictions?limit=1000")["items"], start, end)
    scaling_events = in_window(request("/api/scaling/events?limit=1000")["items"], start, end)
    all_models = request("/api/models?limit=1000")["items"]
    model_versions = [item for item in all_models if (created := timestamp(item.get("created_at"))) and start <= created <= end]
    active_model = next((item.get("version") for item in all_models if item.get("status") == "active"), None)
    payload = {
        "experiment_id": experiment_id, "started_at": start.isoformat(), "status": "completed",
        "configuration": {
            "policy": arguments.policy, "workload": vars(arguments) | {"scenario": arguments.scenario},
            "initial_replicas": arguments.initial_replicas, "application_image": "cloud-resource-autoscaling-app:phase3",
            "monitoring_interval_seconds": 5, "prediction_horizon_seconds": 30,
            "aggregate_cpu_definition": "mean_active_healthy_application_replicas", "configuration_snapshot": config_snapshot(),
        },
        "results": {
            "ended_at": end.isoformat(), "active_model_version": active_model, "metrics": metrics, "predictions": predictions,
            "scaling_events": scaling_events, "model_versions": model_versions,
            "summary": summarize(metrics, predictions, scaling_events, model_versions),
        },
    }
    encoded = base64.b64encode(json.dumps(payload, default=str).encode("utf-8")).decode("ascii")
    command(["docker", "compose", "exec", "-T", "backend", "python", "-m", "src.services.experiments.recorder", encoded], environment)
    if arguments.export_directory:
        save_exports(experiment_id, Path(arguments.export_directory))
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run one observed, reproducible local autoscaling trial.")
    parser.add_argument("--policy", choices=POLICIES, required=True)
    parser.add_argument("--scenario", choices=SCENARIOS, required=True)
    parser.add_argument("--duration-seconds", type=int, default=60)
    parser.add_argument("--users", type=int, default=5)
    parser.add_argument("--spawn-rate", type=float, default=2)
    parser.add_argument("--initial-replicas", type=int, default=1)
    parser.add_argument("--work-duration-ms", type=int, default=100)
    parser.add_argument("--work-intensity", type=int, default=20)
    parser.add_argument("--phase-seconds", type=int, default=10)
    parser.add_argument("--wait-min-seconds", type=float, default=0.1)
    parser.add_argument("--wait-max-seconds", type=float, default=0.3)
    parser.add_argument("--export-directory", default="results")
    return parser.parse_args()


if __name__ == "__main__":
    outcome = run_trial(parse_args())
    print(json.dumps({"experiment_id": outcome["experiment_id"], "summary": outcome["results"]["summary"]}, indent=2))
