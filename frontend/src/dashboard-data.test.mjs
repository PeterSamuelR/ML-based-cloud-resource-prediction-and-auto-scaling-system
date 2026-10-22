import assert from "node:assert/strict";
import test from "node:test";
import { activeModel, cpuTrend, experimentSummary, latestEvaluatedPrediction, livePrediction, modelMetrics, predictionSeries, recentScalingEvent, series } from "./dashboard-data.js";

test("dashboard helpers select evaluated forecasts and active model", () => {
  const predictions = [
    { timestamp: "2026-01-01T00:00:02Z", target_timestamp: "2026-01-01T00:00:32Z", predicted_aggregate_cpu_percent: 30, actual_aggregate_cpu_percent: 29 },
    { timestamp: "2026-01-01T00:00:01Z", target_timestamp: "2026-01-01T00:00:31Z", predicted_aggregate_cpu_percent: 20, actual_aggregate_cpu_percent: 25 },
  ];
  assert.equal(latestEvaluatedPrediction(predictions).actual_aggregate_cpu_percent, 29);
  assert.deepEqual(predictionSeries(predictions), [
    { label: new Date("2026-01-01T00:00:31Z").toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", hourCycle: "h23" }), timestamp: "2026-01-01T00:00:31Z", predicted: 20, actual: 25 },
    { label: new Date("2026-01-01T00:00:32Z").toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", hourCycle: "h23" }), timestamp: "2026-01-01T00:00:32Z", predicted: 30, actual: 29 },
  ]);
  const metricSeries = series([{ timestamp: "2026-01-01T20:19:48Z", aggregate_cpu_percent: 51.234 }], "aggregate_cpu_percent");
  assert.equal(metricSeries[0].label, new Date("2026-01-01T20:19:48Z").toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", hourCycle: "h23" }));
  assert.equal(metricSeries[0].timestamp, "2026-01-01T20:19:48Z");
  const model = activeModel([{ status: "superseded" }, { status: "active", metadata: { validation: { candidate: { mae: 2, rmse: 3 } } } }]);
  assert.deepEqual(modelMetrics(model), { mae: 2, rmse: 3 });
});

test("dashboard summaries use only real experiment, scaling, and CPU history values", () => {
  const summary = experimentSummary([
    { status: "completed", configuration: { policy: "predictive", workload: { scenario: "sudden_spike" } }, results: { summary: { prediction_mae: 4.5, mean_response_time_ms: 100 } } },
    { status: "completed", configuration: { policy: "reactive", workload: { scenario: "stable" } }, results: { summary: { prediction_mae: 8, mean_response_time_ms: 200 } } },
    { status: "completed", results: { summary: { prediction_mae: null, mean_response_time_ms: null } } },
    { status: "invalid", results: { summary: { prediction_mae: 0.1, mean_response_time_ms: 10 } } },
  ]);
  assert.deepEqual(summary, { total: 4, bestMae: 4.5, bestPolicy: "predictive", bestWorkload: "sudden spike", averageResponseTime: 150 });
  assert.equal(recentScalingEvent([{ timestamp: "2026-01-01T00:00:01Z" }, { timestamp: "2026-01-01T00:00:02Z", action: "scale_out" }]).action, "scale_out");
  assert.deepEqual(cpuTrend([{ timestamp: "2026-01-01T00:00:01Z", aggregate_cpu_percent: 20 }, { timestamp: "2026-01-01T00:00:06Z", aggregate_cpu_percent: 24 }]), { direction: "rising", delta: 4, label: "Rising" });
  assert.equal(cpuTrend([{ timestamp: "2026-01-01T00:00:01Z", aggregate_cpu_percent: 20 }, { timestamp: "2026-01-01T00:00:06Z", aggregate_cpu_percent: null }]), null);
});

test("dashboard never displays stale or unavailable predictions as current", () => {
  const prediction = { predicted_aggregate_cpu_percent: 87.3 };
  assert.equal(livePrediction({ status: "live", prediction }), prediction);
  assert.equal(livePrediction({ status: "stale", prediction }), null);
  assert.equal(livePrediction({ status: "unavailable", prediction: null }), null);
});
