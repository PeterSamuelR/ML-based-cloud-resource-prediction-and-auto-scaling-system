export function LineChart({ title, data, lines }) {
  const usable = data.filter((point) => lines.some((line) => Number.isFinite(point[line.key])));
  const values = usable.flatMap((point) => lines.map((line) => point[line.key]).filter(Number.isFinite));
  if (!values.length) return <section className="panel chart"><h2>{title}</h2><p className="empty">No observed data yet.</p></section>;
  const low = Math.min(...values);
  const high = Math.max(...values);
  const range = high - low || 1;
  const points = (key) => usable.map((point, index) => {
    const x = usable.length === 1 ? 50 : (index / (usable.length - 1)) * 100;
    const y = 90 - ((point[key] - low) / range) * 80;
    return `${x},${y}`;
  }).join(" ");
  return <section className="panel chart">
    <div className="chart-heading"><h2>{title}</h2><span>{low.toFixed(2)}–{high.toFixed(2)}</span></div>
    <svg viewBox="0 0 100 100" preserveAspectRatio="none" role="img" aria-label={title}>
      <line x1="0" y1="90" x2="100" y2="90" className="axis" />
      {lines.map((line) => <polyline key={line.key} points={points(line.key)} className="line" style={{ stroke: line.color }} />)}
    </svg>
    <div className="legend">{lines.map((line) => <span key={line.key}><i style={{ background: line.color }} />{line.label}</span>)}</div>
  </section>;
}
