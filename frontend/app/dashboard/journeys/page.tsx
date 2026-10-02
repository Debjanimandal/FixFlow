"use client";

import { useEffect, useState, useCallback } from "react";
import {
  journeys as journeysApi,
  type Journey,
  type JourneyRun,
} from "@/lib/api-client";

const STATUS_COLORS: Record<string, { bg: string; text: string; border: string; dot: string }> = {
  healthy: { bg: "#0f2a1a", text: "#4ade80", border: "#166534", dot: "#22c55e" },
  failing: { bg: "#2a0f0f", text: "#f87171", border: "#991b1b", dot: "#ef4444" },
  unknown: { bg: "#1a1a1a", text: "#9ca3af", border: "#374151", dot: "#6b7280" },
  disabled: { bg: "#111111", text: "#4b5563", border: "#1f2937", dot: "#374151" },
};

const RUN_STATUS_COLORS: Record<string, { bg: string; text: string }> = {
  passed: { bg: "#0f2a1a", text: "#4ade80" },
  failed: { bg: "#2a0f0f", text: "#f87171" },
  running: { bg: "#0f1a2a", text: "#60a5fa" },
  timeout: { bg: "#2a1a0f", text: "#fdba74" },
  error: { bg: "#2a0f0f", text: "#f87171" },
};

const inputStyle: React.CSSProperties = {
  width: "100%",
  padding: "0.5rem",
  borderRadius: 6,
  border: "1px solid #374151",
  background: "#0f172a",
  color: "#f1f5f9",
  fontSize: "0.875rem",
  boxSizing: "border-box",
};

