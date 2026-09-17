# Error-Aware Adaptive Retraining

The adaptive policy retains the Pass 2 predictive scaling decision path. It adds a guarded replacement path after prediction feedback:

```text
prediction → target observation → absolute error → consecutive breaches
→ cooldown and sample gates → Random Forest candidate → chronological validation
→ activation or rejection
```

All five configured gates must pass before a candidate can be trained and activated:

1. The absolute prediction error is greater than `adaptive.absolute_error_threshold`.
2. The most recent `adaptive.consecutive_error_requirement` evaluated predictions all breach that threshold.
3. At least `adaptive.minimum_recent_training_samples` valid, leak-free samples can be built from recent monitoring observations.
4. The retraining cooldown has expired. An attempted candidate, including a rejected one, starts this cooldown. New evaluated errors are also required after an attempt.
5. The candidate passes chronological validation before activation.

Recent-data candidates use the same 30-second target and feature definition as Pass 2. The newest valid samples are split chronologically using `prediction.training_fraction`; the early portion trains the candidate and the later portion validates it. The active model and candidate are evaluated on that identical holdout. A candidate passes when its MAE is no greater than the active model's MAE; RMSE is recorded for both models but is not an activation threshold.

Every candidate has an immutable model-version record. Its metadata includes the artifact location, training window, valid/training/validation sample counts, feature definition version, validation metrics, triggering errors, attempt time, and activation state. Rejected candidates remain `rejected`; on success the previous `active` model becomes `superseded` and the candidate becomes `active`. Artifacts are retained.

The feedback acceptance window equals the locked monitoring interval. This permits the first future observation collected by the five-second monitor to evaluate a 30-second forecast, while retaining temporal ordering and avoiding use of pre-target observations.
