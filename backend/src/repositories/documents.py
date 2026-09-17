from __future__ import annotations

from typing import Any

from pymongo.collection import Collection


class DocumentRepository:
    """Small common repository for append-only project records."""

    def __init__(self, collection: Collection, timestamp_field: str = "timestamp"):
        self.collection = collection
        self.timestamp_field = timestamp_field

    def ensure_indexes(self) -> None:
        self.collection.create_index([(self.timestamp_field, -1)])

    def insert(self, document: Any) -> str:
        value = document.model_dump() if hasattr(document, "model_dump") else document
        return str(self.collection.insert_one(value).inserted_id)

    def latest(self) -> dict[str, Any] | None:
        return self.collection.find_one(sort=[(self.timestamp_field, -1)])

    def history(self, limit: int = 100) -> list[dict[str, Any]]:
        return list(self.collection.find({}).sort(self.timestamp_field, -1).limit(limit))
