from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from bisect import bisect_left
from typing import Any

import pandas as pd

LEGACY_FEATURE_COLUMNS = [
    "aggregate_cpu_percent",
    "aggregate_memory_percent",
    "request_rate_per_second",
    "response_time_ms",
    "active_healthy_replica_count",
]
TEMPORAL_FEATURE_COLUMNS = [
    "cpu_previous_sample_percent",
    "cpu_three_samples_ago_percent",
    "cpu_six_samples_ago_percent",
    "cpu_delta_previous_sample_percent",
    "cpu_trend_per_second",
    "request_rate_previous_sample",
    "request_rate_three_samples_ago",
    "request_rate_delta_previous_sample",
    "request_rate_trend_per_second",
    "previous_sample_interval_seconds",
    "six_sample_interval_seconds",
]
FEATURE_COLUMNS = LEGACY_FEATURE_COLUMNS + TEMPORAL_FEATURE_COLUMNS
FEATURE_DEFINITION_VERSION = "aggregate_cpu_features_v2_temporal"


@dataclass
class Dataset:
    features: pd.DataFrame
    targets: pd.Series
    timestamps: pd.Series
    target_timestamps: pd.Series


def build_future_cpu_dataset(
    metrics: list[dict[str, Any]], interval_seconds: int = 5, horizon_seconds: int = 30
) -> Dataset:
    """Build leakage-safe feature rows at t and observed CPU targets at t+horizon."""
    frame = _prepare_frame(metrics)
    if frame.empty:
        return _empty_dataset()

    maximum_lateness = timedelta(seconds=interval_seconds)
    rows: list[dict[str, Any]] = []
    timestamps = frame["timestamp"].tolist()
    for index in range(6, len(frame)):
        current = frame.iloc[index]
        expected_target_time = current["timestamp"] + timedelta(seconds=horizon_seconds)
        target_index = bisect_left(timestamps, expected_target_time, index + 1)
        if target_index >= len(frame):
            continue
        future = frame.iloc[target_index]
        if future["timestamp"] - expected_target_time > maximum_lateness:
            continue
        feature_row = _features_at(frame, index)
        feature_row["target"] = _number(future.get("aggregate_cpu_percent"))
        feature_row["timestamp"] = current["timestamp"]
        feature_row["target_timestamp"] = future["timestamp"]
        rows.append(feature_row)

    if not rows:
        return _empty_dataset()
    samples = pd.DataFrame(rows)
    return Dataset(
        samples[FEATURE_COLUMNS], samples["target"], samples["timestamp"], samples["target_timestamp"]
    )


def build_live_feature_vector(metrics: list[dict[str, Any]]) -> pd.DataFrame | None:
    """Build the current vector from the latest metric and earlier observations only."""
    frame = _prepare_frame(metrics)
    if len(frame) < 7:
        return None
    return pd.DataFrame([_features_at(frame, len(frame) - 1)], columns=FEATURE_COLUMNS)


def _prepare_frame(metrics: list[dict[str, Any]]) -> pd.DataFrame:
    frame = pd.DataFrame(metrics)
    if frame.empty:
        return frame
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
    return (
        frame.sort_values("timestamp")
        .drop_duplicates(subset=["timestamp"], keep="last")
        .dropna(subset=["aggregate_cpu_percent", "aggregate_memory_percent"])
        .reset_index(drop=True)
    )


def _features_at(frame: pd.DataFrame, index: int) -> dict[str, float]:
    current = frame.iloc[index]
    previous = frame.iloc[index - 1]
    three_ago = frame.iloc[index - 3]
    six_ago = frame.iloc[index - 6]
    interval_1 = max((current["timestamp"] - previous["timestamp"]).total_seconds(), 1.0)
    interval_3 = max((current["timestamp"] - three_ago["timestamp"]).total_seconds(), 1.0)
    interval_6 = max((current["timestamp"] - six_ago["timestamp"]).total_seconds(), 1.0)
    cpu = _number(current.get("aggregate_cpu_percent"))
    cpu_previous = _number(previous.get("aggregate_cpu_percent"))
    cpu_three = _number(three_ago.get("aggregate_cpu_percent"))
    cpu_six = _number(six_ago.get("aggregate_cpu_percent"))
    requests = _number(current.get("request_rate_per_second"))
    requests_previous = _number(previous.get("request_rate_per_second"))
    requests_three = _number(three_ago.get("request_rate_per_second"))
    return {
        "aggregate_cpu_percent": cpu,
        "aggregate_memory_percent": _number(current.get("aggregate_memory_percent")),
        "request_rate_per_second": requests,
        "response_time_ms": _number(current.get("response_time_ms")),
        "active_healthy_replica_count": _number(current.get("active_healthy_replica_count")),
        "cpu_previous_sample_percent": cpu_previous,
        "cpu_three_samples_ago_percent": cpu_three,
        "cpu_six_samples_ago_percent": cpu_six,
        "cpu_delta_previous_sample_percent": cpu - cpu_previous,
        "cpu_trend_per_second": (cpu - cpu_six) / interval_6,
        "request_rate_previous_sample": requests_previous,
        "request_rate_three_samples_ago": requests_three,
        "request_rate_delta_previous_sample": requests - requests_previous,
        "request_rate_trend_per_second": (requests - requests_three) / interval_3,
        "previous_sample_interval_seconds": interval_1,
        "six_sample_interval_seconds": interval_6,
    }


def _number(value: Any, default: float = 0.0) -> float:
    if value is None or pd.isna(value):
        return default
    return float(value)


def _empty_dataset() -> Dataset:
    empty_time = pd.Series(dtype="datetime64[ns, UTC]")
    return Dataset(pd.DataFrame(columns=FEATURE_COLUMNS), pd.Series(dtype=float), empty_time, empty_time.copy())
