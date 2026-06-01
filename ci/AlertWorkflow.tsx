/**
 * AlertWorkflow.tsx
 * ──────────────────
 * Full alert lifecycle management page.
 *
 * Features:
 *  • Filterable alert list (status / severity / chain)
 *  • Detail drawer: tx info, wallet risk score, timeline of comments
 *  • Assign alert to analyst
 *  • Add freeform comments (persisted to DB via POST /alerts/:id/comment)
 *  • Close with structured resolution + note
 *  • Status badge progression: open → assigned → closed
 */

import { useState } from "react";

// ─── Types ───────────────────────────────────────────────────

type AlertStatus   = "open" | "assigned" | "closed";
type Severity      = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
type Resolution    = "confirmed_fraud" | "false_positive" | "escalated" | "monitoring";

interface Comment {
  id: number;
  analyst_id: string;
  text: string;
  created_at: string;
}

interface Alert {
  id: string;
  tx_hash: string;
  wallet: string;
  chain: string;
  severity: Severity;
  status: AlertStatus;
  score: number;
  rule_name?: string;
  assigned_to?: string | null;
  resolution?: Resolution | null;
  resolution_note?: string;
  comments: Comment[];
  created_at: string;
  updated_at: string;
}

// ─── Mock data ────────────────────────────────────────────────

const MOCK_ANALYSTS = [
  "alice@blockshield.io",
  "bob@blockshield.io",
  "carol@blockshield.io",
];

const MOCK_ALERTS: Alert[] = [
  { id: "ALT-001", tx_hash: "0xdead...1001", wallet: "0xaaa...111", chain: "ethereum", severity: "CRITICAL", status: "open",     score: 0.95, rule_name: "High Anomaly Score",     assigned_to: null,                  resolution: null, comments: [], created_at: "2025-05-01T11:50:00Z", updated_at: "2025-05-01T11:50:00Z" },
  { id: "ALT-002", tx_hash: "0xdead...1002", wallet: "0xbbb...222", chain: "polygon",  severity: "HIGH",     status: "assigned", score: 0.82, rule_name: "Mixer Interaction",       assigned_to: "alice@blockshield.io", resolution: null, comments: [{ id: 1, analyst_id: "alice@blockshield.io", text: "Looks like a Tornado Cash interaction. Investigating.", created_at: "2025-05-01T12:00:00Z" }], created_at: "2025-05-01T10:00:00Z", updated_at: "2025-05-01T12:00:00Z" },
  { id: "ALT-003", tx_hash: "0xdead...1003", wallet: "0xccc...333", chain: "ethereum", severity: "MEDIUM",   status: "closed",   score: 0.61, rule_name: "Burst Ratio Exceeded",   assigned_to: "bob@blockshield.io",  resolution: "false_positive", resolution_note: "Verified: MEV bot, not malicious.", comments: [], created_at: "2025-04-30T08:00:00Z", updated_at: "2025-05-01T09:00:00Z" },
  { id: "ALT-004", tx_hash: "0xdead...1004", wallet: "0xddd...444", chain: "arbitrum", severity: "HIGH",     status: "open",     score: 0.79, rule_name: "OFAC Proximity",          assigned_to: null,                  resolution: null, comments: [], created_at: "2025-05-01T13:00:00Z", updated_at: "2025-05-01T13:00:00Z" },
];

// ─── Style constants ──────────────────────────────────────────

const SEV_COLOR: Record<Severity, string> = { LOW: "#4ade80", MEDIUM: "#facc15", HIGH: "#fb923c", CRITICAL: "#f87171" };
const SEV_BG:    Record<Severity, string> = { LOW: "#052e16", MEDIUM: "#1c1400", HIGH: "#1c0a00", CRITICAL: "#1c0505" };

const STATUS_COLOR: Record<AlertStatus, string> = { open: "#3b82f6", assigned: "#fb923c", closed: "#4b5563" };

const RESOLUTION_LABELS: Record<Resolution, string> = {
  confirmed_fraud:  "🚨 Confirmed Fraud",
  false_positive:   "✅ False Positive",
  escalated:        "⬆ Escalated",
  monitoring:       "👁 Monitoring",
};

// ─── Sub-components ───────────────────────────────────────────

function SevBadge({ sev }: { sev: Severity }) {
  return (
    <span style={{ padding: "2px 8px", borderRadius: 4, fontSize: 10, fontWeight: 700, letterSpacing: 1, textTransform: "uppercase" as const, color: SEV_COLOR[sev], background: SEV_BG[sev], border: `1px solid ${SEV_COLOR[sev]}44` }}>
      {sev}
    </span>
  );
}

