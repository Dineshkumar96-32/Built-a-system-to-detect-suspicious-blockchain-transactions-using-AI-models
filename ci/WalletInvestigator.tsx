/**
 * WalletInvestigator.tsx
 * ───────────────────────
 * Deep-dive page for a single wallet address.
 *
 * Sections:
 *   1. Search bar + address validation
 *   2. Risk profile card (score, tier, OFAC, mixer flag, degree, community)
 *   3. Cluster panel  – related wallets table (links to cluster graph)
 *   4. Transaction timeline – paginated chronological tx list
 *   5. Feedback action  – flag as risky / safe (calls /api/v1/feedback)
 *
 * Routes: /wallet  (search landing)  →  /wallet/:address (profile)
 */

import { useState, useEffect, useCallback } from "react";

// ─── Types ───────────────────────────────────────────────────

interface WalletRisk {
  address: string;
  anomaly_score: number;
  gnn_risk_score: number;
  ofac_flagged: boolean;
  mixer_interaction: boolean;
  bridge_interaction: boolean;
  out_degree: number;
  in_degree: number;
  tx_count_24h: number;
  unique_counterparties: number;
  counterparty_entropy: number;
  community_id: number;
  cluster_size: number;
  risk_tier: "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
  last_seen: string;
}

interface ClusterNode {
  address: string;
  risk_tier: string;
  gnn_risk_score: number;
  tx_count: number;
}

interface TxRow {
  tx_hash: string;
  chain: string;
  value_eth: number;
  gas_price_gwei: number;
  anomaly_score: number;
  flagged: boolean;
  direction: "sent" | "received";
  counterparty: string;
  timestamp: string;
}

// ─── Colours ─────────────────────────────────────────────────

const TIER_COLOR: Record<string, string> = {
  LOW:      "#4ade80",
  MEDIUM:   "#facc15",
  HIGH:     "#fb923c",
  CRITICAL: "#f87171",
};

const TIER_BG: Record<string, string> = {
  LOW:      "#052e16",
  MEDIUM:   "#1c1400",
  HIGH:     "#1c0a00",
  CRITICAL: "#1c0505",
};

// ─── Mock data (replace with real API calls) ─────────────────

const mockRisk = (addr: string): WalletRisk => ({
  address: addr,
  anomaly_score: 0.81,
  gnn_risk_score: 0.76,
  ofac_flagged: false,
  mixer_interaction: true,
  bridge_interaction: false,
  out_degree: 42,
  in_degree: 7,
  tx_count_24h: 18,
  unique_counterparties: 11,
  counterparty_entropy: 1.23,
  community_id: 5,
  cluster_size: 14,
  risk_tier: "HIGH",
  last_seen: "2025-05-01T11:55:00Z",
});

const mockCluster: ClusterNode[] = [
  { address: "0xaaa...111", risk_tier: "CRITICAL", gnn_risk_score: 0.94, tx_count: 8 },
  { address: "0xbbb...222", risk_tier: "HIGH",     gnn_risk_score: 0.81, tx_count: 14 },
  { address: "0xccc...333", risk_tier: "MEDIUM",   gnn_risk_score: 0.55, tx_count: 3  },
  { address: "0xddd...444", risk_tier: "HIGH",     gnn_risk_score: 0.78, tx_count: 22 },
];

const mockTimeline: TxRow[] = [
  { tx_hash: "0xdead...1", chain: "ethereum", value_eth: 2.5, gas_price_gwei: 45, anomaly_score: 0.91, flagged: true,  direction: "sent",     counterparty: "0xaaa...111", timestamp: "2025-05-01T11:50:00Z" },
  { tx_hash: "0xdead...2", chain: "ethereum", value_eth: 0.1, gas_price_gwei: 32, anomaly_score: 0.34, flagged: false, direction: "received",  counterparty: "0xeee...555", timestamp: "2025-05-01T10:12:00Z" },
  { tx_hash: "0xdead...3", chain: "polygon",  value_eth: 5.0, gas_price_gwei: 120, anomaly_score: 0.78, flagged: true, direction: "sent",     counterparty: "0xbbb...222", timestamp: "2025-04-30T22:00:00Z" },
];

// ─── Sub-components ───────────────────────────────────────────

