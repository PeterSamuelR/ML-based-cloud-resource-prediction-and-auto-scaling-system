# Architecture

## Scope and control loop

The intended system is a reproducible Docker-based environment for comparing reactive, predictive, and adaptive predictive autoscaling of a simple web application:

```text
LOAD → MONITOR → PREDICT → DECIDE → SCALE → FEEDBACK → ADAPT
```

```text
Locust → Nginx → healthy FastAPI application replicas
                     ↓
                  Monitoring → MongoDB → Feature builder → Random Forest predictor
                                                        ↓
                         Docker Engine ← Scaling controller ← Policy decision engine
                                                        ↓
                actual future observation ← feedback/error service ← prediction record
                                                        ↓
                    persistent-error detection → retraining → validated model version
                                                        ↓
                                      FastAPI backend APIs → React dashboard
```

Only this architecture is documented in Phase 1. Components are implemented in later approved phases.

## Primary CPU definition

At timestamp `t`, aggregate CPU utilization is the arithmetic mean CPU utilization of all currently active, healthy application replicas:

```text
aggregate_cpu(t) = sum(cpu_i(t) for each active healthy application replica i) / active_healthy_replica_count(t)
```

This is the primary CPU metric used for monitoring, dataset construction, prediction, policy decisions, feedback, and evaluation. A zero-replica condition is invalid for this calculation and must be represented as unavailable; future controllers must preserve or restore the configured minimum replica count.

## Measurement and prediction contract

- Monitoring samples occur every **5 seconds**.
- The initial prediction horizon is **30 seconds**, equivalent to six monitoring intervals.
- A feature record at `t` may contain only measurements at or before `t`.
- Its target is the actual `aggregate_cpu(t + 30 seconds)` observation.
- Records without an observed future target are excluded from supervised training/evaluation.
- Dataset splits are chronological. Random record splitting is prohibited.

The monitoring record will include timestamp, aggregate CPU, aggregate memory, request rate, response time, and active healthy application replica count. Per-replica values may be retained for traceability.

## Docker control boundary

The future backend/scaling controller will use the Python Docker SDK to access the Docker Engine API on the host. In a local Docker deployment this commonly means access to the host Docker socket. That access is highly privileged and is limited to the research environment.

The controller may discover, monitor, create, stop, or remove only containers carrying all of these labels:

```text
com.ml-autoscaler.project=cloud-resource-autoscaling
com.ml-autoscaler.role=application
com.ml-autoscaler.managed=true
```

It must enforce configured minimum/maximum replica limits, check health/readiness before adding a replica to traffic, record failures, and never manage unrelated host containers.

## Dynamic Nginx lifecycle

Nginx membership is not static. Each membership change follows this required sequence:

```text
discover active healthy labeled replicas
  → generate or update Nginx upstream configuration
  → validate the full Nginx configuration
  → graceful Nginx reload
```

For scale-in, a replica is removed from the upstream only after successful validation and reload; it is stopped/removed after that membership update. If generation, validation, or reload fails, the last valid Nginx configuration remains active and the scaling event is recorded as failed.

## Adaptive predictive loop

The adaptive contribution is an error-aware predictive loop:

```text
prediction → scaling → actual observation → prediction error
→ persistent-error detection → retraining → validated model version update
```

A candidate retraining run can replace the active model only when all five conditions hold:

1. Absolute prediction error exceeds its configured threshold.
2. Breaches persist for the configured number of consecutive predictions.
3. The configured minimum number of recent valid training samples is available.
4. The retraining cooldown has expired.
5. The newly trained candidate model passes validation before activation.

Every version will record its training time, source-window metadata, feature definition/version, model settings, validation outcome, activation status, and retraining reason.

## Phase acceptance criteria

| Phase | Acceptance criterion |
|---|---|
| 1 | Foundation files, configuration contract, and locked architecture are documented and validated. |
| 2 | Healthy labeled application replicas can be built and discovered. |
| 3 | Only managed application replicas are controlled and Nginx membership updates safely. |
| 4 | All named Locust workload patterns run with documented controls. |
| 5 | Required five-second measurements persist, including correctly calculated aggregate CPU. |
| 6 | Read-only status/history views expose stored data. |
| 7 | Reactive decisions respect thresholds, cooldown, and replica bounds. |
| 8 | Random Forest training uses leak-free 30-second targets and chronological validation. |
| 9 | Predictive decisions are stored with forecasts and target timestamps. |
| 10 | Evaluable predictions are matched exactly once with actual CPU/error records. |
| 11 | All five adaptive gates are enforced before a validated candidate becomes active. |
| 12 | Repeatable trials record configurations, raw measurements, events, and versions. |
| 13 | Reported comparison claims are traceable to actual recorded experiments. |
