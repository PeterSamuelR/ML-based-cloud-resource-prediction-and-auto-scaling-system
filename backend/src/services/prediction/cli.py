from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone

from src.core.config import load_config
from src.repositories.database import create_document_repositories, create_metrics_repository
from src.services.prediction.dataset import (
    FEATURE_COLUMNS,
    FEATURE_DEFINITION_VERSION,
    build_future_cpu_dataset,
)
from src.services.prediction.trainer import (
    RandomForestPredictionService,
)


def materialize(config, metrics_repository, sample_repository) -> dict:
    limit = int(config["prediction"].get("training_history_limit", 100_000))
    metrics = list(reversed(metrics_repository.history(limit)))
    dataset = build_future_cpu_dataset(
        metrics,
        int(config["monitoring"]["interval_seconds"]),
        int(config["prediction"]["horizon_seconds"]),
    )
    materialized_at = datetime.now(timezone.utc)
    rows = []
    for index in range(len(dataset.features)):
        rows.append({
            "timestamp": dataset.timestamps.iloc[index].to_pydatetime(),
            "target_timestamp": dataset.target_timestamps.iloc[index].to_pydatetime(),
            "target_cpu_30s": float(dataset.targets.iloc[index]),
            "horizon_seconds": int(config["prediction"]["horizon_seconds"]),
            "feature_definition_version": FEATURE_DEFINITION_VERSION,
            "features": {
                column: float(dataset.features.iloc[index][column])
                for column in FEATURE_COLUMNS
            },
            "materialized_at": materialized_at,
        })
    changed = sample_repository.upsert_many(rows)
    return {
        "raw_metrics_read": len(metrics),
        "valid_labeled_samples": len(rows),
        "upserts": changed,
        "materialized_at": materialized_at.isoformat(),
    }


def train(config, metrics_repository, document_repositories) -> dict:
    service = RandomForestPredictionService(
        metrics_repository, document_repositories["model_versions"], config
    )
    service._load_active_model()
    if service.model is None:
        record = service.train_if_needed()
        return {"outcome": "initial_training", "record": record}
    previous_version = service.version
    service.train_if_needed()
    return {
        "outcome": "refresh_checked",
        "previous_version": previous_version,
        "active_version": service.version,
        "candidate_changed_active_model": service.version != previous_version,
        "note": "Existing freshness, cooldown, recent-data, and chronological candidate-validation gates were preserved.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Materialize and train from observed project metrics.")
    parser.add_argument("command", choices=("materialize", "train"))
    args = parser.parse_args()
    config = load_config()
    metrics_repository = create_metrics_repository()
    repositories = create_document_repositories()
    if args.command == "materialize":
        result = materialize(config, metrics_repository, repositories["training_samples"])
    else:
        result = train(config, metrics_repository, repositories)
    print(json.dumps(result, default=str, indent=2))


if __name__ == "__main__":
    main()