function ScoreBar({ value, color }: { value: number; color: string }) {
  return (
    <div style={{ background: "#0f1117", borderRadius: 4, height: 6, width: "100%", overflow: "hidden" }}>
      <div style={{ width: `${value * 100}%`, height: "100%", background: color, borderRadius: 4, transition: "width 0.6s ease" }} />
    </div>
  );
}

function RiskBadge({ tier }: { tier: string }) {
  return (
    <span style={{
      padding: "3px 10px", borderRadius: 4, fontSize: 11, fontWeight: 700,
      letterSpacing: 1, textTransform: "uppercase" as const,
      color: TIER_COLOR[tier] || "#fff",
      background: TIER_BG[tier] || "#111",
      border: `1px solid ${TIER_COLOR[tier] || "#333"}44`,
    }}>{tier}</span>
  );
}

function Flag({ label, active, danger = false }: { label: string; active: boolean; danger?: boolean }) {
  const col = active ? (danger ? "#f87171" : "#fb923c") : "#374151";
  return (
    <span style={{
      padding: "2px 8px", borderRadius: 4, fontSize: 11, border: `1px solid ${col}44`,
      color: col, background: active ? col + "18" : "transparent",
    }}>{label}</span>
  );
}

// ─── Main component ────────────────────────────────────────────

