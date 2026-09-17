from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import joblib
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error

from src.models.documents import ModelVersionDocument, PredictionDocument
from src.services.prediction.dataset import FEATURE_COLUMNS, FEATURE_DEFINITION_VERSION, build_future_cpu_dataset


class RandomForestPredictionService:
    def __init__(self, metrics_repository, model_repository, config: dict[str, Any], models_directory: str = "/models"):
        self.metrics_repository = metrics_repository
        self.model_repository = model_repository
        self.config = config
        self.models_directory = Path(models_directory)
        self.model = None
        self.version: str | None = None

    def train_if_needed(self) -> dict[str, Any] | None:
        if self.model is None:
            self._load_active_model()
        if self.model is not None:
            return None
        metrics = list(reversed(self.metrics_repository.history(10_000)))
        prediction = self.config["prediction"]
        dataset = build_future_cpu_dataset(metrics, self.config["monitoring"]["interval_seconds"], prediction["horizon_seconds"])
        minimum = prediction["minimum_training_samples"]
        if len(dataset.features) < minimum:
            return None
        split = max(1, int(len(dataset.features) * prediction["training_fraction"]))
        if split >= len(dataset.features):
            split = len(dataset.features) - 1
        train_x, validation_x = dataset.features.iloc[:split], dataset.features.iloc[split:]
        train_y, validation_y = dataset.targets.iloc[:split], dataset.targets.iloc[split:]
        model, mae, rmse = self._fit_and_evaluate(train_x, train_y, validation_x, validation_y)
        version = f"rf-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:8]}"
        self.models_directory.mkdir(parents=True, exist_ok=True)
        artifact = self.models_directory / f"{version}.joblib"
        joblib.dump({"model": model, "feature_columns": FEATURE_COLUMNS, "version": version}, artifact)
        record = ModelVersionDocument(
            version=version, created_at=datetime.now(timezone.utc), status="active",
            metadata={"artifact": str(artifact), "model": "RandomForestRegressor", "training_samples": len(train_x), "validation_samples": len(validation_x), "mae": mae, "rmse": rmse, "horizon_seconds": prediction["horizon_seconds"], "feature_columns": FEATURE_COLUMNS, "feature_definition_version": FEATURE_DEFINITION_VERSION},
        )
        self.model_repository.insert(record)
        self.model, self.version = model, version
        return record.model_dump()

    def retrain_recent(self, retraining_reason: dict[str, Any]) -> dict[str, Any]:
        """Train and validate a recent-data candidate without replacing a model prematurely."""
        if self.model is None:
            self._load_active_model()
        if self.model is None or self.version is None:
            return {"outcome": "not_ready", "reason": "No active model is available for candidate validation."}

        prediction = self.config["prediction"]
        adaptive = self.config["adaptive"]
        metrics = list(reversed(self.metrics_repository.history(10_000)))
        dataset = build_future_cpu_dataset(metrics, self.config["monitoring"]["interval_seconds"], prediction["horizon_seconds"])
        recent = dataset.features.tail(adaptive["minimum_recent_training_samples"])
        recent_targets = dataset.targets.tail(adaptive["minimum_recent_training_samples"])
        recent_timestamps = dataset.timestamps.tail(adaptive["minimum_recent_training_samples"])
        minimum = adaptive["minimum_recent_training_samples"]
        if len(recent) < minimum:
            return {"outcome": "insufficient_samples", "valid_samples": len(recent), "minimum_required": minimum}

        split = max(1, int(len(recent) * prediction["training_fraction"]))
        if split >= len(recent):
            split = len(recent) - 1
        train_x, validation_x = recent.iloc[:split], recent.iloc[split:]
        train_y, validation_y = recent_targets.iloc[:split], recent_targets.iloc[split:]
        candidate, candidate_mae, candidate_rmse = self._fit_and_evaluate(train_x, train_y, validation_x, validation_y)
        baseline_estimates = self.model.predict(validation_x)
        baseline_mae = float(mean_absolute_error(validation_y, baseline_estimates))
        baseline_rmse = float(mean_squared_error(validation_y, baseline_estimates) ** 0.5)
        passed = bool(candidate_mae <= baseline_mae)

        now = datetime.now(timezone.utc)
        version = f"rf-{now.strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:8]}"
        self.models_directory.mkdir(parents=True, exist_ok=True)
        artifact = self.models_directory / f"{version}.joblib"
        joblib.dump({"model": candidate, "feature_columns": FEATURE_COLUMNS, "version": version}, artifact)
        validation = {
            "required": bool(adaptive["candidate_validation_required"]),
            "passed": passed,
            "candidate": {"mae": candidate_mae, "rmse": candidate_rmse},
            "active_baseline": {"version": self.version, "mae": baseline_mae, "rmse": baseline_rmse},
            "criterion": "candidate_mae_not_greater_than_active_mae_on_same_chronological_holdout",
        }
        metadata = {
            "artifact": str(artifact), "model": "RandomForestRegressor", "horizon_seconds": prediction["horizon_seconds"],
            "feature_columns": FEATURE_COLUMNS, "feature_definition_version": FEATURE_DEFINITION_VERSION,
            "training_samples": len(train_x), "validation_samples": len(validation_x), "training_window": {
                "start_timestamp": recent_timestamps.iloc[0].to_pydatetime(),
                "end_timestamp": recent_timestamps.iloc[-1].to_pydatetime(),
                "valid_samples": len(recent),
            },
            "validation": validation, "retraining_reason": retraining_reason,
            "retraining_attempted_at": now,
            "activation_status": "candidate",
        }
        record = ModelVersionDocument(version=version, created_at=now, status="candidate", metadata=metadata)
        self.model_repository.insert(record)
        if not passed:
            self.model_repository.collection.update_one(
                {"version": version}, {"$set": {"status": "rejected", "metadata.activation_status": "rejected"}}
            )
            return {"outcome": "rejected", "version": version, "validation": validation}

        previous_version = self.version
        self.model_repository.collection.update_one(
            {"version": previous_version, "status": "active"},
            {"$set": {"status": "superseded", "metadata.superseded_at": now, "metadata.superseded_by": version}},
        )
        self.model_repository.collection.update_one(
            {"version": version}, {"$set": {"status": "active", "metadata.activation_status": "active", "metadata.activated_at": now}},
        )
        self.model, self.version = candidate, version
        return {"outcome": "activated", "version": version, "previous_version": previous_version, "validation": validation}

    def _fit_and_evaluate(self, train_x, train_y, validation_x, validation_y):
        prediction = self.config["prediction"]
        model = RandomForestRegressor(
            n_estimators=prediction["random_forest_estimators"], random_state=prediction["random_seed"], n_jobs=1
        )
        model.fit(train_x, train_y)
        estimates = model.predict(validation_x)
        return model, float(mean_absolute_error(validation_y, estimates)), float(mean_squared_error(validation_y, estimates) ** 0.5)

    def _load_active_model(self) -> None:
        record = self.model_repository.collection.find_one({"status": "active"}, sort=[("created_at", -1)])
        if record is None:
            return
        artifact = Path(record.get("metadata", {}).get("artifact", ""))
        if not artifact.exists():
            return
        loaded = joblib.load(artifact)
        self.model, self.version = loaded["model"], loaded["version"]

    def predict(self, metric: dict[str, Any]) -> PredictionDocument | None:
        if self.model is None or self.version is None or metric.get("aggregate_cpu_percent") is None:
            return None
        values = pd.DataFrame([[metric.get(column, 0.0) or 0.0 for column in FEATURE_COLUMNS]], columns=FEATURE_COLUMNS)
        predicted = max(0.0, float(self.model.predict(values)[0]))
        timestamp = metric["timestamp"]
        return PredictionDocument(
            timestamp=timestamp,
            target_timestamp=timestamp + timedelta(seconds=self.config["prediction"]["horizon_seconds"]),
            predicted_aggregate_cpu_percent=round(predicted, 3), model_version=self.version,
        )
