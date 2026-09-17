import os

from pymongo import MongoClient

from src.repositories.metrics import MetricsRepository


def create_metrics_repository() -> MetricsRepository:
    client = MongoClient(os.getenv("MONGODB_URI", "mongodb://mongodb:27017"), serverSelectionTimeoutMS=3_000)
    database = client[os.getenv("MONGODB_DATABASE", "cloud_autoscaling")]
    return MetricsRepository(database["metrics"])
