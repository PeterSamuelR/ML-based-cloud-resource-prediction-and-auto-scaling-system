param(
    [ValidateSet("stable", "gradual_increase", "sudden_spike", "sudden_drop", "periodic", "changing_workload")]
    [string]$Scenario = "changing_workload",
    [string]$Duration = "15m",
    [ValidateRange(1, 200)]
    [int]$Users = 20,
    [ValidateRange(1, 50)]
    [int]$SpawnRate = 5,
    [ValidateRange(1, 500)]
    [int]$WorkDurationMs = 50,
    [ValidateRange(1, 100)]
    [int]$WorkIntensity = 10,
    [ValidateRange(1, 3600)]
    [int]$PhaseSeconds = 60
)

$ErrorActionPreference = "Stop"

docker compose up -d
if ($LASTEXITCODE -ne 0) { throw "Docker Compose failed to start." }

$env:LOCUST_WORKLOAD_SCENARIO = $Scenario
$env:LOCUST_WORK_DURATION_MS = "$WorkDurationMs"
$env:LOCUST_WORK_INTENSITY = "$WorkIntensity"
$env:LOCUST_PHASE_SECONDS = "$PhaseSeconds"

locust -f load-tests/locustfile.py --headless --host http://localhost:8080 `
    --users $Users --spawn-rate $SpawnRate --run-time $Duration --only-summary
if ($LASTEXITCODE -ne 0) { throw "Locust failed; metric collection remains persisted for inspection." }

docker compose exec -T backend python -m src.services.prediction.cli materialize
if ($LASTEXITCODE -ne 0) { throw "Historical target materialization failed." }
