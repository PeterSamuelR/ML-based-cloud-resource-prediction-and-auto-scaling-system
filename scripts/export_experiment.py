"""Download one persisted experiment as JSON and CSV for report preparation."""

from __future__ import annotations

import argparse
from pathlib import Path
from urllib.request import urlopen


parser = argparse.ArgumentParser()
parser.add_argument("experiment_id")
parser.add_argument("--output-directory", default="results")
arguments = parser.parse_args()

directory = Path(arguments.output_directory)
directory.mkdir(parents=True, exist_ok=True)
for extension in ("json", "csv"):
    with urlopen(f"http://127.0.0.1:8001/api/experiments/{arguments.experiment_id}/export?format={extension}", timeout=15) as response:
        (directory / f"{arguments.experiment_id}.{extension}").write_bytes(response.read())
