export const chronological = (items) => [...items].sort((a, b) => new Date(a.timestamp ?? a.created_at) - new Date(b.timestamp ?? b.created_at));

export function latestEvaluatedPrediction(predictions) {
  return [...predictions]
    .filter((prediction) => prediction.actual_aggregate_cpu_percent !== null && prediction.actual_aggregate_cpu_percent !== undefined)
    .sort((a, b) => new Date(b.target_timestamp ?? b.timestamp) - new Date(a.target_timestamp ?? a.timestamp))[0] ?? null;
}

export function livePrediction(predictionState) {
  return predictionState?.status === "live" ? predictionState.prediction : null;
}

export function activeModel(models) {
  return models.find((model) => model.status === "active") ?? null;
}

export function modelMetrics(model) {
  if (!model) return { mae: null, rmse: null };
  const validation = model.metadata?.validation?.candidate;
  return { mae: validation?.mae ?? model.metadata?.mae ?? null, rmse: validation?.rmse ?? model.metadata?.rmse ?? null };
}

export function series(items, value, timestamp = "timestamp") {
  return chronological(items).map((item) => ({
    label: new Date(item[timestamp]).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", hourCycle: "h23" }),
    timestamp: item[timestamp],
    value: item[value] ?? null,
  }));
}

export function predictionSeries(predictions) {
  return chronological(predictions)
    .filter((item) => item.actual_aggregate_cpu_percent !== null && item.actual_aggregate_cpu_percent !== undefined)
    .map((item) => {
      const target = item.target_timestamp ?? item.timestamp;
      return { label: new Date(target).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", hourCycle: "h23" }), timestamp: target, predicted: item.predicted_aggregate_cpu_percent, actual: item.actual_aggregate_cpu_percent };
    });
}

export function adaptationHistory(models) {
  return models.filter((model) => model.metadata?.retraining_attempted_at);
}

export function recentScalingEvent(events) {
  return [...events].sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp))[0] ?? null;
}

export function cpuTrend(metrics) {
  const samples = chronological(metrics).filter((item) => item.aggregate_cpu_percent !== null && item.aggregate_cpu_percent !== undefined && Number.isFinite(Number(item.aggregate_cpu_percent))).slice(-2);
  if (samples.length < 2) return null;
  const delta = Number(samples[1].aggregate_cpu_percent) - Number(samples[0].aggregate_cpu_percent);
  const direction = delta > 1 ? "rising" : delta < -1 ? "falling" : "stable";
  return { direction, delta, label: direction === "stable" ? "Stable" : direction === "rising" ? "Rising" : "Falling" };
}

export function experimentSummary(experiments) {
  const eligibleExperiments = experiments.filter((experiment) => experiment.status === "completed" && experiment.valid !== false && experiment.results?.valid !== false);
  const withMae = eligibleExperiments
    .map((experiment) => ({ experiment, rawMae: experiment.results?.summary?.prediction_mae, mae: Number(experiment.results?.summary?.prediction_mae) }))
    .filter(({ rawMae, mae }) => rawMae !== null && rawMae !== undefined && Number.isFinite(mae));
  const best = withMae.reduce((winner, entry) => !winner || entry.mae < winner.mae ? entry : winner, null);
  const responseTimes = eligibleExperiments
    .map((experiment) => experiment.results?.summary?.mean_response_time_ms)
    .filter((value) => value !== null && value !== undefined && Number.isFinite(Number(value)))
    .map(Number);
  return {
    total: experiments.length,
    bestMae: best?.mae ?? null,
    bestPolicy: best?.experiment.configuration?.policy?.replaceAll("_", " ") ?? null,
    bestWorkload: best?.experiment.configuration?.workload?.scenario?.replaceAll("_", " ") ?? null,
    averageResponseTime: responseTimes.length ? responseTimes.reduce((total, value) => total + value, 0) / responseTimes.length : null,
  };
}
