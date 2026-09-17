"""Small, intentionally bounded FastAPI workload target."""

from __future__ import annotations

import os
import socket
import time
from datetime import datetime, timezone
from typing import Annotated

from fastapi import FastAPI, Query, Request
from fastapi.responses import JSONResponse

DEFAULT_WORK_DURATION_MS = 100
MAX_WORK_DURATION_MS = 2_000
DEFAULT_WORK_INTENSITY = 10
MAX_WORK_INTENSITY = 100

app = FastAPI(title="Scalable Application Target", version="0.1.0")


def instance_id() -> str:
    """Return an explicit instance ID when supplied, otherwise the hostname."""
    return os.getenv("INSTANCE_ID", socket.gethostname())


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def perform_cpu_work(duration_ms: int, intensity: int) -> float:
    """Use bounded arithmetic work until the requested time budget is consumed."""
    started = time.perf_counter()
    deadline = started + (duration_ms / 1_000)
    accumulator = 0

    while time.perf_counter() < deadline:
        for value in range(intensity * 200):
            accumulator = (accumulator * 1_103_515_245 + value + 12_345) & 0x7FFFFFFF

    # Keep the loop's arithmetic observable without exposing an irrelevant result.
    if accumulator < 0:  # pragma: no cover - defensive and unreachable with the bitmask above
        raise RuntimeError("Unexpected workload accumulator")

    return (time.perf_counter() - started) * 1_000


@app.middleware("http")
async def add_response_timing(request: Request, call_next):
    """Expose server-side request duration for future monitoring integration."""
    started = time.perf_counter()
    response = await call_next(request)
    response.headers["X-Process-Time-Ms"] = f"{(time.perf_counter() - started) * 1_000:.3f}"
    return response


@app.get("/")
def root() -> dict[str, str]:
    return {
        "status": "running",
        "instance_id": instance_id(),
        "timestamp": utc_timestamp(),
    }


@app.get("/health")
def health() -> JSONResponse:
    return JSONResponse(status_code=200, content={"status": "healthy"})


@app.get("/work")
def work(
    duration_ms: Annotated[
        int,
        Query(
            ge=1,
            le=MAX_WORK_DURATION_MS,
            description="Bounded CPU-work time budget in milliseconds.",
        ),
    ] = DEFAULT_WORK_DURATION_MS,
    intensity: Annotated[
        int,
        Query(
            ge=1,
            le=MAX_WORK_INTENSITY,
            description="Bounded arithmetic work performed in each loop batch.",
        ),
    ] = DEFAULT_WORK_INTENSITY,
) -> dict[str, object]:
    actual_duration_ms = perform_cpu_work(duration_ms=duration_ms, intensity=intensity)
    return {
        "instance_id": instance_id(),
        "timestamp": utc_timestamp(),
        "requested_workload": {
            "duration_ms": duration_ms,
            "intensity": intensity,
        },
        "actual_execution_duration_ms": round(actual_duration_ms, 3),
    }
