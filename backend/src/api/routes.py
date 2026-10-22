import csv
import io
import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response

from src.repositories.metrics import MetricsRepository

router = APIRouter(prefix="/api")


def get_metrics_repository() -> MetricsRepository:
    from src.main import metrics_repository
    return metrics_repository


def get_repositories():
    from src.main import document_repositories
    return document_repositories


def get_config():
    from src.main import config
    return config


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
def system_status(repository: MetricsRepository = Depends(get_metrics_repository), config: dict = Depends(get_config)):
    latest = repository.latest()
    if latest is None:
        return {"monitoring": "waiting_for_first_sample", "active_healthy_replica_count": 0}
    latest.pop("_id", None)
    return {
        "monitoring": "degraded" if latest.get("collection_error") else "healthy",
        "autoscaling_mode": config["selected_policy"],
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


@router.get("/predictions/current")
def current_prediction(repositories=Depends(get_repositories), config: dict = Depends(get_config)):
    """Return the newest forecast with an explicit, server-computed freshness state."""
    prediction_repository = repositories["predictions"]
    model_repository = repositories["model_versions"]
    prediction = prediction_repository.collection.find_one(sort=[("timestamp", -1)])
    active_model = model_repository.collection.find_one(
        {"status": "active"}, sort=[("created_at", -1)]
    )
    if active_model is None:
        return {"status": "unavailable", "prediction": None, "reason": "no_active_model"}

    now = datetime.now(timezone.utc)
    if prediction is None:
        return {"status": "unavailable", "prediction": None, "reason": "no_prediction_record"}

    prediction.pop("_id", None)
    timestamp = _as_utc(prediction["timestamp"])
    age_seconds = max(0.0, (now - timestamp).total_seconds())
    training_window = active_model.get("metadata", {}).get("training_window", {})
    training_end = training_window.get("end_timestamp") or active_model.get("created_at")
    model_age = max(0.0, (now - _as_utc(training_end)).total_seconds()) if training_end else None
    maximum_prediction_age = max(
        15.0,
        float(config["monitoring"]["interval_seconds"]) * 3,
    )
    reason = None
    if prediction.get("model_version") != active_model.get("version"):
        reason = "prediction_model_is_not_active"
    elif age_seconds > maximum_prediction_age:
        reason = "prediction_record_is_too_old"

    return {
        "status": "stale" if reason else "live",
        "prediction": prediction,
        "prediction_timestamp": timestamp,
        "prediction_age_seconds": round(age_seconds, 3),
        "active_model_version": active_model.get("version"),
        "model_training_timestamp": _as_utc(training_end) if training_end else None,
        "age_seconds": round(age_seconds, 3),
        "maximum_prediction_age_seconds": maximum_prediction_age,
        "model_age_seconds": round(model_age, 3) if model_age is not None else None,
        "reason": reason,
    }


def _as_utc(value):
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00")) if isinstance(value, str) else value
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed


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


@router.get("/experiments")
def experiments(limit: int = Query(default=100, ge=1, le=1_000), repositories=Depends(get_repositories)):
    items = repositories["experiments"].history(limit)
    for item in items:
        item.pop("_id", None)
    return {"items": items}


@router.get("/experiments/{experiment_id}/export")
def export_experiment(experiment_id: str, format: str = Query(default="json", pattern="^(json|csv)$"), repositories=Depends(get_repositories)):
    item = repositories["experiments"].collection.find_one({"experiment_id": experiment_id})
    if item is None:
        raise HTTPException(status_code=404, detail="Experiment not found.")
    item.pop("_id", None)
    if format == "json":
        return item

    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=["record_type", "experiment_id", "policy", "timestamp", "model_version", "payload_json"])
    writer.writeheader()
    policy = item.get("configuration", {}).get("policy", "")
    writer.writerow({"record_type": "experiment", "experiment_id": experiment_id, "policy": policy, "timestamp": item.get("started_at", ""), "model_version": "", "payload_json": json.dumps(item, default=str)})
    results = item.get("results", {})
    for record_type, key in (("metric", "metrics"), ("prediction", "predictions"), ("scaling_event", "scaling_events"), ("model_version", "model_versions")):
        for record in results.get(key, []):
            writer.writerow({
                "record_type": record_type, "experiment_id": experiment_id, "policy": policy,
                "timestamp": record.get("timestamp", record.get("created_at", "")), "model_version": record.get("model_version", record.get("version", "")),
                "payload_json": json.dumps(record, default=str),
            })
    return Response(stream.getvalue(), media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="{experiment_id}.csv"'})
