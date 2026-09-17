from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Any

import pandas as pd

FEATURE_COLUMNS = [
    "aggregate_cpu_percent",
    "aggregate_memory_percent",
    "request_rate_per_second",
    "response_time_ms",
    "active_healthy_replica_count",
]


@dataclass
class Dataset:
    features: pd.DataFrame
    targets: pd.Series
    timestamps: pd.Series


def build_future_cpu_dataset(metrics: list[dict[str, Any]], interval_seconds: int = 5, horizon_seconds: int = 30) -> Dataset:
    """Build samples at t with targets observed at t + horizon, never future features."""
    frame = pd.DataFrame(metrics)
    if frame.empty:
        return Dataset(pd.DataFrame(columns=FEATURE_COLUMNS), pd.Series(dtype=float), pd.Series(dtype="datetime64[ns, UTC]"))
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
    frame = frame.sort_values("timestamp").reset_index(drop=True)
    frame = frame.dropna(subset=["aggregate_cpu_percent", "aggregate_memory_percent"])
    steps = horizon_seconds // interval_seconds
    tolerance = timedelta(seconds=interval_seconds / 2)
    rows: list[dict[str, Any]] = []
    for index in range(len(frame) - steps):
        current, future = frame.iloc[index], frame.iloc[index + steps]
        expected_target_time = current["timestamp"] + timedelta(seconds=horizon_seconds)
        if abs(future["timestamp"] - expected_target_time) > tolerance:
            continue
        row = {column: current.get(column, 0.0) or 0.0 for column in FEATURE_COLUMNS}
        row["target"] = future["aggregate_cpu_percent"]
        row["timestamp"] = current["timestamp"]
        rows.append(row)
    samples = pd.DataFrame(rows)
    if samples.empty:
        return Dataset(pd.DataFrame(columns=FEATURE_COLUMNS), pd.Series(dtype=float), pd.Series(dtype="datetime64[ns, UTC]"))
    return Dataset(samples[FEATURE_COLUMNS], samples["target"], samples["timestamp"])