function StatusPill({ status }: { status: AlertStatus }) {
  const col = STATUS_COLOR[status];
  return (
    <span style={{ padding: "2px 10px", borderRadius: 10, fontSize: 10, fontWeight: 600, letterSpacing: 1, textTransform: "uppercase" as const, color: col, background: col + "18", border: `1px solid ${col}44` }}>
      {status}
    </span>
  );
}

// ─── Main ────────────────────────────────────────────────────

export default function AlertWorkflow() {
  const [alerts, setAlerts]         = useState<Alert[]>(MOCK_ALERTS);
  const [selected, setSelected]     = useState<Alert | null>(null);
  const [filterStatus, setFilterStatus] = useState<string>("all");
  const [filterSev, setFilterSev]   = useState<string>("all");
  const [newComment, setNewComment] = useState("");
  const [assignTo, setAssignTo]     = useState("");
  const [closeRes, setCloseRes]     = useState<Resolution | "">("");
  const [closeNote, setCloseNote]   = useState("");
  const [toast, setToast]           = useState<string | null>(null);

  const showToast = (msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(null), 2500);
  };

  const mutateAlert = (id: string, patch: Partial<Alert>) => {
    const updated = alerts.map(a => a.id === id ? { ...a, ...patch, updated_at: new Date().toISOString() } : a);
    setAlerts(updated);
    if (selected?.id === id) setSelected({ ...selected, ...patch });
  };

  // ── Actions ─────────────────────────────────────────────────

  const handleAssign = async () => {
    if (!selected || !assignTo) return;
    // await fetch(`/api/v1/alerts/${selected.id}/assign`, { method:"POST", body: JSON.stringify({ analyst_id: assignTo }) })
    mutateAlert(selected.id, { assigned_to: assignTo, status: "assigned" });
    showToast(`Assigned to ${assignTo}`);
    setAssignTo("");
  };

  const handleComment = async () => {
    if (!selected || !newComment.trim()) return;
    // await fetch(`/api/v1/alerts/${selected.id}/comment`, { method:"POST", body: JSON.stringify({ text: newComment }) })
    const comment: Comment = { id: Date.now(), analyst_id: "you@blockshield.io", text: newComment.trim(), created_at: new Date().toISOString() };
    mutateAlert(selected.id, { comments: [...selected.comments, comment] });
    setNewComment("");
    showToast("Comment added");
  };

  const handleClose = async () => {
    if (!selected || !closeRes) return;
    // await fetch(`/api/v1/alerts/${selected.id}/close`, { method:"POST", body: JSON.stringify({ resolution: closeRes, note: closeNote }) })
    mutateAlert(selected.id, { status: "closed", resolution: closeRes as Resolution, resolution_note: closeNote });
    showToast("Alert closed");
    setCloseRes("");
    setCloseNote("");
  };

  const filtered = alerts.filter(a =>
    (filterStatus === "all" || a.status === filterStatus) &&
    (filterSev    === "all" || a.severity === filterSev)
  );

  return (
    <div style={{ fontFamily: "'IBM Plex Mono', monospace", background: "#060810", color: "#c9d1d9", minHeight: "100vh", display: "flex", flexDirection: "column" }}>

      {/* Toast */}
      {toast && (
        <div style={{ position: "fixed", top: 16, right: 16, background: "#0b0f1a", border: "1px solid #3b82f6", borderRadius: 6, padding: "10px 18px", color: "#3b82f6", fontSize: 12, zIndex: 100 }}>
          ✓ {toast}
        </div>
      )}

      {/* Header */}
      <div style={{ padding: "24px 28px 0", borderBottom: "1px solid #1e2433" }}>
        <h1 style={{ margin: "0 0 12px", fontSize: 20, fontWeight: 700, color: "#e2e8f0" }}>⚡ Alert Workflow</h1>

        {/* Filters */}
        <div style={{ display: "flex", gap: 10, paddingBottom: 16 }}>
          {["all","open","assigned","closed"].map(s => (
            <button key={s} onClick={() => setFilterStatus(s)} style={{
              ...pillBtn,
              background: filterStatus === s ? "#1d4ed8" : "#0b0f1a",
              color: filterStatus === s ? "#fff" : "#6b7280",
              borderColor: filterStatus === s ? "#2563eb" : "#1e2433",
            }}>{s}</button>
          ))}
          <div style={{ flex: 1 }} />
          {["all","LOW","MEDIUM","HIGH","CRITICAL"].map(s => (
            <button key={s} onClick={() => setFilterSev(s)} style={{
              ...pillBtn,
              background: filterSev === s ? "#111827" : "transparent",
              color: s === "all" ? "#9ca3af" : (filterSev === s ? SEV_COLOR[s as Severity] : "#4b5563"),
              borderColor: s === "all" ? "#1e2433" : (filterSev === s ? SEV_COLOR[s as Severity] + "66" : "#1e2433"),
            }}>{s}</button>
          ))}
        </div>
      </div>

      {/* Body */}
      <div style={{ display: "flex", flex: 1, overflow: "hidden" }}>

        {/* Alert list */}
        <div style={{ width: 420, borderRight: "1px solid #1e2433", overflowY: "auto" as const, padding: 16 }}>
          {filtered.length === 0 && (
            <div style={{ textAlign: "center", color: "#374151", padding: 40 }}>No alerts match filters.</div>
          )}
          {filtered.map(a => (
            <div
              key={a.id}
              onClick={() => setSelected(a)}
              style={{
                border: `1px solid ${selected?.id === a.id ? "#2563eb" : "#1a2035"}`,
                borderRadius: 8, background: selected?.id === a.id ? "#0d1425" : "#0b0f1a",
                padding: "12px 14px", marginBottom: 8, cursor: "pointer",
                transition: "border-color 0.15s",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
                <span style={{ fontWeight: 600, color: "#e2e8f0", fontSize: 13 }}>{a.id}</span>
                <SevBadge sev={a.severity} />
                <StatusPill status={a.status} />
              </div>
              <div style={{ fontSize: 11, color: "#6b7280", marginBottom: 4 }}>
                {a.rule_name || "Manual Flag"} · {a.chain}
              </div>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span style={{ fontSize: 10, color: "#374151", fontFamily: "monospace" }}>{a.wallet}</span>
                <span style={{ fontSize: 10, color: a.score > 0.8 ? "#f87171" : "#6b7280" }}>
                  Score: {(a.score * 100).toFixed(0)}%
                </span>
              </div>
              {a.assigned_to && (
                <div style={{ fontSize: 10, color: "#4b5563", marginTop: 4 }}>→ {a.assigned_to}</div>
              )}
            </div>
          ))}
        </div>

        {/* Detail drawer */}
        {selected ? (
          <div style={{ flex: 1, overflowY: "auto" as const, padding: 24 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 20 }}>
              <h2 style={{ margin: 0, fontSize: 16, color: "#e2e8f0" }}>{selected.id}</h2>
              <SevBadge sev={selected.severity} />
              <StatusPill status={selected.status} />
            </div>

            {/* Tx / wallet info */}
            <div style={{ ...infoGrid, marginBottom: 20 }}>
              {[
                ["Tx Hash",    selected.tx_hash],
                ["Wallet",     selected.wallet],
                ["Chain",      selected.chain],
                ["Score",      `${(selected.score * 100).toFixed(0)}%`],
                ["Rule",       selected.rule_name || "—"],
                ["Assigned",   selected.assigned_to || "—"],
                ["Created",    new Date(selected.created_at).toLocaleString()],
                ["Updated",    new Date(selected.updated_at).toLocaleString()],
              ].map(([k, v]) => (
                <div key={k} style={{ background: "#060810", borderRadius: 6, padding: "8px 12px" }}>
                  <div style={{ fontSize: 10, color: "#4b5563", textTransform: "uppercase" as const, letterSpacing: 1 }}>{k}</div>
                  <div style={{ fontSize: 12, color: "#9ca3af", marginTop: 3, fontFamily: "monospace", wordBreak: "break-all" as const }}>{v}</div>
                </div>
              ))}
            </div>

            {/* Resolution badge (if closed) */}
            {selected.status === "closed" && selected.resolution && (
              <div style={{ background: "#0b0f1a", border: "1px solid #1a2035", borderRadius: 8, padding: "12px 16px", marginBottom: 20 }}>
                <div style={{ fontSize: 11, color: "#4b5563", textTransform: "uppercase" as const, letterSpacing: 1, marginBottom: 4 }}>Resolution</div>
                <div style={{ fontSize: 13, color: "#e2e8f0" }}>{RESOLUTION_LABELS[selected.resolution]}</div>
                {selected.resolution_note && (
                  <div style={{ fontSize: 12, color: "#6b7280", marginTop: 6, fontStyle: "italic" }}>"{selected.resolution_note}"</div>
                )}
              </div>
            )}

            {/* Actions (only for non-closed) */}
            {selected.status !== "closed" && (
              <div style={{ display: "flex", flexDirection: "column" as const, gap: 16, marginBottom: 24 }}>

                {/* Assign */}
                <div style={actionBox}>
                  <div style={actionTitle}>Assign Alert</div>
                  <div style={{ display: "flex", gap: 8 }}>
                    <select value={assignTo} onChange={e => setAssignTo(e.target.value)} style={selectStyle}>
                      <option value="">Select analyst…</option>
                      {MOCK_ANALYSTS.map(a => <option key={a} value={a}>{a}</option>)}
                    </select>
                    <button onClick={handleAssign} disabled={!assignTo} style={{ ...actionBtn, opacity: assignTo ? 1 : 0.4 }}>Assign</button>
                  </div>
                </div>

                {/* Close */}
                <div style={actionBox}>
                  <div style={actionTitle}>Close Alert</div>
                  <div style={{ display: "flex", gap: 8, marginBottom: 8 }}>
                    <select value={closeRes} onChange={e => setCloseRes(e.target.value as Resolution)} style={selectStyle}>
                      <option value="">Select resolution…</option>
                      {(Object.entries(RESOLUTION_LABELS) as [Resolution, string][]).map(([k, v]) => (
                        <option key={k} value={k}>{v}</option>
                      ))}
                    </select>
                    <button onClick={handleClose} disabled={!closeRes} style={{ ...actionBtn, background: "#7f1d1d", borderColor: "#f87171", opacity: closeRes ? 1 : 0.4 }}>Close</button>
                  </div>
                  <textarea
                    value={closeNote}
                    onChange={e => setCloseNote(e.target.value)}
                    placeholder="Optional resolution note…"
                    rows={2}
                    style={{ ...textAreaStyle, width: "100%" }}
                  />
                </div>
              </div>
            )}

            {/* Comment thread */}
            <div style={{ marginBottom: 16 }}>
              <div style={{ fontSize: 11, color: "#4b5563", textTransform: "uppercase" as const, letterSpacing: 1, marginBottom: 12 }}>
                Comments ({selected.comments.length})
              </div>
              {selected.comments.map(c => (
                <div key={c.id} style={{ background: "#060810", border: "1px solid #1a2035", borderRadius: 6, padding: "10px 14px", marginBottom: 8 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
                    <span style={{ fontSize: 11, color: "#3b82f6" }}>{c.analyst_id}</span>
                    <span style={{ fontSize: 10, color: "#374151" }}>{new Date(c.created_at).toLocaleString()}</span>
                  </div>
                  <p style={{ margin: 0, fontSize: 12, color: "#9ca3af" }}>{c.text}</p>
                </div>
              ))}
              {selected.comments.length === 0 && (
                <div style={{ fontSize: 12, color: "#374151" }}>No comments yet.</div>
              )}

              {/* Add comment */}
              <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
                <input
                  value={newComment}
                  onChange={e => setNewComment(e.target.value)}
                  onKeyDown={e => e.key === "Enter" && handleComment()}
                  placeholder="Add a comment… (Enter to submit)"
                  style={{ ...selectStyle, flex: 1 }}
                />
                <button onClick={handleComment} disabled={!newComment.trim()} style={{ ...actionBtn, opacity: newComment.trim() ? 1 : 0.4 }}>Post</button>
              </div>
            </div>
          </div>
        ) : (
          <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", color: "#374151" }}>
            <div style={{ textAlign: "center" }}>
              <div style={{ fontSize: 32, marginBottom: 8 }}>↖</div>
              Select an alert to view details.
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ─── Shared styles ────────────────────────────────────────────

const pillBtn: React.CSSProperties = {
  padding: "4px 12px", borderRadius: 4, border: "1px solid",
  cursor: "pointer", fontSize: 11, fontFamily: "inherit",
  fontWeight: 600, letterSpacing: 0.5, textTransform: "capitalize" as const,
};

const actionBox: React.CSSProperties = {
  background: "#0b0f1a", border: "1px solid #1a2035", borderRadius: 8, padding: "14px 16px",
};

const actionTitle: React.CSSProperties = {
  fontSize: 11, color: "#4b5563", textTransform: "uppercase" as const, letterSpacing: 1, fontWeight: 700, marginBottom: 10,
};

const actionBtn: React.CSSProperties = {
  background: "#1d4ed8", color: "#fff", border: "1px solid #2563eb",
  borderRadius: 5, padding: "7px 16px", cursor: "pointer",
  fontSize: 12, fontFamily: "inherit", fontWeight: 600, whiteSpace: "nowrap" as const,
};

const selectStyle: React.CSSProperties = {
  background: "#060810", color: "#c9d1d9", border: "1px solid #1e2433",
  borderRadius: 5, padding: "7px 10px", fontSize: 12, fontFamily: "inherit", outline: "none", flex: 1,
};

const textAreaStyle: React.CSSProperties = {
  background: "#060810", color: "#c9d1d9", border: "1px solid #1e2433",
  borderRadius: 5, padding: "8px 10px", fontSize: 12, fontFamily: "inherit",
  outline: "none", resize: "vertical" as const,
};

const infoGrid: React.CSSProperties = {
  display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8,
};
