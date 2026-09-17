# Machine Learning-Based Cloud Resource Prediction and Auto-Scaling System

This final-year project implements and experimentally evaluates an **error-aware adaptive predictive autoscaling framework** in a reproducible Docker-based environment. It compares three policies under equivalent experimental conditions:

1. Reactive autoscaling
2. Predictive autoscaling
3. Adaptive predictive autoscaling

The contribution is the implementation and evaluation of the error-aware adaptive loop, not the invention of predictive or adaptive autoscaling.

## Status

**Pass 3 — error-aware adaptive predictive autoscaling is complete.** The local Docker environment includes label-scoped Nginx membership, five-second monitoring, MongoDB persistence, a Random Forest predictor, reactive/predictive policies, prediction feedback, and guarded adaptive candidate replacement.

**Pass 4 — dashboard, experiment recording, exports, and end-to-end integration are complete.** The React dashboard is available at `http://localhost:5173` when Docker Compose is running. It polls the backend's read-only API every five seconds and shows current state, charts, scaling/adaptation histories, model data, and observed experiment results.

## Locked control loop

```text
LOAD → MONITOR → PREDICT → DECIDE → SCALE → FEEDBACK → ADAPT
```

Locust will generate controlled workloads against Nginx, which will route traffic to healthy FastAPI application replicas. Monitoring will collect operational metrics. A Random Forest model will predict aggregate CPU, policies will make scaling decisions, and an adaptive loop will use prediction error to decide whether to retrain and activate a validated new model version.

## Measurement and prediction contract

- Monitoring interval: **5 seconds**.
- Initial prediction horizon: **30 seconds** (six monitoring intervals).
- Primary CPU metric: arithmetic mean CPU utilization across all currently active, healthy application replicas.
- At observation time `t`, features may use only data available at or before `t`; the target is the actual aggregate CPU observed at `t + 30 seconds`.
- Training and evaluation use chronological splits to prevent temporal leakage.

Full definitions are in [docs/architecture.md](docs/architecture.md), [docs/decisions.md](docs/decisions.md), and [adaptive retraining](docs/adaptive-retraining.md).

## Safety boundaries

The future scaling controller will communicate with the local Docker Engine through its Docker API. It will manage only application containers carrying all required project labels; it will not act on arbitrary host containers. Nginx membership follows this fixed lifecycle:

```text
discover healthy replicas → generate upstream → validate configuration → graceful reload
```

## Configuration

The configuration contract is defined by [config/schema.json](config/schema.json). Default and policy-specific YAML configuration files are in `config/`. Values are intentionally declarative only at this stage; they are not yet consumed by runtime code.

## Documentation

- [Architecture](docs/architecture.md)
- [Architecture decisions](docs/decisions.md)
- [Experiment protocol](docs/experiment-protocol.md)
- [Configuration reference](docs/configuration.md)
- [Planned API](docs/api.md)
- [Adaptive retraining](docs/adaptive-retraining.md)

## Planned phases

1. Foundation and architecture documentation — complete
2. Containerized FastAPI application and safe container identity
3. Docker Engine boundary and dynamic Nginx membership
4. Locust workload scenarios
5. Monitoring and persistence
6. Observability API and dashboard
7. Reactive baseline
8. Leak-free dataset construction and Random Forest prediction
9. Predictive autoscaling
10. Feedback and prediction-error records
11. Adaptive predictive autoscaling
12. Reproducible experiment execution
13. Comparative evaluation and final verification

See [docs/architecture.md](docs/architecture.md) for phase acceptance criteria.
