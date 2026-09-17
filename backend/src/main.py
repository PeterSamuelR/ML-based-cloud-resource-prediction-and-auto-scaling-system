from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager

import docker
from fastapi import FastAPI

from src.api.routes import router
from src.repositories.database import create_metrics_repository
from src.services.monitoring.collector import DockerMetricsCollector
from src.services.monitoring.nginx_logs import NginxAccessLogReader

metrics_repository = create_metrics_repository()


async def monitoring_loop() -> None:
    interval = float(os.getenv("MONITORING_INTERVAL_SECONDS", "5"))
    collector = DockerMetricsCollector(
        docker.from_env(),
        NginxAccessLogReader(os.getenv("NGINX_ACCESS_LOG", "/var/log/nginx/access.json"), interval),
    )
    while True:
        try:
            metric = await asyncio.to_thread(collector.collect)
            await asyncio.to_thread(metrics_repository.insert, metric)
        except Exception as error:
            # The next interval retries. The service remains available for reads.
            print(f"Monitoring cycle failed: {error}", flush=True)
        await asyncio.sleep(interval)


@asynccontextmanager
async def lifespan(_: FastAPI):
    try:
        metrics_repository.ensure_indexes()
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
