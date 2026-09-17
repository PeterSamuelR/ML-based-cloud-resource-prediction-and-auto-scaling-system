from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ContainerMetric(BaseModel):
    container_id: str
    container_name: str
    cpu_percent: float
    memory_percent: float


class MetricDocument(BaseModel):
    timestamp: datetime
    per_container: list[ContainerMetric] = Field(default_factory=list)
    aggregate_cpu_percent: float | None
    aggregate_memory_percent: float | None
    request_rate_per_second: float
    response_time_ms: float | None
    active_healthy_replica_count: int
    collection_error: str | None = None


class PredictionDocument(BaseModel):
    timestamp: datetime
    target_timestamp: datetime
    predicted_aggregate_cpu_percent: float
    model_version: str
    actual_aggregate_cpu_percent: float | None = None
    absolute_error: float | None = None
    evaluated_at: datetime | None = None


class ScalingEventDocument(BaseModel):
    timestamp: datetime
    policy: str
    action: str
    reason: str
    replica_count_before: int
    replica_count_after: int
    status: str = "completed"
    model_version: str | None = None


class ModelVersionDocument(BaseModel):
    version: str
    created_at: datetime
    status: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExperimentDocument(BaseModel):
    experiment_id: str
    started_at: datetime
    status: str
    configuration: dict[str, Any] = Field(default_factory=dict)
    results: dict[str, Any] = Field(default_factory=dict)
