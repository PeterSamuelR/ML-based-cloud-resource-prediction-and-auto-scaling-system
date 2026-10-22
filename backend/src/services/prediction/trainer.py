from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
import time

import joblib
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.model_selection import TimeSeriesSplit

from src.models.documents import ModelVersionDocument, PredictionDocument
from src.services.prediction.dataset import (
    FEATURE_COLUMNS,
    FEATURE_DEFINITION_VERSION,
    LEGACY_FEATURE_COLUMNS,
    build_future_cpu_dataset,
    build_live_feature_vector,
)


class RandomForestPredictionService:
    def __init__(self, metrics_repository, model_repository, config: dict[str, Any], models_directory: str = "/models"):
        self.metrics_repository = metrics_repository
        self.model_repository = model_repository
        self.config = config
        self.models_directory = Path(models_directory)
        self.model = None
        self.version: str | None = None
        self.feature_columns: list[str] | None = None
        self.training_window_end: datetime | None = None
        self._last_refresh_check = 0.0

    def train_if_needed(self) -> dict[str, Any] | None:
        if self.model is None:
            self._load_active_model()
        if self.model is not None:
            if self.config.get("selected_policy") != "adaptive_predictive":
                self._refresh_stale_model_if_due()
            return None
        prediction = self.config["prediction"]
        history_limit = prediction.get("training_history_limit", 100_000)
        metrics = list(reversed(self.metrics_repository.history(history_limit)))
        window_size = prediction.get("recent_training_samples", prediction["minimum_training_samples"])
        recent_dataset = _build_recent_dataset(metrics, self.config, window_size, datetime.now(timezone.utc))
        minimum = prediction["minimum_training_samples"]
        if len(recent_dataset.features) < minimum:
            return None
        dataset = build_future_cpu_dataset(
            metrics,
            int(self.config["monitoring"]["interval_seconds"]),
            int(prediction["horizon_seconds"]),
        )
        if len(dataset.features) < minimum:
            return None
        train_x, train_y, validation_x, validation_y, split_info = _chronological_split(
            dataset, prediction["training_fraction"]
        )
        if train_x.empty or validation_x.empty:
            return None
        train_target_times = dataset.target_timestamps.loc[train_x.index]
        train_times = dataset.timestamps.loc[train_x.index]
        model, mae, rmse, tuning = self._fit_and_evaluate(
            train_x, train_y, validation_x, validation_y, train_times, train_target_times
        )
        version = f"rf-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:8]}"
        self.models_directory.mkdir(parents=True, exist_ok=True)
        artifact = self.models_directory / f"{version}.joblib"
        joblib.dump({"model": model, "feature_columns": FEATURE_COLUMNS, "version": version}, artifact)
        now = datetime.now(timezone.utc)
        record = ModelVersionDocument(
            version=version, created_at=now, status="active",
            metadata={"artifact": str(artifact), "model": "RandomForestRegressor", "training_samples": len(train_x), "validation_samples": len(validation_x), "purged_training_samples": split_info["purged_training_samples"], "max_training_target_timestamp": split_info["max_training_target_timestamp"], "validation_start_timestamp": split_info["validation_start_timestamp"], "training_window": {"start_timestamp": dataset.timestamps.iloc[0].to_pydatetime(), "end_timestamp": dataset.timestamps.iloc[-1].to_pydatetime(), "valid_samples": len(dataset.features), "recent_valid_samples": len(recent_dataset.features)}, "mae": mae, "rmse": rmse, "tuning": tuning, "horizon_seconds": prediction["horizon_seconds"], "feature_columns": FEATURE_COLUMNS, "feature_definition_version": FEATURE_DEFINITION_VERSION},
        )
        self.model_repository.insert(record)
        self.model, self.version, self.feature_columns = model, version, FEATURE_COLUMNS
        self.training_window_end = dataset.timestamps.iloc[-1].to_pydatetime()
        return record.model_dump()

    def refresh_active_model_if_changed(self) -> bool:
        """Pick up versions activated by another process, such as the CLI."""
        previous_version = self.version
        self._load_active_model()
        return self.version != previous_version

    def _refresh_stale_model_if_due(self) -> None:
        """Refresh old non-adaptive models with recent data and the same candidate gate."""
        if self.config.get("selected_policy") == "adaptive_predictive":
            return
        prediction = self.config["prediction"]
        refresh_interval = prediction.get("refresh_interval_seconds", 300)
        if self.training_window_end is None:
            return
        now = datetime.now(timezone.utc)
        if (now - _as_utc(self.training_window_end)).total_seconds() < refresh_interval:
            return
        monotonic_now = time.monotonic()
        retry_interval = self.config["adaptive"].get("retraining_cooldown_seconds", 1800)
        if self._last_refresh_check and monotonic_now - self._last_refresh_check < refresh_interval:
            return
        self._last_refresh_check = monotonic_now
        latest_attempt = self.model_repository.collection.find_one(
            {"metadata.retraining_attempted_at": {"$exists": True}},
            sort=[("metadata.retraining_attempted_at", -1)],
        )
        if latest_attempt:
            attempted_at = _as_utc(latest_attempt["metadata"]["retraining_attempted_at"])
            if (now - attempted_at).total_seconds() < retry_interval:
                return
        self.retrain_recent({
            "trigger": "stale_model_refresh",
            "model_training_window_end": self.training_window_end,
            "model_age_seconds": round((now - _as_utc(self.training_window_end)).total_seconds(), 3),
        })

    def retrain_recent(self, retraining_reason: dict[str, Any], now: datetime | None = None) -> dict[str, Any]:
        """Train and validate a recent-data candidate without replacing a model prematurely."""
        if self.model is None:
            self._load_active_model()
        if self.model is None or self.version is None:
            return {"outcome": "not_ready", "reason": "No active model is available for candidate validation."}

        prediction = self.config["prediction"]
        adaptive = self.config["adaptive"]
        window_size = max(prediction.get("recent_training_samples", 0), adaptive["minimum_recent_training_samples"])
        # Use broad project history for the candidate, but gate retraining on
        # enough fresh recent rows. This method is called outside the sampling
        # path so the larger history read/training cannot stall monitoring.
        history_limit = prediction.get("training_history_limit", 100_000)
        metrics = list(reversed(self.metrics_repository.history(history_limit)))
        now = now or datetime.now(timezone.utc)
        recent_metrics = metrics[-max(window_size * 2, window_size + 20):]
        recent_dataset = _build_recent_dataset(recent_metrics, self.config, window_size, now)
        minimum = adaptive["minimum_recent_training_samples"]
        if len(recent_dataset.features) < minimum:
            return {"outcome": "insufficient_samples", "valid_samples": len(recent_dataset.features), "minimum_required": minimum}

        dataset = build_future_cpu_dataset(
            metrics,
            int(self.config["monitoring"]["interval_seconds"]),
            int(prediction["horizon_seconds"]),
        )
        if len(dataset.features) < minimum:
            return {"outcome": "insufficient_historical_samples", "valid_samples": len(dataset.features), "minimum_required": minimum}

        train_x, train_y, validation_x, validation_y, split_info = _chronological_split(
            dataset, prediction["training_fraction"]
        )
        if train_x.empty or validation_x.empty:
            return {"outcome": "insufficient_temporal_holdout", "valid_samples": len(dataset.features), "purged_training_samples": split_info["purged_training_samples"]}
        train_target_times = dataset.target_timestamps.loc[train_x.index]
        train_times = dataset.timestamps.loc[train_x.index]
        candidate, candidate_mae, candidate_rmse, tuning = self._fit_and_evaluate(
            train_x, train_y, validation_x, validation_y, train_times, train_target_times
        )
        active_features = self.feature_columns or LEGACY_FEATURE_COLUMNS
        baseline_estimates = self.model.predict(validation_x[active_features])
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
            "tuning": tuning,
        }
        metadata = {
            "artifact": str(artifact), "model": "RandomForestRegressor", "horizon_seconds": prediction["horizon_seconds"],
            "feature_columns": FEATURE_COLUMNS, "feature_definition_version": FEATURE_DEFINITION_VERSION,
            "training_samples": len(train_x), "validation_samples": len(validation_x), "training_window": {
                "start_timestamp": dataset.timestamps.iloc[0].to_pydatetime(),
                "end_timestamp": dataset.timestamps.iloc[-1].to_pydatetime(),
                "valid_samples": len(dataset.features),
                "recent_valid_samples": len(recent_dataset.features),
            },
            "purged_training_samples": split_info["purged_training_samples"],
            "max_training_target_timestamp": split_info["max_training_target_timestamp"],
            "validation_start_timestamp": split_info["validation_start_timestamp"],
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
        self.feature_columns = FEATURE_COLUMNS
        self.training_window_end = dataset.timestamps.iloc[-1].to_pydatetime()
        return {"outcome": "activated", "version": version, "previous_version": previous_version, "validation": validation}

    def _fit_and_evaluate(self, train_x, train_y, validation_x, validation_y, train_times=None, train_target_times=None):
        prediction = self.config["prediction"]
        parameters, tuning = _tune_forest(
            train_x, train_y, train_times, train_target_times, prediction
        )
        model = RandomForestRegressor(**parameters, random_state=prediction["random_seed"], n_jobs=1)
        model.fit(train_x, train_y)
        estimates = model.predict(validation_x)
        return model, float(mean_absolute_error(validation_y, estimates)), float(mean_squared_error(validation_y, estimates) ** 0.5), tuning

    def _load_active_model(self) -> None:
        record = self.model_repository.collection.find_one({"status": "active"}, sort=[("created_at", -1)])
        if record is None:
            return
        if self.model is not None and record.get("version") == self.version:
            return
        artifact = Path(record.get("metadata", {}).get("artifact", ""))
        if not artifact.exists():
            return
        loaded = joblib.load(artifact)
        self.model, self.version = loaded["model"], loaded["version"]
        self.feature_columns = loaded.get("feature_columns") or record.get("metadata", {}).get("feature_columns") or LEGACY_FEATURE_COLUMNS
        training_window = record.get("metadata", {}).get("training_window", {})
        self.training_window_end = _as_utc(training_window.get("end_timestamp") or record.get("created_at"))

    def predict(self, metric: dict[str, Any]) -> PredictionDocument | None:
        if self.model is None or self.version is None or metric.get("aggregate_cpu_percent") is None:
            return None
        history = list(reversed(self.metrics_repository.history(8)))
        history.append(metric)
        values = build_live_feature_vector(history)
        if values is None:
            return None
        model_features = self.feature_columns or LEGACY_FEATURE_COLUMNS
        predicted = max(0.0, float(self.model.predict(values[model_features])[0]))
        timestamp = metric["timestamp"]
        return PredictionDocument(
            timestamp=timestamp,
            target_timestamp=timestamp + timedelta(seconds=self.config["prediction"]["horizon_seconds"]),
            predicted_aggregate_cpu_percent=round(predicted, 3), model_version=self.version,
        )


def _chronological_split(dataset, training_fraction: float):
    """Split by feature time and purge train labels reaching into validation time."""
    sample_count = len(dataset.features)
    if sample_count < 2:
        empty_x = dataset.features.iloc[:0]
        empty_y = dataset.targets.iloc[:0]
        return empty_x, empty_y, empty_x, empty_y, {
            "purged_training_samples": 0,
            "max_training_target_timestamp": None,
            "validation_start_timestamp": None,
        }
    split = max(1, int(sample_count * training_fraction))
    if split >= sample_count:
        split = sample_count - 1
    validation_x = dataset.features.iloc[split:]
    validation_y = dataset.targets.iloc[split:]
    validation_start = dataset.timestamps.iloc[split]
    eligible_train = dataset.target_timestamps.iloc[:split] < validation_start
    train_x = dataset.features.iloc[:split].loc[eligible_train]
    train_y = dataset.targets.iloc[:split].loc[eligible_train]
    info = {
        "purged_training_samples": int(split - eligible_train.sum()),
        "max_training_target_timestamp": dataset.target_timestamps.iloc[:split].loc[eligible_train].max().to_pydatetime() if eligible_train.any() else None,
        "validation_start_timestamp": validation_start.to_pydatetime(),
    }
    return train_x, train_y, validation_x, validation_y, info


def _tail_dataset(dataset, limit: int):
    if len(dataset.features) <= limit:
        return dataset
    return type(dataset)(
        dataset.features.tail(limit),
        dataset.targets.tail(limit),
        dataset.timestamps.tail(limit),
        dataset.target_timestamps.tail(limit),
    )


def _build_recent_dataset(metrics, config, sample_count: int, now: datetime):
    """Build labels only from a bounded recent window with a fresh latest observation."""
    prediction = config["prediction"]
    interval = float(config["monitoring"]["interval_seconds"])
    horizon = float(prediction["horizon_seconds"])
    lateness = float(prediction.get("max_feedback_lateness_seconds", interval))
    now = _as_utc(now)
    if not metrics:
        return build_future_cpu_dataset([], int(interval), int(horizon))

    newest = max(_as_utc(item["timestamp"]) for item in metrics)
    if (now - newest).total_seconds() > horizon + lateness:
        return build_future_cpu_dataset([], int(interval), int(horizon))

    # Reserve samples for temporal lags, the 30-second target, and the first
    # observation after target time. Old rows outside this window cannot make a
    # stale model appear to have enough recent training data.
    window_seconds = sample_count * interval + horizon + 6 * interval + lateness
    cutoff = now - timedelta(seconds=window_seconds)
    recent_metrics = [
        item for item in metrics
        if cutoff <= _as_utc(item["timestamp"]) <= now
    ]
    return build_future_cpu_dataset(recent_metrics, int(interval), int(horizon))


def _tune_forest(train_x, train_y, train_times, train_target_times, prediction_config):
    tuning_config = prediction_config.get("random_forest_tuning", {})
    candidate_estimators = tuning_config.get("n_estimators", [prediction_config["random_forest_estimators"]])
    candidate_depths = tuning_config.get("max_depth", [None])
    candidate_leaves = tuning_config.get("min_samples_leaf", [1])
    fallback = {
        "n_estimators": prediction_config["random_forest_estimators"],
        "max_depth": None,
        "min_samples_leaf": 1,
    }
    if train_times is None or train_target_times is None or len(train_x) < 30:
        return fallback, {"method": "configured_default_insufficient_cv_data", "parameters": fallback}

    folds = []
    splitter = TimeSeriesSplit(n_splits=min(tuning_config.get("cv_splits", 3), max(2, len(train_x) // 15)))
    for fold_train, fold_validation in splitter.split(train_x):
        validation_start = train_times.iloc[fold_validation[0]]
        fold_train_times = train_target_times.iloc[fold_train]
        eligible = fold_train_times < validation_start
        if int(eligible.sum()) < 12:
            continue
        folds.append((fold_train[eligible.to_numpy()], fold_validation))
    if not folds:
        return fallback, {"method": "configured_default_no_purged_cv_folds", "parameters": fallback}

    best_parameters = fallback
    best_score = float("inf")
    best_fold_count = 0
    for estimator_count in candidate_estimators:
        for depth in candidate_depths:
            for leaf_size in candidate_leaves:
                parameters = {
                    "n_estimators": int(estimator_count),
                    "max_depth": depth,
                    "min_samples_leaf": int(leaf_size),
                }
                fold_scores = []
                for fold_train, fold_validation in folds:
                    model = RandomForestRegressor(
                        **parameters, random_state=prediction_config["random_seed"], n_jobs=1
                    )
                    model.fit(train_x.iloc[fold_train], train_y.iloc[fold_train])
                    estimate = model.predict(train_x.iloc[fold_validation])
                    fold_scores.append(mean_absolute_error(train_y.iloc[fold_validation], estimate))
                score = float(sum(fold_scores) / len(fold_scores))
                if score < best_score:
                    best_parameters, best_score, best_fold_count = parameters, score, len(fold_scores)
    return best_parameters, {
        "method": "purged_expanding_window_time_series_cv_mae",
        "cv_mae": best_score,
        "cv_folds": best_fold_count,
        "parameters": best_parameters,
    }


def _as_utc(value: datetime | str | None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00")) if isinstance(value, str) else value
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed
