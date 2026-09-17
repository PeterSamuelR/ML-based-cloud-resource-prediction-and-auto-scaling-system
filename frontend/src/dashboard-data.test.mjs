import assert from "node:assert/strict";
import test from "node:test";
import { activeModel, latestEvaluatedPrediction, modelMetrics, predictionSeries } from "./dashboard-data.js";

test("dashboard helpers select evaluated forecasts and active model", () => {
  const predictions = [
    { timestamp: "2026-01-01T00:00:02Z", predicted_aggregate_cpu_percent: 30, actual_aggregate_cpu_percent: null },
    { timestamp: "2026-01-01T00:00:01Z", predicted_aggregate_cpu_percent: 20, actual_aggregate_cpu_percent: 25 },
  ];
  assert.equal(latestEvaluatedPrediction(predictions).actual_aggregate_cpu_percent, 25);
  assert.deepEqual(predictionSeries(predictions), [{ label: new Date("2026-01-01T00:00:01Z").toLocaleTimeString(), predicted: 20, actual: 25 }]);
  const model = activeModel([{ status: "superseded" }, { status: "active", metadata: { validation: { candidate: { mae: 2, rmse: 3 } } } }]);
  assert.deepEqual(modelMetrics(model), { mae: 2, rmse: 3 });
});
