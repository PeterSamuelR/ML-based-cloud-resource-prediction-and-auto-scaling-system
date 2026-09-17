from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager

import docker
from fastapi import FastAPI

from src.api.routes import router
from src.core.config import load_config
from src.repositories.database import create_document_repositories, create_metrics_repository
from src.services.monitoring.collector import DockerMetricsCollector
from src.services.monitoring.nginx_logs import NginxAccessLogReader
from src.services.prediction.feedback import evaluate_due_predictions
from src.services.prediction.trainer import RandomForestPredictionService
from src.services.scaling.controller import ScalingController

metrics_repository = create_metrics_repository()
document_repositories = create_document_repositories()
config = load_config()
prediction_service = RandomForestPredictionService(metrics_repository, document_repositories["model_versions"], config)
scaling_controller = None


async def monitoring_loop() -> None:
    global scaling_controller
    interval = float(os.getenv("MONITORING_INTERVAL_SECONDS", "5"))
    docker_client = docker.from_env()
    collector = DockerMetricsCollector(
        docker_client,
        NginxAccessLogReader(os.getenv("NGINX_ACCESS_LOG", "/var/log/nginx/access.json"), interval),
    )
    scaling_controller = ScalingController(docker_client, document_repositories["scaling_events"], config)
    while True:
        try:
            metric = await asyncio.to_thread(collector.collect)
            await asyncio.to_thread(metrics_repository.insert, metric)
            await asyncio.to_thread(evaluate_due_predictions, document_repositories["predictions"].collection, metric.model_dump())
            await asyncio.to_thread(prediction_service.train_if_needed)
            prediction = prediction_service.predict(metric.model_dump())
            selected_policy = config["selected_policy"]
            if prediction is not None:
                await asyncio.to_thread(document_repositories["predictions"].insert, prediction)
                decision_policy, decision_cpu = selected_policy, prediction.predicted_aggregate_cpu_percent
            else:
                decision_policy, decision_cpu = "reactive", metric.aggregate_cpu_percent
            await asyncio.to_thread(scaling_controller.execute, decision_cpu, decision_policy, prediction.model_version if prediction else None)
        except Exception as error:
            # The next interval retries. The service remains available for reads.
            print(f"Monitoring cycle failed: {error}", flush=True)
        await asyncio.sleep(interval)


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
