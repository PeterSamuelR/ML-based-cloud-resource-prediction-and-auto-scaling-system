$ErrorActionPreference = "Stop"

docker compose up -d
if ($LASTEXITCODE -ne 0) { throw "Docker Compose failed to start." }

docker compose exec -T backend python -m src.services.prediction.cli train
if ($LASTEXITCODE -ne 0) { throw "Historical candidate training failed." }
