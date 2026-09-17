from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


class AdaptiveRetrainingService:
    """Error-gated, cooldown-protected retraining for the active predictor."""

    def __init__(self, predictions_collection, prediction_service, config: dict[str, Any]):
        self.predictions_collection = predictions_collection
        self.prediction_service = prediction_service
        self.config = config

    def evaluate(self, now: datetime | None = None) -> dict[str, Any]:
        now = now or datetime.now(timezone.utc)
        adaptive = self.config["adaptive"]
        required = adaptive["consecutive_error_requirement"]
        errors = list(self.predictions_collection.find(
            {"absolute_error": {"$ne": None}, "evaluated_at": {"$ne": None}}
        ).sort("evaluated_at", -1).limit(required))
        if len(errors) < required:
            return {"outcome": "not_triggered", "reason": "insufficient_evaluated_predictions", "count": len(errors)}
        if not all(float(error["absolute_error"]) > adaptive["absolute_error_threshold"] for error in errors):
            return {"outcome": "not_triggered", "reason": "error_threshold_not_persistent", "count": len(errors)}

        latest_attempt = self._latest_attempt()
        latest_error_at = self._aware(errors[0]["evaluated_at"])
        if latest_attempt:
            attempted_at = self._aware(latest_attempt["metadata"]["retraining_attempted_at"])
            if latest_error_at <= attempted_at:
                return {"outcome": "not_triggered", "reason": "no_new_errors_since_last_attempt"}
            elapsed = (now - attempted_at).total_seconds()
            if elapsed < adaptive["retraining_cooldown_seconds"]:
                return {"outcome": "not_triggered", "reason": "retraining_cooldown", "remaining_seconds": round(adaptive["retraining_cooldown_seconds"] - elapsed, 3)}

        trigger = {
            "absolute_error_threshold": adaptive["absolute_error_threshold"],
            "consecutive_error_requirement": required,
            "breaches": [
                {"prediction_timestamp": item["timestamp"], "evaluated_at": item["evaluated_at"], "absolute_error": item["absolute_error"]}
                for item in reversed(errors)
            ],
        }
        return self.prediction_service.retrain_recent(trigger)

    def _latest_attempt(self) -> dict | None:
        return self.prediction_service.model_repository.collection.find_one(
            {"metadata.retraining_attempted_at": {"$exists": True}}, sort=[("metadata.retraining_attempted_at", -1)]
        )

    @staticmethod
    def _aware(value: datetime) -> datetime:
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value
