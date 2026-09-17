# Planned API Surface

The backend exposes read-only monitoring endpoints on port `8001`. They never expose arbitrary Docker operations or make scaling decisions.

| Endpoint | Purpose |
|---|---|
| `GET /health` | Backend liveness response. |
| `GET /api/metrics/current` | Latest persisted five-second metric; returns `404` before collection starts. |
| `GET /api/metrics/history?limit=100` | Persisted metrics, newest first; `limit` is 1–1000. |
| `GET /api/status` | Monitoring state, last sample, healthy replica count, and collection error when present. |
| `GET /api/containers` | Per-container measurements from the latest persisted metric. |
| `GET /api/predictions` | Prediction records, including target-time actual CPU/error when evaluated. |
| `GET /api/models` | Random Forest model-version records and measured MAE/RMSE metadata. |
| `GET /api/scaling/events` | Read-only reactive/predictive scaling history. |

Later passes may add read-only resources for predictions/errors, scaling events, model versions, and experiment records. The frontend will consume these APIs for visibility; it will not directly control Docker or make scaling decisions.
