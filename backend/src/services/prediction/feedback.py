from __future__ import annotations

from datetime import datetime, timezone


def evaluate_due_predictions(predictions_collection, metric: dict, tolerance_seconds: int = 3) -> int:
    """Attach only observed future aggregate CPU to due, unevaluated forecasts."""
    if metric.get("aggregate_cpu_percent") is None:
        return 0
    current_time = metric["timestamp"]
    candidates = predictions_collection.find({"actual_aggregate_cpu_percent": None, "target_timestamp": {"$lte": current_time}})
    count = 0
    for prediction in candidates:
        target = prediction["target_timestamp"]
        if abs((current_time - target).total_seconds()) > tolerance_seconds:
            continue
        error = abs(prediction["predicted_aggregate_cpu_percent"] - metric["aggregate_cpu_percent"])
        predictions_collection.update_one({"_id": prediction["_id"]}, {"$set": {"actual_aggregate_cpu_percent": metric["aggregate_cpu_percent"], "absolute_error": round(error, 3), "evaluated_at": datetime.now(timezone.utc)}})
        count += 1
    return count
