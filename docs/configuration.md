# Configuration Reference

`config/schema.json` defines the baseline configuration contract. `default.yaml` supplies common values; policy files state policy-specific overrides for later phases.

| Setting | Initial value | Meaning |
|---|---:|---|
| `monitoring.interval_seconds` | 5 | Required sampling interval. |
| `monitoring.aggregate_cpu_definition` | `mean_active_healthy_application_replicas` | Arithmetic mean CPU across active healthy app replicas. |
| `prediction.horizon_seconds` | 30 | Future target offset. |
| `prediction.model` | `random_forest_regression` | Approved initial model family. |
| `prediction.minimum_training_samples` | 8 | Minimum leak-free feature/target samples before initial training. |
| `prediction.training_fraction` | 0.8 | Earliest chronological fraction used for training; later records validate. |
| `scaling.scale_out_step` / `scaling.scale_in_step` | 1 / 1 | Fixed one-replica safety step per scaling event. |
| `nginx.membership_sync_interval_seconds` | 2 | Interval used to discover health-qualified membership changes. |
| `nginx.membership_lifecycle` | `discover_generate_validate_graceful_reload` | Required Nginx membership sequence. |
| `scaling.min_replicas` | 1 | Lower safety bound. |
| `scaling.max_replicas` | 5 | Upper safety bound. |
| `scaling.cooldown_seconds` | 30 | Initial decision cooldown. |
| `adaptive.absolute_error_threshold` | 15.0 | Error trigger threshold, in aggregate CPU percentage points. |
| `adaptive.consecutive_error_requirement` | 3 | Consecutive evaluated breaches required. |
| `adaptive.minimum_recent_training_samples` | 120 | Minimum valid recent samples for candidate training. |
| `adaptive.retraining_cooldown_seconds` | 1800 | Minimum time between retraining attempts. |
| `adaptive.candidate_validation_required` | `true` | Candidate must pass validation before activation. |

Adaptive candidate validation is chronological and compares candidate MAE with the current active model's MAE on the same recent holdout. Candidate and baseline RMSE are stored for inspection. See [adaptive retraining](adaptive-retraining.md) for the complete activation contract.

The numeric values are initial, configurable research defaults—not claimed optimal settings. Their suitability will be evaluated later using real experiments.

## Pass 1 workload controls

Locust always targets `http://localhost:8080`, the Nginx entry point. The selectable `LOCUST_WORKLOAD_SCENARIO` values are `stable`, `gradual_increase`, `sudden_spike`, `sudden_drop`, `periodic`, and `changing_workload`. `LOCUST_WORK_DURATION_MS`, `LOCUST_WORK_INTENSITY`, `LOCUST_PHASE_SECONDS`, `LOCUST_WAIT_MIN_SECONDS`, and `LOCUST_WAIT_MAX_SECONDS` control its bounded requests and pacing.
