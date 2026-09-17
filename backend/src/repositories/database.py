import os

from pymongo import MongoClient

from src.repositories.documents import DocumentRepository
from src.repositories.metrics import MetricsRepository


def create_metrics_repository() -> MetricsRepository:
    client = MongoClient(os.getenv("MONGODB_URI", "mongodb://mongodb:27017"), serverSelectionTimeoutMS=3_000)
    database = client[os.getenv("MONGODB_DATABASE", "cloud_autoscaling")]
    return MetricsRepository(database["metrics"])


def create_document_repositories() -> dict[str, DocumentRepository]:
    client = MongoClient(os.getenv("MONGODB_URI", "mongodb://mongodb:27017"), serverSelectionTimeoutMS=3_000)
    database = client[os.getenv("MONGODB_DATABASE", "cloud_autoscaling")]
    return {
        "predictions": DocumentRepository(database["predictions"]),
        "scaling_events": DocumentRepository(database["scaling_events"]),
        "model_versions": DocumentRepository(database["model_versions"], timestamp_field="created_at"),
        "experiments": DocumentRepository(database["experiments"], timestamp_field="started_at"),
    }
