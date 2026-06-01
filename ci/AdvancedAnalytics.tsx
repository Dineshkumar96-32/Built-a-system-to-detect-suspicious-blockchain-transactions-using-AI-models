/**
 * AdvancedAnalytics.tsx
 * ──────────────────────
 * Advanced analytics for BlockShield:
 *  • Transaction heatmap (hour-of-day × day-of-week, coloured by anomaly rate)
 *  • Historical trend sparklines (tx count, anomaly rate, flagged wallets)
 *  • Model performance stats (IF version, contamination, last retrain)
 *
 * Data: fetched from /api/v1/analytics/heatmap, /trend, /model
 * Charting: recharts (already in BlockShield frontend deps)
 */

import { useState, useEffect } from "react";
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer,
  AreaChart, Area, CartesianGrid, Legend,
} from "recharts";

// ─── Types ───────────────────────────────────────────────────

interface HeatCell { day: number; hour: number; value: number }

interface TrendPoint {
  date: string;
  tx_count: number;
  anomaly_rate: number;
  flagged_wallets: number;
  avg_score: number;
}

interface ModelStats {
  model_type: string;
  version: number;
  training_rows: number;
  labels_used: number;
  contamination: number;
  trained_at: string;
}

// ─── Mock data generators ─────────────────────────────────────

const DAYS  = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const HOURS = Array.from({ length: 24 }, (_, i) => i);

function generateHeatmap(): HeatCell[] {
  const cells: HeatCell[] = [];
  for (let day = 0; day < 7; day++) {
    for (let hour = 0; hour < 24; hour++) {
      // Simulate higher anomaly rates at night + weekends
      const base = (day === 0 || day === 6) ? 0.15 : 0.07;
      const nightBoost = (hour < 6 || hour > 22) ? 0.12 : 0;
      const noise = (Math.random() - 0.5) * 0.06;
      cells.push({ day, hour, value: Math.max(0, Math.min(1, base + nightBoost + noise)) });
    }
  }
  return cells;
}

function generateTrend(days: number = 30): TrendPoint[] {
  const points: TrendPoint[] = [];
  for (let i = days - 1; i >= 0; i--) {
    const d = new Date();
    d.setDate(d.getDate() - i);
    const date = d.toISOString().split("T")[0];
    const tx_count = Math.round(2000 + Math.random() * 3000);
    const anomaly_rate = parseFloat((0.06 + Math.random() * 0.08).toFixed(3));
    const flagged_wallets = Math.round(tx_count * anomaly_rate * 0.4);
    const avg_score = parseFloat((0.55 + Math.random() * 0.2).toFixed(3));
    points.push({ date, tx_count, anomaly_rate, flagged_wallets, avg_score });
  }
  return points;
}

const MOCK_MODELS: ModelStats[] = [
  { model_type: "isolation_forest", version: 7, training_rows: 84_200, labels_used: 350, contamination: 0.08, trained_at: "2025-05-01T02:00:00Z" },
  { model_type: "gnn",              version: 3, training_rows: 84_200, labels_used: 350, contamination: 0,    trained_at: "2025-05-01T02:15:00Z" },
];

// ─── Heatmap colours ──────────────────────────────────────────

function anomalyColor(value: number): string {
  // 0 → deep blue, 0.5 → orange, 1 → red
  if (value < 0.1)  return "#0c2340";
  if (value < 0.2)  return "#1e3a5f";
  if (value < 0.3)  return "#1d4ed8";
  if (value < 0.4)  return "#7c3aed";
  if (value < 0.55) return "#c2410c";
  if (value < 0.7)  return "#ea580c";
  return "#dc2626";
}

// ─── Custom tooltip ───────────────────────────────────────────

function TrendTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div style={{ background: "#0b0f1a", border: "1px solid #1a2035", borderRadius: 6, padding: "10px 14px", fontSize: 11 }}>
      <div style={{ color: "#9ca3af", marginBottom: 6 }}>{label}</div>
      {payload.map((p: any) => (
        <div key={p.dataKey} style={{ color: p.color, marginBottom: 2 }}>
          {p.name}: <strong>{typeof p.value === "number" && p.value < 1 ? `${(p.value * 100).toFixed(1)}%` : p.value.toLocaleString()}</strong>
        </div>
      ))}
    </div>
  );
}

// ─── Main ────────────────────────────────────────────────────

