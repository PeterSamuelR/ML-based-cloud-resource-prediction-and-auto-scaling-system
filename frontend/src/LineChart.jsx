import { useEffect, useRef, useState } from "react";

export function LineChart({ title, data, lines, description, className = "" }) {
  const svgRef = useRef(null);
  const [axisScale, setAxisScale] = useState({ x: 1, y: 1 });
  const axisTextStyle = {
    fontFamily: 'Inter, "Segoe UI", ui-sans-serif, system-ui, sans-serif',
    fontSize: "11px",
    fontWeight: 400,
    letterSpacing: "0",
    fontVariantNumeric: "tabular-nums",
    fontFeatureSettings: "normal",
    fontStretch: "normal",
  };
  const hasValue = (value) => value !== null && value !== undefined && Number.isFinite(Number(value));
  const usable = data.filter((point) => lines.some((line) => hasValue(point[line.key])));
  useEffect(() => {
    const svg = svgRef.current;
    if (!svg) return undefined;
    const updateScale = () => {
      const { width, height } = svg.getBoundingClientRect();
      if (width > 0 && height > 0) setAxisScale({ x: 112 / width, y: 100 / height });
    };
    updateScale();
    const observer = new ResizeObserver(updateScale);
    observer.observe(svg);
    return () => observer.disconnect();
  }, [usable.length > 0]);
  const values = usable.flatMap((point) => lines.map((line) => Number(point[line.key])).filter(Number.isFinite));
  if (!values.length) return <section className={`panel chart ${className}`}><div className="chart-heading"><h3>{title}</h3></div><p className="empty">No observed data yet.</p></section>;
  const low = Math.min(...values);
  const high = Math.max(...values);
  const padding = (high - low) * 0.08 || Math.max(Math.abs(high) * 0.08, 1);
  const min = Math.max(0, low - padding);
  const max = high + padding || 1;
  const range = max - min || 1;
  const tickPrecision = range < 5 ? 1 : 0;
  const xStart = 12;
  const xWidth = 96;
  const yTop = 10;
  const yHeight = 76;
  const xAt = (index) => usable.length <= 1 ? xStart + xWidth / 2 : xStart + (index / (usable.length - 1)) * xWidth;
  const yAt = (value) => yTop + yHeight - ((Number(value) - min) / range) * yHeight;
  const xLabels = [...new Set([0, Math.floor((usable.length - 1) / 2), usable.length - 1])];
  const tickValues = Array.from({ length: 4 }, (_, index) => max - (range * index) / 3);

  return <section className={`panel chart ${className}`}>
    <div className="chart-heading"><div><h3>{title}</h3>{description && <p>{description}</p>}</div><span className="chart-range">{low.toFixed(1)}–{high.toFixed(1)}</span></div>
    <svg ref={svgRef} viewBox="0 0 112 100" preserveAspectRatio="none" role="img" aria-label={title}>
      {tickValues.map((value, index) => {
        const y = yTop + (yHeight * index) / 3;
        return <g key={index}><line x1={xStart} y1={y} x2={108} y2={y} className="chart-grid" /><text x="0.5" y={y + 1} transform={`translate(0.5 ${y + 1}) scale(${axisScale.x} ${axisScale.y}) translate(-0.5 ${-(y + 1)})`} className="axis-label y-axis-label" style={axisTextStyle}>{value.toFixed(tickPrecision)}</text></g>;
      })}
      <line x1={xStart} y1={yTop} x2={xStart} y2={yTop + yHeight} className="chart-axis" />
      <line x1={xStart} y1={yTop + yHeight} x2={108} y2={yTop + yHeight} className="chart-axis" />
      {lines.map((line) => {
        const points = usable.map((point, index) => hasValue(point[line.key]) ? `${xAt(index)},${yAt(point[line.key])}` : null).filter(Boolean).join(" ");
        return <g key={line.key}>
          <polyline points={points} className="chart-line" style={{ stroke: line.color }} />
          {usable.map((point, index) => hasValue(point[line.key]) && (usable.length <= 60 || index === usable.length - 1) ? <circle key={`${line.key}-${index}`} cx={xAt(index)} cy={yAt(point[line.key])} r={usable.length <= 60 ? 1.2 : 1.7} className="chart-point" style={{ fill: line.color }}><title>{`${point.timestamp ? new Date(point.timestamp).toLocaleString() : point.label ?? ""} · ${line.label}: ${String(point[line.key])}${line.key.includes("cpu") || line.key === "actual" || line.key === "predicted" ? "%" : ""}`}</title></circle> : null)}
        </g>;
      })}
      {xLabels.map((index) => <text key={index} x={xAt(index)} y="97" transform={`translate(${xAt(index)} 97) scale(${axisScale.x} ${axisScale.y}) translate(${-xAt(index)} -97)`} textAnchor={index === 0 ? "start" : index === usable.length - 1 ? "end" : "middle"} className="axis-label" style={axisTextStyle}>{usable[index]?.label ?? ""}</text>)}
    </svg>
    <div className="legend">{lines.map((line) => <span key={line.key}><i style={{ background: line.color }} />{line.label}</span>)}</div>
  </section>;
}
