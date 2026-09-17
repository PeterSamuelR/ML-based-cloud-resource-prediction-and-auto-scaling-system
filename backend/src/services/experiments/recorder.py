from __future__ import annotations

import base64
import json
import sys
from typing import Any

from src.models.documents import ExperimentDocument
from src.repositories.database import create_document_repositories


def record(payload: dict[str, Any]) -> str:
    """Persist an observed experiment payload supplied by the host-side runner."""
    document = ExperimentDocument(**payload)
    return create_document_repositories()["experiments"].insert(document)


def main() -> None:
    encoded = sys.stdin.read() if len(sys.argv) == 2 and sys.argv[1] == "-" else sys.argv[1]
    payload = json.loads(base64.b64decode(encoded).decode("utf-8"))
    print(record(payload))


if __name__ == "__main__":
    main()