export default function AdvancedAnalytics() {
  const [heatmap]    = useState<HeatCell[]>(() => generateHeatmap());
  const [trend]      = useState<TrendPoint[]>(() => generateTrend(30));
  const [heatMetric, setHeatMetric] = useState<"anomaly_rate" | "tx_count">("anomaly_rate");
  const [trendDays,  setTrendDays]  = useState<30 | 60 | 90>(30);

  const trendData = trend.slice(-trendDays);

  return (
    <div style={{ fontFamily: "'IBM Plex Mono', monospace", background: "#060810", color: "#c9d1d9", minHeight: "100vh", padding: 28 }}>

      <div style={{ marginBottom: 24 }}>
        <h1 style={{ margin: 0, fontSize: 20, fontWeight: 700, color: "#e2e8f0" }}>📊 Advanced Analytics</h1>
        <p style={{ margin: "4px 0 0", color: "#4b5563", fontSize: 12 }}>
          Historical trend analysis and transaction pattern heatmaps.
        </p>
      </div>

      {/* ── Model stats row ── */}
      <div style={{ display: "flex", gap: 12, marginBottom: 28 }}>
        {MOCK_MODELS.map(m => (
          <div key={m.model_type} style={statCard}>
            <div style={{ fontSize: 10, color: "#4b5563", textTransform: "uppercase" as const, letterSpacing: 1, marginBottom: 6 }}>
              {m.model_type === "isolation_forest" ? "Isolation Forest" : "GNN (GraphSAGE)"}
            </div>
            <div style={{ display: "flex", gap: 16, flexWrap: "wrap" as const }}>
              {[
                ["Version",     `v${m.version}`],
                ["Training Rows", m.training_rows.toLocaleString()],
                ["Labels Used",   m.labels_used],
                ...(m.contamination ? [["Contamination", `${(m.contamination * 100).toFixed(1)}%`]] : []),
                ["Last Retrain",  new Date(m.trained_at).toLocaleDateString()],
              ].map(([k, v]) => (
                <div key={String(k)}>
                  <div style={{ fontSize: 10, color: "#374151" }}>{k}</div>
                  <div style={{ fontSize: 13, color: "#e2e8f0", fontWeight: 600 }}>{v}</div>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>

      {/* ── Heatmap ── */}
      <div style={{ ...panel, marginBottom: 28 }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
          <div style={panelTitle}>Transaction Heatmap — Hour × Day</div>
          <div style={{ display: "flex", gap: 6 }}>
            {(["anomaly_rate", "tx_count"] as const).map(m => (
              <button key={m} onClick={() => setHeatMetric(m)} style={{
                ...pillBtn,
                background: heatMetric === m ? "#1d4ed8" : "transparent",
                color: heatMetric === m ? "#fff" : "#6b7280",
                borderColor: heatMetric === m ? "#2563eb" : "#1e2433",
              }}>{m === "anomaly_rate" ? "Anomaly Rate" : "Tx Count"}</button>
            ))}
          </div>
        </div>

        {/* Grid: 7 rows × 24 cols */}
        <div>
          {/* Hour labels */}
          <div style={{ display: "flex", gap: 2, marginBottom: 4, paddingLeft: 40 }}>
            {HOURS.map(h => (
              <div key={h} style={{ width: 22, fontSize: 9, color: "#374151", textAlign: "center" as const }}>
                {h % 6 === 0 ? `${h}h` : ""}
              </div>
            ))}
          </div>

          {DAYS.map((day, di) => (
            <div key={day} style={{ display: "flex", alignItems: "center", gap: 2, marginBottom: 2 }}>
              <div style={{ width: 36, fontSize: 10, color: "#4b5563", textAlign: "right" as const, paddingRight: 4, flexShrink: 0 }}>{day}</div>
              {HOURS.map(hour => {
                const cell = heatmap.find(c => c.day === di && c.hour === hour);
                const val  = cell?.value ?? 0;
                return (
                  <div
                    key={hour}
                    title={`${day} ${hour}:00 — ${(val * 100).toFixed(1)}%`}
                    style={{
                      width: 22, height: 18, borderRadius: 2,
                      background: anomalyColor(val),
                      cursor: "default",
                      transition: "transform 0.1s",
                    }}
                    onMouseEnter={e => (e.currentTarget.style.transform = "scale(1.3)")}
                    onMouseLeave={e => (e.currentTarget.style.transform = "scale(1)")}
                  />
                );
              })}
            </div>
          ))}

          {/* Legend */}
          <div style={{ display: "flex", alignItems: "center", gap: 4, marginTop: 12, paddingLeft: 40 }}>
            <span style={{ fontSize: 10, color: "#374151" }}>Low</span>
            {["#0c2340","#1e3a5f","#1d4ed8","#7c3aed","#c2410c","#ea580c","#dc2626"].map(c => (
              <div key={c} style={{ width: 20, height: 10, background: c, borderRadius: 2 }} />
            ))}
            <span style={{ fontSize: 10, color: "#374151" }}>High</span>
          </div>
        </div>
      </div>

      {/* ── Trend charts ── */}
      <div style={{ ...panel, marginBottom: 28 }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
          <div style={panelTitle}>Historical Trends</div>
          <div style={{ display: "flex", gap: 6 }}>
            {([30, 60, 90] as const).map(d => (
              <button key={d} onClick={() => setTrendDays(d)} style={{
                ...pillBtn,
                background: trendDays === d ? "#1d4ed8" : "transparent",
                color: trendDays === d ? "#fff" : "#6b7280",
                borderColor: trendDays === d ? "#2563eb" : "#1e2433",
              }}>{d}d</button>
            ))}
          </div>
        </div>

        {/* Transaction count */}
        <div style={{ marginBottom: 24 }}>
          <div style={{ fontSize: 11, color: "#4b5563", marginBottom: 8 }}>Daily Transaction Volume</div>
          <ResponsiveContainer width="100%" height={140}>
            <AreaChart data={trendData}>
              <defs>
                <linearGradient id="gradTx" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid stroke="#1a2035" strokeDasharray="3 3" />
              <XAxis dataKey="date" tick={{ fontSize: 9, fill: "#374151" }} tickFormatter={d => d.slice(5)} />
              <YAxis tick={{ fontSize: 9, fill: "#374151" }} width={40} />
              <Tooltip content={<TrendTooltip />} />
              <Area type="monotone" dataKey="tx_count" name="Tx Count" stroke="#3b82f6" fill="url(#gradTx)" strokeWidth={1.5} dot={false} />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        {/* Anomaly rate + flagged wallets */}
        <div>
          <div style={{ fontSize: 11, color: "#4b5563", marginBottom: 8 }}>Anomaly Rate & Flagged Wallets</div>
          <ResponsiveContainer width="100%" height={160}>
            <LineChart data={trendData}>
              <CartesianGrid stroke="#1a2035" strokeDasharray="3 3" />
              <XAxis dataKey="date" tick={{ fontSize: 9, fill: "#374151" }} tickFormatter={d => d.slice(5)} />
              <YAxis yAxisId="rate" tick={{ fontSize: 9, fill: "#374151" }} width={40} tickFormatter={v => `${(v * 100).toFixed(0)}%`} />
              <YAxis yAxisId="wallets" orientation="right" tick={{ fontSize: 9, fill: "#374151" }} width={40} />
              <Tooltip content={<TrendTooltip />} />
              <Legend wrapperStyle={{ fontSize: 10, color: "#6b7280" }} />
              <Line yAxisId="rate"    type="monotone" dataKey="anomaly_rate"    name="Anomaly Rate"     stroke="#fb923c" strokeWidth={1.5} dot={false} />
              <Line yAxisId="wallets" type="monotone" dataKey="flagged_wallets" name="Flagged Wallets"  stroke="#f87171" strokeWidth={1.5} dot={false} strokeDasharray="4 2" />
              <Line yAxisId="rate"    type="monotone" dataKey="avg_score"       name="Avg Score"        stroke="#7c3aed" strokeWidth={1}   dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

    </div>
  );
}

// ─── Shared styles ────────────────────────────────────────────

const panel: React.CSSProperties = { background: "#0b0f1a", border: "1px solid #1a2035", borderRadius: 10, padding: 20 };
const panelTitle: React.CSSProperties = { fontSize: 11, color: "#4b5563", textTransform: "uppercase" as const, letterSpacing: 1, fontWeight: 700 };
const statCard: React.CSSProperties = { background: "#0b0f1a", border: "1px solid #1a2035", borderRadius: 8, padding: "14px 18px", flex: 1 };
const pillBtn: React.CSSProperties = { padding: "4px 10px", borderRadius: 4, border: "1px solid", cursor: "pointer", fontSize: 11, fontFamily: "inherit" };
