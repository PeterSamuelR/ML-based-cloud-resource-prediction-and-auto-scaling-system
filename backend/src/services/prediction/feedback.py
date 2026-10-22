from __future__ import annotations

from datetime import datetime, timezone


def evaluate_due_predictions(predictions_collection, metric: dict, tolerance_seconds: int = 3) -> int:
    """Attach only observed future aggregate CPU to due, unevaluated forecasts."""
    if metric.get("aggregate_cpu_percent") is None:
        return 0
    current_time = metric["timestamp"]
    if current_time.tzinfo is None:
        current_time = current_time.replace(tzinfo=timezone.utc)
    candidates = predictions_collection.find({"actual_aggregate_cpu_percent": None, "target_timestamp": {"$lte": current_time}})
    count = 0
    for prediction in candidates:
        target = prediction["target_timestamp"]
        if target.tzinfo is None:
            target = target.replace(tzinfo=timezone.utc)
        if abs((current_time - target).total_seconds()) > tolerance_seconds:
            continue
        error = abs(prediction["predicted_aggregate_cpu_percent"] - metric["aggregate_cpu_percent"])
        predictions_collection.update_one({"_id": prediction["_id"]}, {"$set": {"actual_aggregate_cpu_percent": metric["aggregate_cpu_percent"], "absolute_error": round(error, 3), "evaluated_at": datetime.now(timezone.utc)}})
        count += 1
    return count


def observed_sampling_tolerance(
    previous_timestamp: datetime | None,
    current_timestamp: datetime,
    interval_seconds: int,
    maximum_lateness_seconds: int,
) -> int:
    """Allow the actual collection cadence, bounded to avoid stale target pairing."""
    nominal = max(1, int(interval_seconds))
    maximum = max(nominal, int(maximum_lateness_seconds))
    if previous_timestamp is None:
        return min(nominal, maximum)
    previous = _aware(previous_timestamp)
    current = _aware(current_timestamp)
    observed = max(nominal, int((current - previous).total_seconds() + 0.999))
    return min(observed, maximum)


def _aware(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value
