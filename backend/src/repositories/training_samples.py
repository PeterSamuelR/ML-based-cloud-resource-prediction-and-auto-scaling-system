from __future__ import annotations

from typing import Any

from pymongo import UpdateOne
from pymongo.collection import Collection


class TrainingSampleRepository:
    """Idempotent persisted feature/target rows derived from real metrics."""

    def __init__(self, collection: Collection):
        self.collection = collection

    def ensure_indexes(self) -> None:
        self.collection.create_index(
            [("timestamp", 1), ("horizon_seconds", 1), ("feature_definition_version", 1)],
            unique=True,
        )

    def upsert_many(self, samples: list[dict[str, Any]]) -> int:
        if not samples:
            return 0
        operations = [
            UpdateOne(
                {
                    "timestamp": item["timestamp"],
                    "horizon_seconds": item["horizon_seconds"],
                    "feature_definition_version": item["feature_definition_version"],
                },
                {"$set": item},
                upsert=True,
            )
            for item in samples
        ]
        result = self.collection.bulk_write(operations, ordered=False)
        return result.upserted_count + result.modified_count
