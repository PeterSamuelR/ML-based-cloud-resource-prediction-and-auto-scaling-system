from typing import Any

from pymongo.collection import Collection

from src.models.documents import MetricDocument


class MetricsRepository:
    def __init__(self, collection: Collection):
        self.collection = collection

    def ensure_indexes(self) -> None:
        self.collection.create_index([("timestamp", -1)])

    def insert(self, metric: MetricDocument) -> None:
        self.collection.insert_one(metric.model_dump())

    def latest(self) -> dict[str, Any] | None:
        return self.collection.find_one(sort=[("timestamp", -1)])

    def history(self, limit: int) -> list[dict[str, Any]]:
        return list(self.collection.find({}).sort("timestamp", -1).limit(limit))