export default function JourneysPage() {
  const [journeyList, setJourneyList] = useState<Journey[]>([]);
  const [selectedJourney, setSelectedJourney] = useState<Journey | null>(null);
  const [runs, setRuns] = useState<JourneyRun[]>([]);
  const [selectedRun, setSelectedRun] = useState<JourneyRun | null>(null);
  const [loading, setLoading] = useState(true);
  const [runningJourney, setRunningJourney] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [newJourney, setNewJourney] = useState({
    name: "",
    base_url: "",
    description: "",
    failure_threshold: 2,
    timeout_ms: 10000,
    steps: [{ name: "Homepage", method: "GET", path: "/", expected_status: 200 }],
  });
  const [createError, setCreateError] = useState<string | null>(null);

  const refresh = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    try {
      const list = await journeysApi.list();
      setJourneyList(list);
    } catch {
      // silent failure
    } finally {
      if (!silent) setLoading(false);
    }
  }, []);

  const loadRuns = useCallback(async (journeyId: string) => {
    try {
      const r = await journeysApi.listRuns(journeyId, 20);
      setRuns(r);
    } catch {
      setRuns([]);
    }
  }, []);

  useEffect(() => {
    refresh();
    const t = setInterval(() => refresh(true), 15000);
    return () => clearInterval(t);
  }, [refresh]);

  useEffect(() => {
    if (selectedJourney) {
      loadRuns(selectedJourney.id);
      const t = setInterval(() => loadRuns(selectedJourney.id), 10000);
      return () => clearInterval(t);
    }
  }, [selectedJourney, loadRuns]);

  const handleRunNow = async (journey: Journey) => {
    setRunningJourney(journey.id);
    try {
      await journeysApi.runNow(journey.id);
      setTimeout(() => {
        loadRuns(journey.id);
        refresh(true);
      }, 2000);
    } catch {
      // show error
    } finally {
      setTimeout(() => setRunningJourney(null), 3000);
    }
  };

  const handleToggleEnabled = async (journey: Journey) => {
    try {
      await journeysApi.update(journey.id, { enabled: !journey.enabled });
      await refresh(true);
    } catch {}
  };

  const handleDelete = async (journey: Journey) => {
    if (!confirm(`Delete journey "${journey.name}"?`)) return;
    try {
      await journeysApi.delete(journey.id);
      setSelectedJourney(null);
      setRuns([]);
      await refresh(true);
    } catch {}
  };

  const handleCreate = async () => {
    setCreateError(null);
    if (!newJourney.name) { setCreateError("Name is required."); return; }
    if (!newJourney.base_url) { setCreateError("Base URL is required."); return; }
    try {
      await journeysApi.create({
        name: newJourney.name,
        description: newJourney.description || undefined,
        base_url: newJourney.base_url,
        failure_threshold: newJourney.failure_threshold,
        timeout_ms: newJourney.timeout_ms,
        steps: newJourney.steps,
        enabled: true,
        severity: "high",
      });
      setShowCreate(false);
      setNewJourney({ name: "", base_url: "", description: "", failure_threshold: 2, timeout_ms: 10000, steps: [{ name: "Homepage", method: "GET", path: "/", expected_status: 200 }] });
      await refresh();
    } catch (e) {
      setCreateError(String(e));
    }
  };

  const healthyCount = journeyList.filter((j) => j.current_status === "healthy").length;
  const failingCount = journeyList.filter((j) => j.current_status === "failing").length;

  if (loading) {
    return <div style={{ padding: "2rem", color: "#9ca3af", textAlign: "center" }}><div style={{ fontSize: "2rem", marginBottom: "1rem" }}>🔍</div>Loading journeys...</div>;
  }

  return (
    <div style={{ padding: "2rem 2.5rem", maxWidth: 1400 }}>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "1.5rem" }}>
        <div>
          <h1 style={{ margin: 0, color: "#f1f5f9", fontSize: "1.5rem", fontWeight: 700 }}>🔍 Synthetic Journeys</h1>
          <p style={{ margin: "0.25rem 0 0", color: "#6b7280", fontSize: "0.875rem" }}>
            Proactive health checks that simulate user flows against your deployed app.
          </p>
        </div>
        <div style={{ display: "flex", gap: "1rem", alignItems: "center" }}>
          <div style={{ display: "flex", gap: "0.5rem" }}>
            <span style={{ fontSize: "0.8rem", color: "#4ade80" }}>✅ {healthyCount} healthy</span>
            {failingCount > 0 && <span style={{ fontSize: "0.8rem", color: "#f87171" }}>❌ {failingCount} failing</span>}
          </div>
          <button
            onClick={() => setShowCreate(true)}
            style={{ padding: "0.5rem 1rem", borderRadius: 8, border: "1px solid #7c3aed", background: "linear-gradient(135deg, #7c3aed, #4f46e5)", color: "#fff", cursor: "pointer", fontSize: "0.875rem", fontWeight: 600 }}
          >
            + New Journey
          </button>
        </div>
      </div>

      <div style={{ display: "flex", gap: "1.5rem" }}>
        {/* Journey list */}
        <div style={{ width: 340, flexShrink: 0 }}>
          <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
            {journeyList.length === 0 ? (
              <div style={{ padding: "2rem", borderRadius: 12, border: "1px dashed #374151", textAlign: "center", color: "#6b7280" }}>
                <div style={{ fontSize: "2rem", marginBottom: "0.5rem" }}>🔍</div>
                <div style={{ marginBottom: "0.5rem" }}>No journeys configured.</div>
                <div style={{ fontSize: "0.8rem", color: "#4b5563" }}>Create a journey to start proactive monitoring.</div>
              </div>
            ) : (
              journeyList.map((journey) => {
                const colors = STATUS_COLORS[journey.current_status] ?? STATUS_COLORS.unknown;
                const isSelected = selectedJourney?.id === journey.id;
                return (
                  <div
                    key={journey.id}
                    onClick={() => { setSelectedJourney(journey); setSelectedRun(null); loadRuns(journey.id); }}
                    style={{ padding: "0.875rem 1rem", borderRadius: 10, border: `1px solid ${isSelected ? "#7c3aed" : colors.border}`, background: isSelected ? "#1a0f2a" : colors.bg, cursor: "pointer", transition: "all 0.15s", outline: isSelected ? "2px solid #7c3aed40" : "none" }}
                  >
                    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "0.5rem" }}>
                      <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                        <div style={{ width: 8, height: 8, borderRadius: "50%", backgroundColor: colors.dot, flexShrink: 0, boxShadow: journey.current_status === "healthy" ? "0 0 6px #22c55e80" : journey.current_status === "failing" ? "0 0 6px #ef444480" : "none" }} />
                        <span style={{ color: "#f1f5f9", fontWeight: 600, fontSize: "0.9rem" }}>{journey.name}</span>
                      </div>
                      <span style={{ fontSize: "0.65rem", fontWeight: 700, padding: "2px 6px", borderRadius: 4, background: colors.bg, color: colors.text, border: `1px solid ${colors.border}`, textTransform: "uppercase" }}>
                        {journey.current_status}
                      </span>
                    </div>
                    <div style={{ display: "flex", gap: "1rem", fontSize: "0.75rem", color: "#6b7280" }}>
                      <span>{journey.steps.length} steps</span>
                      {journey.consecutive_failures > 0 && <span style={{ color: "#f87171" }}>{journey.consecutive_failures} consecutive failures</span>}
                      {journey.last_run_at && <span>Last: {timeAgo(journey.last_run_at)}</span>}
                    </div>
                    {journey.base_url && (
                      <div style={{ fontSize: "0.7rem", color: "#4b5563", marginTop: 2, fontFamily: "monospace", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                        {journey.base_url}
                      </div>
                    )}
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* Right panel */}
        <div style={{ flex: 1, minWidth: 0 }}>
          {selectedJourney ? (
            <JourneyDetail
              journey={selectedJourney}
              runs={runs}
              selectedRun={selectedRun}
              onSelectRun={setSelectedRun}
              onRunNow={handleRunNow}
              onToggle={handleToggleEnabled}
              onDelete={handleDelete}
              runningId={runningJourney}
            />
          ) : (
            <div style={{ textAlign: "center", padding: "4rem 2rem", color: "#6b7280" }}>
              <div style={{ fontSize: "3rem", marginBottom: "1rem" }}>🔍</div>
              <div style={{ fontSize: "1rem" }}>Select a journey to view details</div>
            </div>
          )}
        </div>
      </div>

      {/* Create modal */}
      {showCreate && (
        <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.8)", zIndex: 1000, display: "flex", alignItems: "center", justifyContent: "center" }}
          onClick={(e) => { if (e.target === e.currentTarget) setShowCreate(false); }}>
          <div style={{ background: "#0d1117", border: "1px solid #1f2937", borderRadius: 16, padding: "2rem", width: 520, maxHeight: "80vh", overflowY: "auto" }}>
            <h2 style={{ margin: "0 0 1.5rem", color: "#f1f5f9", fontSize: "1.1rem" }}>➕ Create Journey</h2>
            {createError && <div style={{ color: "#f87171", fontSize: "0.85rem", marginBottom: "1rem", padding: "0.5rem", background: "#2a0f0f", borderRadius: 6 }}>{createError}</div>}
            <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
              <FormField label="Name" value={newJourney.name} onChange={(v) => setNewJourney({ ...newJourney, name: v })} placeholder="e.g. Homepage Health Check" required />
              <FormField label="Base URL" value={newJourney.base_url} onChange={(v) => setNewJourney({ ...newJourney, base_url: v })} placeholder="https://your-app.vercel.app" required />
              <FormField label="Description (optional)" value={newJourney.description} onChange={(v) => setNewJourney({ ...newJourney, description: v })} placeholder="Checks critical user flows" />
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.75rem" }}>
                <div>
                  <label style={{ display: "block", fontSize: "0.75rem", color: "#9ca3af", marginBottom: 4 }}>Failure Threshold</label>
                  <input type="number" value={newJourney.failure_threshold} min={1} max={10} onChange={(e) => setNewJourney({ ...newJourney, failure_threshold: Number(e.target.value) })} style={inputStyle} />
                </div>
                <div>
                  <label style={{ display: "block", fontSize: "0.75rem", color: "#9ca3af", marginBottom: 4 }}>Timeout (ms)</label>
                  <input type="number" value={newJourney.timeout_ms} step={1000} onChange={(e) => setNewJourney({ ...newJourney, timeout_ms: Number(e.target.value) })} style={inputStyle} />
                </div>
              </div>
              <div>
                <div style={{ fontSize: "0.75rem", color: "#9ca3af", marginBottom: 6, display: "flex", justifyContent: "space-between" }}>
                  <span>Steps</span>
                  <button onClick={() => setNewJourney({ ...newJourney, steps: [...newJourney.steps, { name: `Step ${newJourney.steps.length + 1}`, method: "GET", path: "/", expected_status: 200 }] })} style={{ background: "none", border: "none", color: "#7c3aed", cursor: "pointer", fontSize: "0.75rem" }}>+ Add Step</button>
                </div>
                {newJourney.steps.map((step, i) => (
                  <div key={i} style={{ display: "grid", gridTemplateColumns: "2fr 1fr 3fr 1fr auto", gap: "0.5rem", marginBottom: "0.5rem", alignItems: "center" }}>
                    <input value={step.name} onChange={(e) => { const s = [...newJourney.steps]; s[i] = { ...s[i], name: e.target.value }; setNewJourney({ ...newJourney, steps: s }); }} placeholder="Step name" style={inputStyle} />
                    <select value={step.method} onChange={(e) => { const s = [...newJourney.steps]; s[i] = { ...s[i], method: e.target.value }; setNewJourney({ ...newJourney, steps: s }); }} style={inputStyle}>
                      {["GET", "POST", "PUT", "DELETE", "PATCH"].map((m) => <option key={m}>{m}</option>)}
                    </select>
                    <input value={step.path} onChange={(e) => { const s = [...newJourney.steps]; s[i] = { ...s[i], path: e.target.value }; setNewJourney({ ...newJourney, steps: s }); }} placeholder="/api/health" style={inputStyle} />
                    <input type="number" value={step.expected_status} onChange={(e) => { const s = [...newJourney.steps]; s[i] = { ...s[i], expected_status: Number(e.target.value) }; setNewJourney({ ...newJourney, steps: s }); }} placeholder="200" style={inputStyle} />
                    <button onClick={() => setNewJourney({ ...newJourney, steps: newJourney.steps.filter((_, idx) => idx !== i) })} style={{ background: "none", border: "none", color: "#f87171", cursor: "pointer", fontSize: "1rem" }} disabled={newJourney.steps.length <= 1}>✕</button>
                  </div>
                ))}
              </div>
            </div>
            <div style={{ display: "flex", gap: "0.75rem", marginTop: "1.5rem" }}>
              <button onClick={handleCreate} style={{ flex: 1, padding: "0.6rem", borderRadius: 8, border: "none", background: "linear-gradient(135deg, #7c3aed, #4f46e5)", color: "#fff", cursor: "pointer", fontWeight: 600 }}>Create Journey</button>
              <button onClick={() => setShowCreate(false)} style={{ padding: "0.6rem 1rem", borderRadius: 8, border: "1px solid #374151", background: "none", color: "#9ca3af", cursor: "pointer" }}>Cancel</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function JourneyDetail({ journey, runs, selectedRun, onSelectRun, onRunNow, onToggle, onDelete, runningId }: {
  journey: Journey; runs: JourneyRun[]; selectedRun: JourneyRun | null;
  onSelectRun: (r: JourneyRun | null) => void; onRunNow: (j: Journey) => void;
  onToggle: (j: Journey) => void; onDelete: (j: Journey) => void; runningId: string | null;
}) {
  const colors = STATUS_COLORS[journey.current_status] ?? STATUS_COLORS.unknown;
  const isRunning = runningId === journey.id;
  return (
    <div>
      <div style={{ padding: "1.25rem 1.5rem", borderRadius: 12, border: `1px solid ${colors.border}`, background: colors.bg, marginBottom: "1.5rem" }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "0.75rem" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
            <div style={{ width: 12, height: 12, borderRadius: "50%", backgroundColor: colors.dot, boxShadow: journey.current_status === "healthy" ? "0 0 8px #22c55e80" : journey.current_status === "failing" ? "0 0 8px #ef444480" : "none" }} />
            <div>
              <div style={{ color: "#f1f5f9", fontWeight: 700, fontSize: "1.1rem" }}>{journey.name}</div>
              {journey.description && <div style={{ color: "#6b7280", fontSize: "0.8rem" }}>{journey.description}</div>}
            </div>
          </div>
          <div style={{ display: "flex", gap: "0.5rem" }}>
            <button onClick={() => onToggle(journey)} style={{ padding: "0.4rem 0.75rem", borderRadius: 6, border: "1px solid #374151", background: "none", color: journey.enabled ? "#facc15" : "#4ade80", cursor: "pointer", fontSize: "0.8rem" }}>
              {journey.enabled ? "⏸ Disable" : "▶ Enable"}
            </button>
            <button onClick={() => onRunNow(journey)} disabled={!journey.enabled || isRunning} style={{ padding: "0.4rem 0.75rem", borderRadius: 6, border: "1px solid #7c3aed", background: isRunning ? "#1a1a2e" : "#7c3aed20", color: "#a78bfa", cursor: journey.enabled && !isRunning ? "pointer" : "not-allowed", fontSize: "0.8rem", fontWeight: 600 }}>
              {isRunning ? "⏳ Running..." : "▶ Run Now"}
            </button>
            <button onClick={() => onDelete(journey)} style={{ padding: "0.4rem 0.75rem", borderRadius: 6, border: "1px solid #991b1b", background: "none", color: "#f87171", cursor: "pointer", fontSize: "0.8rem" }}>🗑</button>
          </div>
        </div>
        <div style={{ display: "flex", gap: "1.5rem", fontSize: "0.8rem" }}>
          {journey.base_url && <span style={{ color: "#6b7280", fontFamily: "monospace" }}>{journey.base_url}</span>}
          <span style={{ color: "#6b7280" }}>{journey.steps.length} steps</span>
          <span style={{ color: "#6b7280" }}>threshold: {journey.failure_threshold}</span>
        </div>
      </div>

      {/* Steps */}
      <div style={{ marginBottom: "1.5rem" }}>
        <div style={{ fontSize: "0.75rem", fontWeight: 700, color: "#6b7280", textTransform: "uppercase", letterSpacing: "0.1em", marginBottom: "0.75rem" }}>Journey Steps</div>
        <div style={{ display: "flex", flexDirection: "column", gap: "0.4rem" }}>
          {journey.steps.map((step, i) => (
            <div key={i} style={{ display: "flex", alignItems: "center", gap: "0.75rem", padding: "0.5rem 0.75rem", borderRadius: 6, background: "#0f172a", border: "1px solid #1f2937", fontSize: "0.8rem" }}>
              <span style={{ color: "#6b7280", width: 20, textAlign: "right" }}>{i + 1}.</span>
              <span style={{ padding: "2px 6px", borderRadius: 4, background: "#1a2a3a", color: "#60a5fa", fontFamily: "monospace", fontSize: "0.7rem", fontWeight: 700 }}>{step.method}</span>
              <span style={{ flex: 1, color: "#9ca3af", fontFamily: "monospace" }}>{step.path}</span>
              <span style={{ color: "#6b7280" }}>→ <span style={{ color: "#4ade80" }}>{step.expected_status}</span></span>
              <span style={{ color: "#4b5563" }}>{step.name}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Run history */}
      <div>
        <div style={{ fontSize: "0.75rem", fontWeight: 700, color: "#6b7280", textTransform: "uppercase", letterSpacing: "0.1em", marginBottom: "0.75rem" }}>Run History</div>
        {runs.length === 0 ? (
          <div style={{ color: "#4b5563", fontSize: "0.8rem" }}>No runs yet. Click "Run Now" to execute this journey.</div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: "0.4rem" }}>
            {runs.map((run) => {
              const rc = RUN_STATUS_COLORS[run.status] ?? { bg: "#1a1a1a", text: "#9ca3af" };
              const isSelected = selectedRun?.id === run.id;
              return (
                <div key={run.id}>
                  <div onClick={() => onSelectRun(isSelected ? null : run)} style={{ display: "flex", alignItems: "center", gap: "0.75rem", padding: "0.5rem 0.75rem", borderRadius: 6, background: isSelected ? "#1a0f2a" : rc.bg, border: `1px solid ${isSelected ? "#7c3aed" : "#1f2937"}`, cursor: "pointer", fontSize: "0.8rem" }}>
                    <span style={{ width: 6, height: 6, borderRadius: "50%", backgroundColor: rc.text, flexShrink: 0 }} />
                    <span style={{ color: rc.text, fontWeight: 700, textTransform: "uppercase", fontSize: "0.7rem", width: 60 }}>{run.status}</span>
                    <span style={{ color: "#6b7280", flex: 1 }}>{new Date(run.started_at).toLocaleString()}</span>
                    <span style={{ color: "#6b7280" }}>{run.trigger}</span>
                    {run.duration_ms && <span style={{ color: "#4b5563" }}>{run.duration_ms}ms</span>}
                    {run.failing_step && <span style={{ color: "#f87171", fontFamily: "monospace", fontSize: "0.7rem" }}>✗ {run.failing_step}</span>}
                  </div>
                  {isSelected && run.step_results && (
                    <div style={{ marginTop: 2, padding: "0.75rem", borderRadius: 6, background: "#0a0d14", border: "1px solid #1f2937" }}>
                      {run.error && <div style={{ color: "#f87171", fontSize: "0.8rem", marginBottom: "0.5rem", fontFamily: "monospace" }}>Error: {run.error}</div>}
                      {run.step_results.map((step, i) => (
                        <div key={i} style={{ display: "flex", gap: "0.5rem", alignItems: "center", padding: "0.3rem 0", borderBottom: i < (run.step_results?.length ?? 0) - 1 ? "1px solid #1a1a2e" : "none", fontSize: "0.75rem" }}>
                          <span>{step.passed ? "✅" : "❌"}</span>
                          <span style={{ color: "#60a5fa", fontFamily: "monospace", fontSize: "0.7rem" }}>{step.method}</span>
                          <span style={{ flex: 1, color: "#9ca3af", fontFamily: "monospace" }}>{step.path}</span>
                          {step.actual_status && <span style={{ color: step.passed ? "#4ade80" : "#f87171" }}>{step.actual_status}</span>}
                          <span style={{ color: "#4b5563" }}>{step.duration_ms}ms</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

function FormField({ label, value, onChange, placeholder, required }: { label: string; value: string; onChange: (v: string) => void; placeholder?: string; required?: boolean }) {
  return (
    <div>
      <label style={{ display: "block", fontSize: "0.75rem", color: "#9ca3af", marginBottom: 4 }}>
        {label} {required && <span style={{ color: "#ef4444" }}>*</span>}
      </label>
      <input value={value} onChange={(e) => onChange(e.target.value)} placeholder={placeholder} style={inputStyle} />
    </div>
  );
}

function timeAgo(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}
