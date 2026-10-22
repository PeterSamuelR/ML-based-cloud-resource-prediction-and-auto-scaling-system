from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager

import docker
from fastapi import FastAPI

from src.api.routes import router
from src.core.config import load_config
from src.repositories.database import create_document_repositories, create_metrics_repository
from src.services.adaptation.service import AdaptiveRetrainingService
from src.services.monitoring.collector import DockerMetricsCollector
from src.services.monitoring.nginx_logs import NginxAccessLogReader
from src.services.prediction.feedback import evaluate_due_predictions, observed_sampling_tolerance
from src.services.prediction.trainer import RandomForestPredictionService
from src.services.scaling.controller import ScalingController

metrics_repository = create_metrics_repository()
document_repositories = create_document_repositories()
config = load_config()
prediction_service = RandomForestPredictionService(metrics_repository, document_repositories["model_versions"], config)
adaptive_service = AdaptiveRetrainingService(document_repositories["predictions"].collection, prediction_service, config)
scaling_controller = None


def next_collection_schedule(next_collection_at: float, now: float, interval: float) -> tuple[float, float]:
    """Advance a monotonic sampling schedule without adding work time to it."""
    next_collection_at += interval
    if next_collection_at <= now:
        missed_intervals = int((now - next_collection_at) // interval) + 1
        next_collection_at += missed_intervals * interval
    return next_collection_at, max(0.0, next_collection_at - now)


async def monitoring_loop() -> None:
    global scaling_controller
    interval = float(os.getenv("MONITORING_INTERVAL_SECONDS", "5"))
    docker_client = docker.from_env()
    collector = DockerMetricsCollector(
        docker_client,
        NginxAccessLogReader(os.getenv("NGINX_ACCESS_LOG", "/var/log/nginx/access.json"), interval),
    )
    scaling_controller = ScalingController(docker_client, document_repositories["scaling_events"], config)
    last_metric_timestamp = None
    loop = asyncio.get_running_loop()
    next_collection_at = loop.time()
    scaling_task: asyncio.Task | None = None
    training_task: asyncio.Task | None = None
    adaptation_task: asyncio.Task | None = None
    while True:
        if scaling_task is not None and scaling_task.done():
            try:
                scaling_task.result()
            except Exception as error:
                print(f"Scaling action failed: {error}", flush=True)
            scaling_task = None
        if training_task is not None and training_task.done():
            try:
                trained = training_task.result()
                if trained:
                    print(f"Model training/refresh completed: {trained.get('version', 'initial model')}", flush=True)
            except Exception as error:
                print(f"Model training/refresh failed: {error}", flush=True)
            training_task = None
        if adaptation_task is not None and adaptation_task.done():
            try:
                adaptation = adaptation_task.result()
                if adaptation["outcome"] in {"activated", "rejected"}:
                    print(f"Adaptive retraining {adaptation['outcome']}: {adaptation}", flush=True)
            except Exception as error:
                print(f"Adaptive evaluation failed: {error}", flush=True)
            adaptation_task = None
        try:
            metric = await asyncio.to_thread(collector.collect)
            await asyncio.to_thread(metrics_repository.insert, metric)
            # A forecast may be observed by the first sample after its target time.
            # Collection work can make the observed cadence longer than its setting.
            feedback_tolerance = observed_sampling_tolerance(
                last_metric_timestamp,
                metric.timestamp,
                config["monitoring"]["interval_seconds"],
                config["prediction"].get("max_feedback_lateness_seconds", 15),
            )
            await asyncio.to_thread(
                evaluate_due_predictions,
                document_repositories["predictions"].collection,
                metric.model_dump(),
                feedback_tolerance,
            )
            last_metric_timestamp = metric.timestamp
            # Initial training and stale-model candidate refresh can read a
            # large history and tune several forests. Keep only one worker and
            # never await it from the five-second monitoring path.
            if training_task is None:
                training_task = asyncio.create_task(asyncio.to_thread(prediction_service.train_if_needed))
            # CLI/manual refresh can activate a model outside this process; use
            # the active-version pointer, not a stale in-memory model instance.
            await asyncio.to_thread(prediction_service.refresh_active_model_if_changed)
            prediction = prediction_service.predict(metric.model_dump())
            selected_policy = config["selected_policy"]
            if selected_policy == "adaptive_predictive" and adaptation_task is None:
                # Error evaluation/retraining is debounced by a single in-flight
                # task; the existing service enforces breach count, sample,
                # cooldown, and validation gates.
                adaptation_task = asyncio.create_task(asyncio.to_thread(adaptive_service.evaluate))
            if prediction is not None:
                await asyncio.to_thread(document_repositories["predictions"].insert, prediction)
                if selected_policy == "reactive":
                    decision_policy, decision_cpu = "reactive", metric.aggregate_cpu_percent
                else:
                    decision_policy, decision_cpu = selected_policy, prediction.predicted_aggregate_cpu_percent
            else:
                decision_policy, decision_cpu = "reactive", metric.aggregate_cpu_percent
            # Replica startup includes Docker health polling and Nginx membership
            # synchronization. Keep that work off the monitoring cadence, and do
            # not queue overlapping scaling decisions while one is in flight.
            if scaling_task is None:
                scaling_task = asyncio.create_task(asyncio.to_thread(
                    scaling_controller.execute,
                    decision_cpu,
                    decision_policy,
                    prediction.model_version if prediction else None,
                ))
        except Exception as error:
            # The next interval retries. The service remains available for reads.
            print(f"Monitoring cycle failed: {error}", flush=True)
        # Schedule against a monotonic 5-second cadence instead of sleeping an
        # additional full interval after collection/model work has completed.
        next_collection_at, delay = next_collection_schedule(next_collection_at, loop.time(), interval)
        await asyncio.sleep(delay)


@asynccontextmanager
async def lifespan(_: FastAPI):
    try:
        metrics_repository.ensure_indexes()
        for repository in document_repositories.values():
            repository.ensure_indexes()
    except Exception as error:
        print(f"MongoDB index setup deferred: {error}", flush=True)
    task = asyncio.create_task(monitoring_loop())
    yield
    task.cancel()


app = FastAPI(title="Cloud Resource Autoscaling Read API", lifespan=lifespan)
app.include_router(router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "healthy"}
