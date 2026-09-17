from __future__ import annotations

import json
import time
from pathlib import Path


class NginxAccessLogReader:
    def __init__(self, path: str, interval_seconds: float):
        self.path = Path(path)
        self.interval_seconds = interval_seconds
        self.position = 0
        self.last_read = time.monotonic()

    def read_window(self) -> dict[str, float | None]:
        now = time.monotonic()
        elapsed = max(now - self.last_read, 0.001)
        self.last_read = now
        if not self.path.exists():
            return {"request_rate_per_second": 0.0, "response_time_ms": None}
        if self.path.stat().st_size < self.position:
            self.position = 0
        with self.path.open("r", encoding="utf-8") as log_file:
            log_file.seek(self.position)
            lines = log_file.readlines()
            self.position = log_file.tell()
        entries = []
        for line in lines:
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        durations = [float(entry["request_time"]) * 1_000 for entry in entries if entry.get("request_time") not in (None, "-")]
        return {
            "request_rate_per_second": round(len(entries) / elapsed, 3),
            "response_time_ms": round(sum(durations) / len(durations), 3) if durations else None,
        }
