from fastapi import APIRouter, Depends, HTTPException, Query

from src.repositories.metrics import MetricsRepository

router = APIRouter(prefix="/api")


def get_metrics_repository() -> MetricsRepository:
    from src.main import metrics_repository
    return metrics_repository


def get_repositories():
    from src.main import document_repositories
    return document_repositories


@router.get("/metrics/current")
def current_metrics(repository: MetricsRepository = Depends(get_metrics_repository)):
    metric = repository.latest()
    if metric is None:
        raise HTTPException(status_code=404, detail="No metrics have been collected yet.")
    metric.pop("_id", None)
    return metric


@router.get("/metrics/history")
def metric_history(limit: int = Query(default=100, ge=1, le=1_000), repository: MetricsRepository = Depends(get_metrics_repository)):
    metrics = repository.history(limit)
    for metric in metrics:
        metric.pop("_id", None)
    return {"items": metrics}


@router.get("/status")
def system_status(repository: MetricsRepository = Depends(get_metrics_repository)):
    latest = repository.latest()
    if latest is None:
        return {"monitoring": "waiting_for_first_sample", "active_healthy_replica_count": 0}
    latest.pop("_id", None)
    return {
        "monitoring": "degraded" if latest.get("collection_error") else "healthy",
        "last_sample_timestamp": latest["timestamp"],
        "active_healthy_replica_count": latest["active_healthy_replica_count"],
        "collection_error": latest.get("collection_error"),
    }


@router.get("/containers")
def active_containers(repository: MetricsRepository = Depends(get_metrics_repository)):
    latest = repository.latest()
    if latest is None:
        return {"items": []}
    return {"items": latest.get("per_container", [])}


@router.get("/predictions")
def predictions(limit: int = Query(default=100, ge=1, le=1_000), repositories=Depends(get_repositories)):
    items = repositories["predictions"].history(limit)
    for item in items:
        item.pop("_id", None)
    return {"items": items}


@router.get("/models")
def models(limit: int = Query(default=100, ge=1, le=1_000), repositories=Depends(get_repositories)):
    items = repositories["model_versions"].history(limit)
    for item in items:
        item.pop("_id", None)
    return {"items": items}


@router.get("/scaling/events")
def scaling_events(limit: int = Query(default=100, ge=1, le=1_000), repositories=Depends(get_repositories)):
    items = repositories["scaling_events"].history(limit)
    for item in items:
        item.pop("_id", None)
    return {"items": items}
