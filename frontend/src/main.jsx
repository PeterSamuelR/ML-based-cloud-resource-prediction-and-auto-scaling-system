import { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import { loadDashboard } from "./api";
import { LineChart } from "./LineChart";
import { activeModel, adaptationHistory, latestEvaluatedPrediction, modelMetrics, predictionSeries, series } from "./dashboard-data";
import "./styles.css";

const display = (value, suffix = "") => value === null || value === undefined ? "—" : `${Number(value).toFixed(2)}${suffix}`;
const time = (value) => value ? new Date(value).toLocaleString() : "—";

function Card({ label, value, note }) { return <article className="card"><span>{label}</span><strong>{value}</strong>{note && <small>{note}</small>}</article>; }

function App() {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const refresh = () => loadDashboard().then((next) => { setData(next); setError(""); }).catch((cause) => setError(cause.message));
  useEffect(() => { refresh(); const timer = setInterval(refresh, 5000); return () => clearInterval(timer); }, []);
  if (!data) return <main className="loading">Loading observed system data…{error && <p>{error}</p>}</main>;
  const evaluated = latestEvaluatedPrediction(data.predictions);
  const model = activeModel(data.models);
  const metrics = modelMetrics(model);
  const adaptations = adaptationHistory(data.models);
  const latestPrediction = data.predictions[0];
  return <main>
    <header><div><p className="eyebrow">Cloud Resource Prediction & Autoscaling</p><h1>Live control-loop dashboard</h1><p>Polling the read-only API every five seconds. Values are observed, not simulated.</p></div><button onClick={refresh}>Refresh now</button></header>
    {error && <p className="error">Last refresh failed: {error}</p>}
    <section className="cards">
      <Card label="System status" value={data.status.monitoring} note={`Last sample: ${time(data.status.last_sample_timestamp)}`} />
      <Card label="Autoscaling mode" value={data.status.autoscaling_mode ?? "—"} />
      <Card label="Healthy replicas" value={data.status.active_healthy_replica_count} />
      <Card label="Aggregate CPU" value={display(data.current.aggregate_cpu_percent, "%")} />
      <Card label="Aggregate memory" value={display(data.current.aggregate_memory_percent, "%")} />
      <Card label="Request rate" value={display(data.current.request_rate_per_second, "/s")} />
      <Card label="Response time" value={display(data.current.response_time_ms, " ms")} />
      <Card label="Predicted CPU" value={display(latestPrediction?.predicted_aggregate_cpu_percent, "%")} note={latestPrediction ? `Target: ${time(latestPrediction.target_timestamp)}` : ""} />
      <Card label="Actual CPU" value={display(evaluated?.actual_aggregate_cpu_percent, "%")} />
      <Card label="Latest prediction error" value={display(evaluated?.absolute_error, " pts")} />
      <Card label="Active model" value={model?.version ?? "No active model"} />
      <Card label="Validation MAE / RMSE" value={`${display(metrics.mae)} / ${display(metrics.rmse)}`} />
    </section>
    <section className="charts">
      <LineChart title="Actual vs predicted CPU (%)" data={predictionSeries(data.predictions)} lines={[{ key: "actual", label: "Actual", color: "#46d6a1" }, { key: "predicted", label: "Predicted", color: "#7ea5ff" }]} />
      <LineChart title="Aggregate CPU over time (%)" data={series(data.metrics, "aggregate_cpu_percent")} lines={[{ key: "value", label: "CPU", color: "#ffb86b" }]} />
      <LineChart title="Request rate over time (/s)" data={series(data.metrics, "request_rate_per_second")} lines={[{ key: "value", label: "Requests", color: "#b59cff" }]} />
      <LineChart title="Healthy replicas over time" data={series(data.metrics, "active_healthy_replica_count")} lines={[{ key: "value", label: "Replicas", color: "#46d6a1" }]} />
      <LineChart title="Prediction error over time (pts)" data={series(data.predictions.filter((item) => item.absolute_error !== null), "absolute_error")} lines={[{ key: "value", label: "Absolute error", color: "#ff6b86" }]} />
    </section>
    <section className="tables">
      <section className="panel"><h2>Scaling history</h2><Table rows={data.scalingEvents} columns={[["timestamp", "Time"], ["policy", "Policy"], ["action", "Action"], ["replica_count_before", "Before"], ["replica_count_after", "After"], ["status", "Status"]]} /></section>
      <section className="panel"><h2>Adaptation / retraining history</h2><Table rows={adaptations} columns={[["created_at", "Created"], ["version", "Candidate version"], ["status", "Status"]]} detail={(row) => `Validation: ${row.metadata?.validation?.passed ? "passed" : "rejected"}; reason: ${row.metadata?.retraining_reason?.consecutive_error_requirement ?? "—"} consecutive errors`} /></section>
      <section className="panel wide"><h2>Experiment results</h2><Table rows={data.experiments} columns={[["experiment_id", "Experiment"], ["status", "Status"], ["started_at", "Started"]]} detail={(row) => <><span>{row.configuration?.policy} · {row.configuration?.workload?.scenario}</span><span> MAE: {display(row.results?.summary?.prediction_mae)} · Mean response: {display(row.results?.summary?.mean_response_time_ms, " ms")}</span><a href={`/api/experiments/${row.experiment_id}/export?format=csv`}>CSV</a><a href={`/api/experiments/${row.experiment_id}/export?format=json`}>JSON</a></>} /></section>
    </section>
  </main>;
}

function Table({ rows, columns, detail }) { return rows.length ? <div className="table-wrap"><table><thead><tr>{columns.map(([, label]) => <th key={label}>{label}</th>)}{detail && <th>Details</th>}</tr></thead><tbody>{rows.map((row, index) => <tr key={row.experiment_id ?? row.version ?? row.timestamp ?? index}>{columns.map(([key]) => <td key={key}>{key.includes("timestamp") || key === "created_at" ? time(row[key]) : String(row[key] ?? "—")}</td>)}{detail && <td className="detail">{typeof detail === "function" ? detail(row) : detail}</td>}</tr>)}</tbody></table></div> : <p className="empty">No observed records yet.</p>; }

createRoot(document.getElementById("root")).render(<App />);
