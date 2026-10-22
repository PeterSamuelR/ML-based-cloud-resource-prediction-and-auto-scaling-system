const get = async (path) => {
  const response = await fetch(path, { cache: "no-store" });
  if (!response.ok) throw new Error(`${path}: ${response.status}`);
  return response.json();
};

export async function loadDashboard() {
  const [status, current, metrics, predictionState, predictions, models, scalingEvents, experiments] = await Promise.all([
    get("/api/status"), get("/api/metrics/current"), get("/api/metrics/history?limit=240"),
    get("/api/predictions/current"), get("/api/predictions?limit=240"), get("/api/models?limit=100"),
    get("/api/scaling/events?limit=100"), get("/api/experiments?limit=100"),
  ]);
  return { status, current, predictionState, metrics: metrics.items, predictions: predictions.items, models: models.items, scalingEvents: scalingEvents.items, experiments: experiments.items };
}
