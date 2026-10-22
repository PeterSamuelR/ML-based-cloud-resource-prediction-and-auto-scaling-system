import { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import { loadDashboard } from "./api";
import { LineChart } from "./LineChart";
import { activeModel, adaptationHistory, cpuTrend, experimentSummary, latestEvaluatedPrediction, livePrediction, modelMetrics, predictionSeries, recentScalingEvent, series } from "./dashboard-data";
import "./styles.css";

const display = (value, suffix = "") => value === null || value === undefined ? "—" : `${Number(value).toFixed(2)}${suffix}`;
const clock = (value) => value ? new Date(value).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" }) : "—";
const dateTime = (value) => value ? new Date(value).toLocaleString([], { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit", second: "2-digit" }) : "—";
const shortVersion = (version) => {
  if (!version) return "Unavailable";
  const match = version.match(/^rf-(\d{4})(\d{2})(\d{2})(\d{2})(\d{2})\d{2}-([a-f\d]+)/i);
  if (!match) return version.length > 20 ? `${version.slice(0, 13)}…` : version;
  const month = new Date(Number(match[1]), Number(match[2]) - 1, 1).toLocaleString([], { month: "short" });
  return `RF · ${match[3]} ${month} ${match[4]}:${match[5]} · ${match[6].slice(0, 4)}`;
};

function MetricCard({ label, value, note, tone = "", className = "" }) {
  return <article className={`metric-card ${tone} ${className}`}><span className="metric-label">{label}</span><strong className="metric-value">{value}</strong>{note && <small>{note}</small>}</article>;
}

function PolicyBadge({ policy }) {
  const details = {
    reactive: ["REACTIVE", "Current CPU driven"],
    predictive: ["PREDICTIVE", "30-sec forecast driven"],
    adaptive_predictive: ["ADAPTIVE", "Forecast + error feedback"],
  };
  const [label, description] = details[policy] ?? [String(policy ?? "Unknown").toUpperCase(), "Policy status"];
  return <div className="policy-badge"><span className="policy-dot" /><span><strong>{label}</strong><small>{description}</small></span></div>;
}

function App() {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [refreshing, setRefreshing] = useState(false);
  const refresh = () => {
    setRefreshing(true);
    return loadDashboard().then((next) => { setData(next); setError(""); }).catch((cause) => setError(cause.message)).finally(() => setRefreshing(false));
  };
  useEffect(() => { refresh(); const timer = setInterval(refresh, 5000); return () => clearInterval(timer); }, []);
  if (!data) return <main className="loading">Loading observed system data…{error && <p>{error}</p>}</main>;

  const evaluated = latestEvaluatedPrediction(data.predictions);
  const model = activeModel(data.models);
  const metrics = modelMetrics(model);
  const adaptations = adaptationHistory(data.models);
  const predictionState = data.predictionState;
  const prediction = livePrediction(predictionState);
  const scalingEvent = recentScalingEvent(data.scalingEvents);
  const experiments = experimentSummary(data.experiments);
  const trend = cpuTrend(data.metrics);
  const healthy = data.status.monitoring === "healthy";
  const modelTrainingAt = predictionState?.model_training_timestamp;
  const modelAgeMinutes = predictionState?.model_age_seconds != null ? Math.floor(predictionState.model_age_seconds / 60) : null;

  return <main className="dashboard-shell">
    <header className="topbar">
      <div className="brand-block"><p className="eyebrow">Cloud Resource Prediction & Autoscaling</p><h1>Live Control Center</h1><p className="header-subtitle">Real-time resource visibility and policy-driven scaling.</p></div>
      <div className="header-actions"><PolicyBadge policy={data.status.autoscaling_mode} /><div className="live-state"><span className={`live-dot ${healthy ? "" : "is-degraded"}`} /><span><strong>{healthy ? "SYSTEM HEALTHY" : "SYSTEM DEGRADED"}</strong><small>Updating every ~5 seconds</small></span></div><button className="refresh-button" onClick={refresh} disabled={refreshing}>{refreshing ? "Updating…" : "Refresh"}</button></div>
    </header>
    {error && <p className="error-banner">Update failed: {error}. Showing the last observed values.</p>}

    <nav className="flow-strip" aria-label="System flow">{["LOAD", "MONITOR", "PREDICT", "DECIDE", "SCALE", "FEEDBACK", "ADAPT"].map((stage, index) => <span className={stage === "PREDICT" && prediction ? "flow-stage is-live" : "flow-stage"} key={stage}>{index > 0 && <i aria-hidden="true">→</i>}{stage}</span>)}</nav>

    <section className="overview-grid" aria-label="Current system overview">
      <article className="hero-card current-hero">
        <div className="hero-heading"><span className="metric-label">CURRENT CPU</span><span className="state-tag"><i /> OBSERVED NOW</span></div>
        <strong className="hero-value">{display(data.current.aggregate_cpu_percent, "%")}</strong>
        <div className="hero-foot"><span>{trend ? <><b className={`trend-arrow ${trend.direction}`}>{trend.direction === "rising" ? "↑" : trend.direction === "falling" ? "↓" : "→"}</b> {trend.label}</> : "Current aggregate utilization"}</span><span title={dateTime(data.current.timestamp)}>Sample {clock(data.current.timestamp)}</span></div>
      </article>

      <article className="hero-card forecast-hero">
        <div className="hero-heading"><span className="metric-label">PREDICTED CPU</span><span className={`state-tag ${prediction ? "forecast-live" : "state-muted"}`}><i /> {prediction ? "LIVE" : (predictionState?.status ?? "unavailable").toUpperCase()}</span></div>
        <strong className="hero-value forecast-value">{display(prediction?.predicted_aggregate_cpu_percent, "%")}</strong>
        <div className="hero-foot forecast-foot"><span>{predictionState?.prediction_age_seconds != null ? `${Number(predictionState.prediction_age_seconds).toFixed(1)}s old` : "No current forecast"}<b>Forecast: +30 sec</b></span><span title={dateTime(prediction?.target_timestamp)}>Target {clock(prediction?.target_timestamp)}</span></div>
      </article>

      <MetricCard label="HEALTHY REPLICAS" value={data.status.active_healthy_replica_count ?? data.current.active_healthy_replica_count} note={`${data.status.active_healthy_replica_count ?? data.current.active_healthy_replica_count ?? 0} active healthy`} tone="replica-card" />
      <MetricCard label="REQUEST RATE" value={display(data.current.request_rate_per_second, "/s")} note="Requests through Nginx" tone="request-card" />
      <MetricCard label="RESPONSE TIME" value={display(data.current.response_time_ms, " ms")} note="Observed response duration" tone="response-card" />
      <MetricCard label="AGGREGATE MEMORY" value={display(data.current.aggregate_memory_percent, "%")} note="Across healthy replicas" tone="memory-card" />
      <MetricCard label="LATEST EVALUATED ERROR" value={display(evaluated?.absolute_error, " pts")} note={evaluated ? `Absolute error · target ${clock(evaluated.target_timestamp)}` : "Awaiting a completed forecast"} tone="error-card" />
    </section>

    {scalingEvent && <section className={`event-banner ${scalingEvent.action === "scale_out" ? "scale-out" : "scale-in"}`} aria-label="Latest scaling event"><div className="event-symbol">{scalingEvent.action === "scale_out" ? "↗" : "↘"}</div><div className="event-main"><strong>{scalingEvent.action === "scale_out" ? "SCALE OUT" : "SCALE IN"} · {scalingEvent.status ?? "recorded"}</strong><span>{scalingEvent.replica_count_before ?? "—"} → {scalingEvent.replica_count_after ?? "—"} replicas</span></div><div className="event-meta"><span>{String(scalingEvent.policy ?? "").replaceAll("_", " ")}</span><time title={dateTime(scalingEvent.timestamp)}>{clock(scalingEvent.timestamp)}</time></div></section>}

    <section className="support-grid">
      <article className="panel model-panel"><div className="section-heading"><div><p className="eyebrow">MODEL STATUS</p><h2>Active prediction model</h2></div><span className="status-pill good"><i /> {model?.status?.toUpperCase() ?? "UNAVAILABLE"}</span></div>
        <div className="model-facts"><div><span>Algorithm</span><strong>Random Forest</strong></div><div><span>Active version</span><strong title={model?.version ?? predictionState?.active_model_version}>{shortVersion(model?.version ?? predictionState?.active_model_version)}</strong><small className="full-version">{model?.version ?? predictionState?.active_model_version ?? "No active version"}</small></div><div><span>Model age</span><strong>{modelAgeMinutes == null ? "—" : `${modelAgeMinutes} min`}</strong><small>{modelTrainingAt ? `Trained ${dateTime(modelTrainingAt)}` : "Training time unavailable"}</small></div><div><span>Validation MAE</span><strong>{display(metrics.mae)}</strong></div><div><span>Validation RMSE</span><strong>{display(metrics.rmse)}</strong></div></div>
      </article>
      <article className="panel evaluated-panel"><div className="section-heading"><div><p className="eyebrow">FORECAST FEEDBACK</p><h2>Latest evaluated forecast</h2></div><span className="status-pill error-pill"><i /> COMPLETED</span></div>
        {evaluated ? <><div className="evaluation-values"><div><span>Forecast</span><strong>{display(evaluated.predicted_aggregate_cpu_percent, "%")}</strong></div><b aria-hidden="true">→</b><div><span>Actual at target</span><strong>{display(evaluated.actual_aggregate_cpu_percent, "%")}</strong></div><div className="evaluation-error"><span>Absolute error</span><strong>{display(evaluated.absolute_error, " pts")}</strong></div></div><p className="evaluation-time">Issued {dateTime(evaluated.timestamp)} <span>·</span> Target {dateTime(evaluated.target_timestamp)}</p></> : <p className="empty">No completed forecast evaluation yet.</p>}
      </article>
    </section>

    <section className="charts-section">
      <div className="section-heading section-heading-outside"><div><p className="eyebrow">OBSERVABILITY</p><h2>Current state vs future forecast</h2><p>Forecast values are plotted at their target time and paired with the actual observation for that same target.</p></div></div>
      <div className="charts-grid">
        <LineChart className="chart-featured" title="Aggregate CPU · actual vs predicted (%)" data={predictionSeries(data.predictions)} lines={[{ key: "actual", label: "Actual at target", color: "#43d6a1" }, { key: "predicted", label: "30-sec forecast", color: "#7ea5ff" }]} description="Historical forecasts aligned to the timestamp they predicted. Both lines use the same target-time observations." />
        <LineChart title="Aggregate CPU over time (%)" data={series(data.metrics, "aggregate_cpu_percent")} lines={[{ key: "value", label: "CPU", color: "#ffb86b" }]} />
        <LineChart title="Request rate over time (/s)" data={series(data.metrics, "request_rate_per_second")} lines={[{ key: "value", label: "Requests", color: "#b59cff" }]} />
        <LineChart title="Healthy replicas over time" data={series(data.metrics, "active_healthy_replica_count")} lines={[{ key: "value", label: "Replicas", color: "#43d6a1" }]} />
        <LineChart title="Prediction error over time (pts)" data={series(data.predictions.filter((item) => item.absolute_error !== null && item.absolute_error !== undefined), "absolute_error")} lines={[{ key: "value", label: "Absolute error", color: "#ff7188" }]} />
      </div>
    </section>

    <section className="tables-section">
      <div className="section-heading section-heading-outside"><div><p className="eyebrow">CONTROL & LEARNING</p><h2>System activity</h2></div></div>
      <div className="tables-grid">
        <section className="panel table-panel"><div className="section-heading"><div><p className="eyebrow">AUTOSCALING</p><h2>Scaling history</h2></div></div><Table rows={data.scalingEvents} kind="scaling" columns={[["timestamp", "Time"], ["policy", "Policy"], ["action", "Action"], ["replica_count_before", "Before"], ["replica_count_after", "After"], ["status", "Status"]]} /></section>
        <section className="panel table-panel"><div className="section-heading"><div><p className="eyebrow">ADAPTIVE LOOP</p><h2>Adaptation & retraining</h2></div></div><Table rows={adaptations} kind="model" columns={[["created_at", "Time"], ["version", "Candidate version"], ["status", "Status"]]} detail={(row) => `Validation ${row.metadata?.validation?.passed ? "passed" : "rejected"} · ${row.metadata?.retraining_reason?.consecutive_error_requirement ?? "—"} consecutive errors`} /></section>
        <section className="panel table-panel wide"><div className="section-heading"><div><p className="eyebrow">REPRODUCIBLE EVALUATION</p><h2>Experiment results</h2></div><span className="experiment-total">{experiments.total} {experiments.total === 1 ? "experiment" : "experiments"}</span></div>
          <div className="experiment-summary"><div><span>Best MAE</span><strong>{display(experiments.bestMae)}</strong></div><div><span>Best policy</span><strong>{experiments.bestPolicy ?? "—"}</strong></div><div><span>Best workload</span><strong>{experiments.bestWorkload ?? "—"}</strong></div><div><span>Avg response time</span><strong>{display(experiments.averageResponseTime, " ms")}</strong></div></div>
          <Table rows={data.experiments} kind="experiment" columns={[["experiment_id", "Experiment"], ["status", "Status"], ["started_at", "Started"]]} detail={(row) => <><span>{row.configuration?.policy ?? "—"} · {row.configuration?.workload?.scenario ?? "—"}</span><span>MAE {display(row.results?.summary?.prediction_mae)} · Mean response {display(row.results?.summary?.mean_response_time_ms, " ms")}</span><a href={`/api/experiments/${row.experiment_id}/export?format=csv`}>CSV</a><a href={`/api/experiments/${row.experiment_id}/export?format=json`}>JSON</a></>} />
        </section>
      </div>
    </section>
    <footer className="footer-note"><span><i className={`live-dot ${healthy ? "" : "is-degraded"}`} /> Observed backend data</span><span>5-sec monitoring · 30-sec prediction horizon</span></footer>
  </main>;
}

function StatusBadge({ value }) {
  const normalized = String(value ?? "unknown").toLowerCase();
  const tone = normalized.startsWith("scale out") ? "scale-out" : normalized.startsWith("scale in") ? "scale-in" : ["active", "completed", "healthy", "passed"].includes(normalized) ? "good" : ["rejected", "failed", "error"].includes(normalized) ? "bad" : "neutral";
  return <span className={`status-pill ${tone}`}><i />{normalized.toUpperCase()}</span>;
}

function Table({ rows, columns, detail, kind }) {
  return rows.length ? <div className="table-wrap"><table><thead><tr>{columns.map(([, label]) => <th key={label}>{label}</th>)}{detail && <th>Details</th>}</tr></thead><tbody>{rows.map((row, index) => <tr key={row.experiment_id ?? row.version ?? row.timestamp ?? index}>
    {columns.map(([key]) => <td key={key} title={key.includes("timestamp") || key === "created_at" ? dateTime(row[key]) : key === "version" ? row[key] : undefined}>
      {key.includes("timestamp") || key === "created_at" ? <time>{clock(row[key])}<small>{row[key] ? new Date(row[key]).toLocaleDateString([], { day: "2-digit", month: "short", year: "numeric" }) : "—"}</small></time> : key === "status" ? <StatusBadge value={row[key]} /> : key === "version" ? <span className="compact-version">{shortVersion(row[key])}</span> : key === "policy" ? <span className="policy-cell">{String(row[key] ?? "—").replaceAll("_", " ")}</span> : key === "action" ? <StatusBadge value={row[key]?.replace("scale_", "scale ")} /> : String(row[key] ?? "—")}
    </td>)}{detail && <td className="detail">{typeof detail === "function" ? detail(row) : detail}</td>}</tr>)}</tbody></table></div> : <p className="empty">No observed records yet.</p>;
}

createRoot(document.getElementById("root")).render(<App />);
