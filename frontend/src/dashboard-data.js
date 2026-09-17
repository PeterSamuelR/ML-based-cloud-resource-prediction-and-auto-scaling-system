export const chronological = (items) => [...items].sort((a, b) => new Date(a.timestamp ?? a.created_at) - new Date(b.timestamp ?? b.created_at));

export function latestEvaluatedPrediction(predictions) {
  return predictions.find((prediction) => prediction.actual_aggregate_cpu_percent !== null && prediction.actual_aggregate_cpu_percent !== undefined) ?? null;
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
  return chronological(items).map((item) => ({ label: new Date(item[timestamp]).toLocaleTimeString(), value: item[value] ?? null }));
}

export function predictionSeries(predictions) {
  return chronological(predictions)
    .filter((item) => item.actual_aggregate_cpu_percent !== null && item.actual_aggregate_cpu_percent !== undefined)
    .map((item) => ({ label: new Date(item.timestamp).toLocaleTimeString(), predicted: item.predicted_aggregate_cpu_percent, actual: item.actual_aggregate_cpu_percent }));
}

export function adaptationHistory(models) {
  return models.filter((model) => model.metadata?.retraining_attempted_at);
}