export default function WalletInvestigator() {
  const [query, setQuery]       = useState("");
  const [address, setAddress]   = useState<string | null>(null);
  const [risk, setRisk]         = useState<WalletRisk | null>(null);
  const [loading, setLoading]   = useState(false);
  const [error, setError]       = useState<string | null>(null);
  const [tab, setTab]           = useState<"overview" | "cluster" | "timeline">("overview");
  const [feedbackSent, setFeedbackSent] = useState<"risky" | "safe" | null>(null);

  const isValidAddr = (s: string) => /^0x[0-9a-fA-F]{40}$/.test(s.trim());

  const investigate = useCallback(async (addr: string) => {
    if (!isValidAddr(addr)) { setError("Invalid Ethereum address format."); return; }
    setError(null);
    setLoading(true);
    setAddress(addr);
    // Replace with: const data = await fetch(`/api/v1/wallet/${addr}/risk`).then(r => r.json());
    await new Promise(r => setTimeout(r, 600)); // simulate latency
    setRisk(mockRisk(addr));
    setLoading(false);
    setFeedbackSent(null);
    setTab("overview");
  }, []);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    investigate(query.trim());
  };

  const sendFeedback = async (label: "risky" | "safe") => {
    // Replace with: await fetch("/api/v1/feedback", { method:"POST", body: JSON.stringify({...}) })
    setFeedbackSent(label);
  };

  return (
    <div style={{
      fontFamily: "'IBM Plex Mono', monospace",
      background: "#060810", color: "#c9d1d9",
      minHeight: "100vh", padding: 28,
    }}>

      {/* ── Header ── */}
      <div style={{ marginBottom: 24 }}>
        <h1 style={{ margin: 0, fontSize: 20, fontWeight: 700, color: "#e2e8f0" }}>
          🔍 Wallet Investigator
        </h1>
        <p style={{ margin: "4px 0 0", color: "#4b5563", fontSize: 12 }}>
          Search any wallet address for risk profile, cluster membership, and transaction history.
        </p>
      </div>

      {/* ── Search bar ── */}
      <form onSubmit={handleSearch} style={{ display: "flex", gap: 10, marginBottom: 28 }}>
        <input
          value={query}
          onChange={e => setQuery(e.target.value)}
          placeholder="0x... wallet address"
          style={{
            flex: 1, background: "#0b0f1a", color: "#e2e8f0",
            border: "1px solid #1e2433", borderRadius: 6,
            padding: "10px 14px", fontSize: 13, fontFamily: "inherit", outline: "none",
          }}
        />
        <button type="submit" style={{
          background: "#1d4ed8", color: "#fff", border: "1px solid #2563eb",
          borderRadius: 6, padding: "10px 20px", cursor: "pointer",
          fontSize: 13, fontFamily: "inherit", fontWeight: 600,
        }}>
          Investigate
        </button>
      </form>

      {error && (
        <div style={{ background: "#1c0505", border: "1px solid #f8717166", borderRadius: 6, padding: "10px 14px", marginBottom: 16, color: "#f87171", fontSize: 13 }}>
          ⚠ {error}
        </div>
      )}

      {loading && (
        <div style={{ textAlign: "center", color: "#4b5563", padding: 48 }}>
          <div style={{ fontSize: 28, marginBottom: 8 }}>⏳</div>
          Fetching risk profile…
        </div>
      )}

      {/* ── Profile ── */}
      {risk && !loading && (
        <>
          {/* Address header */}
          <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 20 }}>
            <div style={{ fontSize: 14, color: "#9ca3af", fontFamily: "monospace" }}>{risk.address}</div>
            <RiskBadge tier={risk.risk_tier} />
            <Flag label="OFAC"   active={risk.ofac_flagged}       danger />
            <Flag label="Mixer"  active={risk.mixer_interaction}  danger />
            <Flag label="Bridge" active={risk.bridge_interaction} />
            <div style={{ flex: 1 }} />
            <span style={{ fontSize: 11, color: "#374151" }}>
              Last seen {new Date(risk.last_seen).toLocaleString()}
            </span>
          </div>

          {/* Tabs */}
          <div style={{ display: "flex", gap: 4, marginBottom: 20, borderBottom: "1px solid #1e2433" }}>
            {(["overview", "cluster", "timeline"] as const).map(t => (
              <button key={t} onClick={() => setTab(t)} style={{
                background: tab === t ? "#0b0f1a" : "transparent",
                color: tab === t ? "#e2e8f0" : "#6b7280",
                border: "none", borderBottom: tab === t ? "2px solid #3b82f6" : "2px solid transparent",
                padding: "8px 16px", cursor: "pointer", fontFamily: "inherit", fontSize: 12,
                textTransform: "capitalize" as const, fontWeight: tab === t ? 600 : 400,
              }}>{t}</button>
            ))}
          </div>

          {/* ── Overview tab ── */}
          {tab === "overview" && (
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>

              {/* Risk scores */}
              <div style={card}>
                <div style={cardTitle}>Risk Scores</div>
                <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
                  {[
                    { label: "Isolation Forest", value: risk.anomaly_score, color: "#fb923c" },
                    { label: "GNN Risk Score",   value: risk.gnn_risk_score, color: "#f87171" },
                  ].map(({ label, value, color }) => (
                    <div key={label}>
                      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                        <span style={{ fontSize: 12, color: "#9ca3af" }}>{label}</span>
                        <span style={{ fontSize: 13, fontWeight: 700, color }}>{(value * 100).toFixed(0)}%</span>
                      </div>
                      <ScoreBar value={value} color={color} />
                    </div>
                  ))}
                </div>
              </div>

              {/* Graph stats */}
              <div style={card}>
                <div style={cardTitle}>Graph Metrics</div>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                  {[
                    { label: "Out Degree",    value: risk.out_degree },
                    { label: "In Degree",     value: risk.in_degree },
                    { label: "Tx (24h)",      value: risk.tx_count_24h },
                    { label: "Counterparties",value: risk.unique_counterparties },
                    { label: "Entropy",       value: risk.counterparty_entropy.toFixed(2) },
                    { label: "Cluster Size",  value: risk.cluster_size },
                  ].map(({ label, value }) => (
                    <div key={label} style={{ background: "#060810", borderRadius: 6, padding: "10px 12px" }}>
                      <div style={{ fontSize: 10, color: "#4b5563", textTransform: "uppercase", letterSpacing: 1 }}>{label}</div>
                      <div style={{ fontSize: 18, fontWeight: 700, color: "#e2e8f0", marginTop: 2 }}>{value}</div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Analyst feedback */}
              <div style={{ ...card, gridColumn: "span 2" }}>
                <div style={cardTitle}>Analyst Classification</div>
                {feedbackSent ? (
                  <div style={{ color: feedbackSent === "risky" ? "#f87171" : "#4ade80", fontSize: 13 }}>
                    ✓ Marked as <strong>{feedbackSent}</strong>. Label submitted for model retraining.
                  </div>
                ) : (
                  <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
                    <span style={{ fontSize: 12, color: "#6b7280" }}>How would you classify this wallet?</span>
                    <button onClick={() => sendFeedback("risky")} style={{ ...feedbackBtn, borderColor: "#f87171", color: "#f87171" }}>🚨 Mark Risky</button>
                    <button onClick={() => sendFeedback("safe")} style={{ ...feedbackBtn, borderColor: "#4ade80", color: "#4ade80" }}>✓ Mark Safe</button>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* ── Cluster tab ── */}
          {tab === "cluster" && (
            <div style={card}>
              <div style={cardTitle}>Community #{risk.community_id} — {risk.cluster_size} wallets</div>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
                <thead>
                  <tr>
                    {["Address", "Risk Tier", "GNN Score", "Tx Count", "Action"].map(h => (
                      <th key={h} style={{ textAlign: "left", color: "#4b5563", fontWeight: 600, padding: "6px 10px", borderBottom: "1px solid #1e2433" }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {mockCluster.map(node => (
                    <tr key={node.address} style={{ borderBottom: "1px solid #0f1117" }}>
                      <td style={{ padding: "8px 10px", fontFamily: "monospace", color: "#9ca3af" }}>{node.address}</td>
                      <td style={{ padding: "8px 10px" }}><RiskBadge tier={node.risk_tier} /></td>
                      <td style={{ padding: "8px 10px", color: TIER_COLOR[node.risk_tier] }}>{(node.gnn_risk_score * 100).toFixed(0)}%</td>
                      <td style={{ padding: "8px 10px", color: "#e2e8f0" }}>{node.tx_count}</td>
                      <td style={{ padding: "8px 10px" }}>
                        <button
                          onClick={() => investigate(node.address)}
                          style={{ background: "transparent", border: "1px solid #1e2433", borderRadius: 4, color: "#3b82f6", padding: "3px 10px", cursor: "pointer", fontSize: 11, fontFamily: "inherit" }}
                        >
                          Investigate →
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* ── Timeline tab ── */}
          {tab === "timeline" && (
            <div style={card}>
              <div style={cardTitle}>Transaction History</div>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
                <thead>
                  <tr>
                    {["Tx Hash","Chain","Direction","Counterparty","Value (ETH)","Score","Status","Time"].map(h => (
                      <th key={h} style={{ textAlign: "left", color: "#4b5563", fontWeight: 600, padding: "6px 10px", borderBottom: "1px solid #1e2433" }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {mockTimeline.map(tx => (
                    <tr key={tx.tx_hash} style={{ borderBottom: "1px solid #0f1117" }}>
                      <td style={{ padding: "8px 10px", fontFamily: "monospace", color: "#6b7280" }}>{tx.tx_hash}</td>
                      <td style={{ padding: "8px 10px", color: "#9ca3af" }}>{tx.chain}</td>
                      <td style={{ padding: "8px 10px", color: tx.direction === "sent" ? "#fb923c" : "#4ade80" }}>
                        {tx.direction === "sent" ? "↑ Sent" : "↓ Recv"}
                      </td>
                      <td style={{ padding: "8px 10px", fontFamily: "monospace", color: "#6b7280" }}>{tx.counterparty}</td>
                      <td style={{ padding: "8px 10px", color: "#e2e8f0" }}>{tx.value_eth.toFixed(4)}</td>
                      <td style={{ padding: "8px 10px", color: tx.anomaly_score > 0.7 ? "#f87171" : "#4ade80" }}>
                        {(tx.anomaly_score * 100).toFixed(0)}%
                      </td>
                      <td style={{ padding: "8px 10px" }}>
                        {tx.flagged
                          ? <span style={{ color: "#f87171", fontSize: 10 }}>⚠ FLAGGED</span>
                          : <span style={{ color: "#374151", fontSize: 10 }}>OK</span>}
                      </td>
                      <td style={{ padding: "8px 10px", color: "#4b5563" }}>{new Date(tx.timestamp).toLocaleString()}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}

      {/* ── Empty state ── */}
      {!risk && !loading && !error && (
        <div style={{ border: "1px dashed #1e2433", borderRadius: 10, padding: 64, textAlign: "center", color: "#374151" }}>
          <div style={{ fontSize: 40, marginBottom: 12 }}>🏦</div>
          <div style={{ fontSize: 14 }}>Enter a wallet address above to begin investigation.</div>
        </div>
      )}
    </div>
  );
}

// ─── Shared styles ────────────────────────────────────────────

const card: React.CSSProperties = {
  background: "#0b0f1a", border: "1px solid #1a2035",
  borderRadius: 8, padding: 18,
};

const cardTitle: React.CSSProperties = {
  fontSize: 11, color: "#4b5563", textTransform: "uppercase",
  letterSpacing: 1, fontWeight: 700, marginBottom: 14,
};

const feedbackBtn: React.CSSProperties = {
  background: "transparent", border: "1px solid",
  borderRadius: 5, padding: "6px 14px", cursor: "pointer",
  fontSize: 12, fontFamily: "inherit",
};
