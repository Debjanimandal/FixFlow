"use client";

import { useEffect, useState, useCallback } from "react";
import { use } from "react";
import {
  arena as arenaApi,
  incidents as incidentsApi,
  patches as patchesApi,
  type PatchCandidate,
  type RepairProof,
  type TimelineEvent,
  type IncidentDetail,
  type Patch,
} from "@/lib/api-client";
import { STATUS_LABELS, SEVERITY_LABELS } from "@/lib/design-tokens";

interface Props {
  params: Promise<{ id: string }>;
}

const STRATEGY_LABELS: Record<string, string> = {
  minimal_diff: "Minimal Diff",
  defensive: "Defensive Guard",
  dependency_update: "Dependency Fix",
  refactor: "Refactor",
  configuration_fix: "Config Fix",
};

const STRATEGY_ICONS: Record<string, string> = {
  minimal_diff: "⚡",
  defensive: "🛡️",
  dependency_update: "📦",
  refactor: "♻️",
  configuration_fix: "⚙️",
};

const STATUS_COLORS: Record<string, { bg: string; text: string; border: string }> = {
  eligible: { bg: "#0f2a1a", text: "#4ade80", border: "#166534" },
  selected: { bg: "#0f2a1a", text: "#22c55e", border: "#15803d" },
  generating: { bg: "#1a1a0f", text: "#facc15", border: "#854d0e" },
  generated: { bg: "#0f1a2a", text: "#60a5fa", border: "#1e40af" },
  sandbox_running: { bg: "#0f1a2a", text: "#93c5fd", border: "#1d4ed8" },
  discarded: { bg: "#2a0f0f", text: "#f87171", border: "#991b1b" },
  pr_created: { bg: "#1a0f2a", text: "#c084fc", border: "#7e22ce" },
};

function candidateColor(status: string) {
  return STATUS_COLORS[status] ?? { bg: "#1a1a1a", text: "#9ca3af", border: "#374151" };
}

function EvidenceBadge({ label }: { label: string }) {
  const colors: Record<string, { bg: string; text: string }> = {
    observed: { bg: "#1a2a0f", text: "#86efac" },
    correlated: { bg: "#0f1a2a", text: "#93c5fd" },
    inferred: { bg: "#2a1a0f", text: "#fdba74" },
    synthetic: { bg: "#1a0f2a", text: "#c084fc" },
    validated: { bg: "#0f2a1a", text: "#4ade80" },
  };
  const c = colors[label.toLowerCase()] ?? { bg: "#1a1a1a", text: "#9ca3af" };
  return (
    <span
      style={{
        fontSize: "0.65rem",
        fontWeight: 700,
        letterSpacing: "0.05em",
        padding: "2px 6px",
        borderRadius: 4,
        backgroundColor: c.bg,
        color: c.text,
        textTransform: "uppercase",
        fontFamily: "monospace",
      }}
    >
      [{label.toUpperCase()}]
    </span>
  );
}

function GateCheck({ passed, label }: { passed: boolean | null; label: string }) {
  const icon = passed === true ? "✅" : passed === false ? "❌" : "⏳";
  const color = passed === true ? "#4ade80" : passed === false ? "#f87171" : "#9ca3af";
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: "0.8rem" }}>
      <span>{icon}</span>
      <span style={{ color }}>{label}</span>
    </div>
  );
}

export default function PatchArenaPage({ params }: Props) {
  const { id } = use(params);
  const [incident, setIncident] = useState<IncidentDetail | null>(null);
  const [candidates, setCandidates] = useState<PatchCandidate[]>([]);
  const [selectedCandidate, setSelectedCandidate] = useState<string | null>(null);
  const [proof, setProof] = useState<RepairProof | null>(null);
  const [timeline, setTimeline] = useState<TimelineEvent[]>([]);
  const [patches, setPatches] = useState<Patch[]>([]);
  const [loading, setLoading] = useState(true);
  const [arenaRunning, setArenaRunning] = useState(false);
  const [approvingPR, setApprovingPR] = useState(false);
  const [activePanel, setActivePanel] = useState<"arena" | "proof" | "timeline">("arena");
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    try {
      const [inc, cands, tl, patList] = await Promise.all([
        incidentsApi.get(id),
        arenaApi.getCandidates(id).catch(() => [] as PatchCandidate[]),
        arenaApi.getTimeline(id).catch(() => [] as TimelineEvent[]),
        incidentsApi.listPatches(id).catch(() => [] as Patch[]),
      ]);
      setIncident(inc);
      setCandidates(cands);
      setTimeline(tl);
      setPatches(patList);

      // Auto-select the selected candidate
      const sel = cands.find((c) => c.is_selected);
      if (sel && !selectedCandidate) {
        setSelectedCandidate(sel.candidate_id);
        loadProof(id, sel.candidate_id);
      }
    } catch (e) {
      if (!silent) setError(String(e));
    } finally {
      if (!silent) setLoading(false);
    }
  }, [id, selectedCandidate]);

  const loadProof = async (incId: string, candidateId: string) => {
    try {
      const p = await arenaApi.getVerificationProof(incId, candidateId);
      setProof(p);
    } catch {
      setProof(null);
    }
  };

  useEffect(() => {
    refresh();
    const t = setInterval(() => refresh(true), 8000);
    return () => clearInterval(t);
  }, [refresh]);

  const handleSelectCandidate = async (candidateId: string) => {
    setSelectedCandidate(candidateId);
    setActivePanel("proof");
    await loadProof(id, candidateId);
  };

  const handleTriggerArena = async () => {
    setArenaRunning(true);
    setError(null);
    try {
      await arenaApi.triggerArena(id);
      setTimeout(() => refresh(true), 3000);
    } catch (e) {
      setError(`Arena failed: ${String(e)}`);
    } finally {
      setArenaRunning(false);
    }
  };

  const handleApprovePR = async () => {
    if (!proof?.candidate_id) return;
    setApprovingPR(true);
    try {
      // Find the legacy patch for this candidate or use candidate approve endpoint
      const legacyPatch = patches[0];
      if (legacyPatch) {
        await patchesApi.approve(legacyPatch.id, true);
        await refresh(true);
      }
    } catch (e) {
      setError(`Approval failed: ${String(e)}`);
    } finally {
      setApprovingPR(false);
    }
  };

  if (loading) {
    return (
      <div style={{ padding: "2rem", color: "#9ca3af", textAlign: "center" }}>
        <div style={{ fontSize: "2rem", marginBottom: "1rem" }}>⚡</div>
        Loading Patch Arena...
      </div>
    );
  }

  if (!incident) {
    return (
      <div style={{ padding: "2rem", color: "#f87171" }}>
        Incident not found.
      </div>
    );
  }

  const selectedCandidateObj = candidates.find((c) => c.candidate_id === selectedCandidate);

  return (
    <div style={{ height: "calc(100vh - 4rem)", display: "flex", flexDirection: "column", overflow: "hidden" }}>
      {/* ── Header ─────────────────────────────────────────────────────────────── */}
      <div
        style={{
          padding: "1rem 1.5rem",
          borderBottom: "1px solid #1f2937",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          background: "linear-gradient(135deg, #0f172a 0%, #1a1a2e 100%)",
          flexShrink: 0,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "1rem" }}>
          <a
            href={`/dashboard/incidents/${id}`}
            style={{ color: "#6b7280", textDecoration: "none", fontSize: "0.85rem" }}
          >
            ← Back to Incident
          </a>
          <div style={{ color: "#374151" }}>|</div>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
              <span style={{ fontSize: "1.2rem" }}>⚔️</span>
              <span style={{ color: "#f1f5f9", fontWeight: 700, fontSize: "1.1rem" }}>
                Patch Arena
              </span>
              <span style={{ fontSize: "0.75rem", color: "#6b7280" }}>
                {candidates.length} candidate{candidates.length !== 1 ? "s" : ""}
              </span>
            </div>
            <div style={{ color: "#6b7280", fontSize: "0.8rem", marginTop: 2 }}>
              {incident.title.slice(0, 80)}
            </div>
          </div>
        </div>
        <div style={{ display: "flex", gap: "0.75rem", alignItems: "center" }}>
          {error && (
            <span style={{ color: "#f87171", fontSize: "0.8rem" }}>{error}</span>
          )}
          <button
            onClick={handleTriggerArena}
            disabled={arenaRunning}
            style={{
              padding: "0.5rem 1rem",
              borderRadius: 8,
              border: "1px solid #7c3aed",
              background: arenaRunning ? "#1a1a2e" : "linear-gradient(135deg, #7c3aed, #4f46e5)",
              color: "#fff",
              cursor: arenaRunning ? "not-allowed" : "pointer",
              fontSize: "0.85rem",
              fontWeight: 600,
            }}
          >
            {arenaRunning ? "⏳ Running..." : "⚡ Run Arena"}
          </button>
          {proof?.is_verified && (
            <button
              onClick={handleApprovePR}
              disabled={approvingPR}
              style={{
                padding: "0.5rem 1rem",
                borderRadius: 8,
                border: "1px solid #22c55e",
                background: approvingPR ? "#0f2a1a" : "linear-gradient(135deg, #16a34a, #15803d)",
                color: "#fff",
                cursor: approvingPR ? "not-allowed" : "pointer",
                fontSize: "0.85rem",
                fontWeight: 600,
              }}
            >
              {approvingPR ? "⏳ Creating PR..." : "✅ Approve → Create PR"}
            </button>
          )}
        </div>
      </div>

      {/* ── Three-panel layout ────────────────────────────────────────────────── */}
      <div style={{ display: "flex", flex: 1, overflow: "hidden" }}>
        {/* Panel 1: Timeline (Left) */}
        <div
          style={{
            width: 260,
            flexShrink: 0,
            borderRight: "1px solid #1f2937",
            overflowY: "auto",
            padding: "1rem",
            background: "#0b0f1a",
          }}
        >
          <div
            style={{
              fontSize: "0.75rem",
              fontWeight: 700,
              color: "#6b7280",
              letterSpacing: "0.1em",
              textTransform: "uppercase",
              marginBottom: "0.75rem",
            }}
          >
            Incident Timeline
          </div>
          {timeline.length === 0 ? (
            <div style={{ color: "#374151", fontSize: "0.8rem" }}>No events yet.</div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 0 }}>
              {timeline.map((event, i) => (
                <div key={event.id} style={{ display: "flex", gap: "0.5rem" }}>
                  <div style={{ display: "flex", flexDirection: "column", alignItems: "center", width: 20 }}>
                    <div
                      style={{
                        width: 8,
                        height: 8,
                        borderRadius: "50%",
                        backgroundColor: getEventColor(event.action),
                        marginTop: 4,
                        flexShrink: 0,
                      }}
                    />
                    {i < timeline.length - 1 && (
                      <div style={{ width: 1, flex: 1, backgroundColor: "#1f2937", minHeight: 16 }} />
                    )}
                  </div>
                  <div style={{ paddingBottom: 12, flex: 1 }}>
                    <div style={{ fontSize: "0.75rem", color: "#e2e8f0", fontWeight: 500 }}>
                      {formatAction(event.action)}
                    </div>
                    <div style={{ fontSize: "0.7rem", color: "#6b7280", marginTop: 1 }}>
                      {event.actor}
                    </div>
                    <div style={{ fontSize: "0.65rem", color: "#4b5563", marginTop: 1 }}>
                      {new Date(event.created_at).toLocaleTimeString()}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Panel 2: Candidate Arena (Center) */}
        <div
          style={{
            flex: "0 0 400px",
            borderRight: "1px solid #1f2937",
            overflowY: "auto",
            background: "#0d1117",
          }}
        >
          {/* Sub-tabs */}
          <div
            style={{
              display: "flex",
              borderBottom: "1px solid #1f2937",
              padding: "0 1rem",
            }}
          >
            {(["arena", "proof", "timeline"] as const).map((tab) => (
              <button
                key={tab}
                onClick={() => setActivePanel(tab)}
                style={{
                  padding: "0.6rem 0.75rem",
                  border: "none",
                  background: "none",
                  color: activePanel === tab ? "#7c3aed" : "#6b7280",
                  borderBottom: activePanel === tab ? "2px solid #7c3aed" : "2px solid transparent",
                  cursor: "pointer",
                  fontSize: "0.8rem",
                  fontWeight: activePanel === tab ? 700 : 400,
                  textTransform: "capitalize",
                }}
              >
                {tab === "arena" ? "⚔️ Candidates" : tab === "proof" ? "🔬 Proof" : "📋 Details"}
              </button>
            ))}
          </div>

          {activePanel === "arena" && (
            <div style={{ padding: "1rem" }}>
              {candidates.length === 0 ? (
                <div style={{ textAlign: "center", padding: "3rem 1rem" }}>
                  <div style={{ fontSize: "3rem", marginBottom: "1rem" }}>⚔️</div>
                  <div style={{ color: "#9ca3af", marginBottom: "0.5rem" }}>No candidates yet.</div>
                  <div style={{ color: "#4b5563", fontSize: "0.8rem" }}>
                    Click <strong style={{ color: "#7c3aed" }}>Run Arena</strong> to generate 3 concurrent repair candidates.
                  </div>
                </div>
              ) : (
                <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
                  {candidates.map((c) => {
                    const colors = candidateColor(c.status);
                    const isChosen = c.candidate_id === selectedCandidate;
                    return (
                      <div
                        key={c.candidate_id}
                        onClick={() => handleSelectCandidate(c.candidate_id)}
                        style={{
                          border: `1px solid ${isChosen ? "#7c3aed" : colors.border}`,
                          borderRadius: 10,
                          padding: "0.75rem 1rem",
                          background: isChosen ? "#1a0f2a" : colors.bg,
                          cursor: "pointer",
                          transition: "all 0.15s ease",
                          outline: isChosen ? "2px solid #7c3aed40" : "none",
                        }}
                      >
                        {/* Candidate header */}
                        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "0.5rem" }}>
                          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                            <span style={{ fontSize: "1.1rem" }}>
                              {STRATEGY_ICONS[c.strategy] ?? "🔧"}
                            </span>
                            <div>
                              <div style={{ fontSize: "0.85rem", fontWeight: 700, color: colors.text }}>
                                {STRATEGY_LABELS[c.strategy] ?? c.strategy}
                              </div>
                              <div style={{ fontSize: "0.7rem", color: "#6b7280" }}>
                                Candidate {c.candidate_index + 1}
                              </div>
                            </div>
                          </div>
                          <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 4 }}>
                            <StatusBadge status={c.status} />
                            {c.is_selected && (
                              <span style={{ fontSize: "0.65rem", color: "#22c55e", fontWeight: 700 }}>
                                ★ SELECTED
                              </span>
                            )}
                          </div>
                        </div>

                        {/* Gate checks */}
                        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.25rem", marginBottom: "0.5rem" }}>
                          <GateCheck passed={c.reproduction_passed} label="Reproduction" />
                          <GateCheck passed={c.build_passed} label="Build" />
                          <GateCheck passed={c.tests_passed} label="Tests" />
                          <GateCheck passed={c.no_new_failures} label="No Regressions" />
                        </div>

                        {/* Stats row */}
                        <div style={{ display: "flex", gap: "1rem", fontSize: "0.75rem", color: "#6b7280" }}>
                          {c.confidence != null && (
                            <span>
                              Confidence:{" "}
                              <strong style={{ color: c.confidence > 0.7 ? "#4ade80" : c.confidence > 0.4 ? "#facc15" : "#f87171" }}>
                                {Math.round(c.confidence * 100)}%
                              </strong>
                            </span>
                          )}
                          {c.risk_level && (
                            <span>
                              Risk:{" "}
                              <strong style={{ color: riskColor(c.risk_level) }}>
                                {c.risk_level}
                              </strong>
                            </span>
                          )}
                          {c.changed_files_count != null && (
                            <span>{c.changed_files_count} file{c.changed_files_count !== 1 ? "s" : ""}</span>
                          )}
                        </div>

                        {/* Discard reason */}
                        {c.discard_reason && (
                          <div style={{ marginTop: "0.5rem", fontSize: "0.75rem", color: "#f87171", fontFamily: "monospace" }}>
                            ✗ {c.discard_reason.slice(0, 120)}
                          </div>
                        )}

                        {/* Description */}
                        {c.description && (
                          <div style={{ marginTop: "0.5rem", fontSize: "0.75rem", color: "#9ca3af", lineHeight: 1.4 }}>
                            {c.description.slice(0, 150)}{c.description.length > 150 ? "…" : ""}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}

          {activePanel === "proof" && proof && (
            <div style={{ padding: "1rem" }}>
              <ProofPanel proof={proof} />
            </div>
          )}

          {activePanel === "proof" && !proof && (
            <div style={{ padding: "2rem", textAlign: "center", color: "#6b7280" }}>
              <div style={{ fontSize: "2rem", marginBottom: 8 }}>🔬</div>
              Select a candidate from the Arena view to see its Repair Proof.
            </div>
          )}

          {activePanel === "timeline" && (
            <div style={{ padding: "1rem" }}>
              <IncidentSummary incident={incident} />
            </div>
          )}
        </div>

        {/* Panel 3: Verification Proof (Right) */}
        <div
          style={{
            flex: 1,
            overflowY: "auto",
            background: "#0a0d14",
            padding: "1rem 1.5rem",
          }}
        >
          {selectedCandidateObj ? (
            <SelectedCandidateDetail
              candidate={selectedCandidateObj}
              proof={proof}
              onApprove={handleApprovePR}
              approving={approvingPR}
            />
          ) : (
            <div style={{ textAlign: "center", padding: "3rem 1rem", color: "#6b7280" }}>
              <div style={{ fontSize: "3rem", marginBottom: "1rem" }}>🔬</div>
              <div style={{ fontSize: "1rem", marginBottom: "0.5rem" }}>Visual Verification Workspace</div>
              <div style={{ fontSize: "0.85rem", color: "#4b5563" }}>
                Select a candidate from the Arena panel to view its full repair proof with evidence classification.
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Sub-components ─────────────────────────────────────────────────────────────

function StatusBadge({ status }: { status: string }) {
  const colors = candidateColor(status);
  return (
    <span
      style={{
        fontSize: "0.65rem",
        fontWeight: 700,
        padding: "2px 6px",
        borderRadius: 4,
        backgroundColor: colors.bg,
        color: colors.text,
        border: `1px solid ${colors.border}`,
        textTransform: "uppercase",
        letterSpacing: "0.05em",
      }}
    >
      {status.replace(/_/g, " ")}
    </span>
  );
}

function ProofPanel({ proof }: { proof: RepairProof }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
      {/* Verification summary */}
      <div
        style={{
          padding: "0.75rem",
          borderRadius: 8,
          background: proof.is_verified ? "#0f2a1a" : "#2a0f0f",
          border: `1px solid ${proof.is_verified ? "#166534" : "#991b1b"}`,
        }}
      >
        <div style={{ fontWeight: 700, color: proof.is_verified ? "#4ade80" : "#f87171", marginBottom: "0.5rem" }}>
          {proof.is_verified ? "✅ VERIFIED — Eligible for PR" : "❌ NOT VERIFIED — Ineligible"}
        </div>
        <div style={{ fontSize: "0.75rem", color: "#9ca3af", lineHeight: 1.5 }}>
          {proof.truthfulness_note}
        </div>
      </div>

      {/* Gate summary */}
      <div>
        <div style={{ fontSize: "0.7rem", fontWeight: 700, color: "#6b7280", textTransform: "uppercase", letterSpacing: "0.1em", marginBottom: "0.5rem" }}>
          Validation Gates
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          <GateCheck passed={proof.validation_summary.reproduction_passed} label="Reproduction" />
          <GateCheck passed={proof.validation_summary.build_passed} label="Build Validation" />
          <GateCheck passed={proof.validation_summary.tests_passed} label="Test Suite" />
          <GateCheck passed={proof.validation_summary.no_new_failures} label="No New Failures" />
        </div>
      </div>

      {/* Evidence sections */}
      {proof.observed_evidence.length > 0 && (
        <EvidenceSection title="Observed Evidence" items={proof.observed_evidence} />
      )}
      {proof.validated_evidence.map((ev, i) => (
        <div
          key={i}
          style={{
            padding: "0.6rem 0.75rem",
            borderRadius: 6,
            background: ev.passed ? "#0f2a1a" : "#2a0f0f",
            border: `1px solid ${ev.passed ? "#166534" : "#991b1b"}`,
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
            <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
              <span>{ev.passed ? "✅" : "❌"}</span>
              <strong style={{ fontSize: "0.8rem", color: "#e2e8f0" }}>
                {ev.stage.toUpperCase()}
              </strong>
              <EvidenceBadge label={ev.label} />
            </div>
            {ev.duration_seconds && (
              <span style={{ fontSize: "0.7rem", color: "#6b7280" }}>
                {ev.duration_seconds.toFixed(1)}s
              </span>
            )}
          </div>
          {ev.reproduction_level && (
            <div style={{ fontSize: "0.7rem", color: "#6b7280" }}>
              Level: {ev.reproduction_level.replace(/_/g, " ")}
            </div>
          )}
          {ev.stderr_excerpt && !ev.passed && (
            <pre
              style={{
                fontSize: "0.65rem",
                color: "#f87171",
                background: "#1a0808",
                padding: "0.4rem",
                borderRadius: 4,
                marginTop: 4,
                overflowX: "auto",
                whiteSpace: "pre-wrap",
                wordBreak: "break-all",
                maxHeight: 120,
                overflowY: "auto",
              }}
            >
              {ev.stderr_excerpt}
            </pre>
          )}
        </div>
      ))}

      {/* Uncertainty note */}
      <div
        style={{
          padding: "0.6rem 0.75rem",
          borderRadius: 6,
          background: "#1a1a0f",
          border: "1px solid #854d0e",
          fontSize: "0.75rem",
          color: "#fbbf24",
          lineHeight: 1.5,
        }}
      >
        ⚠️ {proof.uncertainty}
      </div>
    </div>
  );
}

function EvidenceSection({
  title,
  items,
}: {
  title: string;
  items: Array<{ label: string; item: string; source?: string }>;
}) {
  return (
    <div>
      <div style={{ fontSize: "0.7rem", fontWeight: 700, color: "#6b7280", textTransform: "uppercase", letterSpacing: "0.1em", marginBottom: "0.4rem" }}>
        {title}
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
        {items.map((item, i) => (
          <div key={i} style={{ display: "flex", gap: "0.5rem", alignItems: "flex-start" }}>
            <EvidenceBadge label={item.label} />
            <span style={{ fontSize: "0.75rem", color: "#9ca3af", lineHeight: 1.5 }}>
              {item.item}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

function SelectedCandidateDetail({
  candidate,
  proof,
  onApprove,
  approving,
}: {
  candidate: PatchCandidate;
  proof: RepairProof | null;
  onApprove: () => void;
  approving: boolean;
}) {
  const colors = candidateColor(candidate.status);

  return (
    <div>
      {/* Candidate header */}
      <div style={{ marginBottom: "1.5rem" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", marginBottom: "0.5rem" }}>
          <span style={{ fontSize: "1.5rem" }}>{STRATEGY_ICONS[candidate.strategy] ?? "🔧"}</span>
          <div>
            <h2 style={{ margin: 0, color: "#f1f5f9", fontSize: "1.1rem" }}>
              {STRATEGY_LABELS[candidate.strategy] ?? candidate.strategy}
            </h2>
            <div style={{ display: "flex", gap: "0.5rem", marginTop: 4 }}>
              <StatusBadge status={candidate.status} />
              {candidate.is_selected && (
                <span style={{ fontSize: "0.7rem", color: "#22c55e", fontWeight: 700, padding: "2px 6px", border: "1px solid #16a34a", borderRadius: 4, background: "#0f2a1a" }}>
                  ★ ARENA WINNER
                </span>
              )}
            </div>
          </div>
        </div>

        {candidate.description && (
          <div style={{ color: "#9ca3af", fontSize: "0.875rem", lineHeight: 1.6, marginTop: "0.75rem" }}>
            {candidate.description}
          </div>
        )}
      </div>

      {/* Metrics grid */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "0.75rem", marginBottom: "1.5rem" }}>
        <MetricCard
          label="Confidence"
          value={candidate.confidence != null ? `${Math.round(candidate.confidence * 100)}%` : "—"}
          color={candidate.confidence != null ? (candidate.confidence > 0.7 ? "#4ade80" : candidate.confidence > 0.4 ? "#facc15" : "#f87171") : "#6b7280"}
        />
        <MetricCard
          label="Risk Level"
          value={candidate.risk_level ?? "—"}
          color={riskColor(candidate.risk_level ?? "")}
        />
        <MetricCard
          label="Files Changed"
          value={String(candidate.changed_files_count ?? "—")}
          color="#60a5fa"
        />
        <MetricCard
          label="Lines Changed"
          value={String(candidate.changed_lines_count ?? "—")}
          color="#60a5fa"
        />
      </div>

      {/* Validation stages */}
      <div style={{ marginBottom: "1.5rem" }}>
        <div style={{ fontSize: "0.75rem", fontWeight: 700, color: "#6b7280", textTransform: "uppercase", letterSpacing: "0.1em", marginBottom: "0.75rem" }}>
          Validation Stages
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
          {candidate.verification_stages.length === 0 ? (
            <div style={{ color: "#4b5563", fontSize: "0.8rem" }}>No validation runs yet.</div>
          ) : (
            candidate.verification_stages.map((stage, i) => (
              <ValidationStageRow key={i} stage={stage} />
            ))
          )}
        </div>
      </div>

      {/* Full Repair Proof */}
      {proof && (
        <div style={{ marginBottom: "1.5rem" }}>
          <div style={{ fontSize: "0.75rem", fontWeight: 700, color: "#6b7280", textTransform: "uppercase", letterSpacing: "0.1em", marginBottom: "0.75rem" }}>
            Repair Proof
          </div>
          <ProofPanel proof={proof} />
        </div>
      )}

      {/* Approval panel */}
      {candidate.is_eligible && !candidate.is_selected && (
        <div
          style={{
            padding: "1rem",
            borderRadius: 8,
            background: "#0f2a1a",
            border: "1px solid #166534",
            marginTop: "1rem",
          }}
        >
          <div style={{ color: "#4ade80", fontWeight: 700, marginBottom: "0.5rem" }}>
            ✅ This candidate passed all validation gates.
          </div>
          <p style={{ color: "#9ca3af", fontSize: "0.85rem", margin: "0 0 1rem 0" }}>
            FixFlow does not automatically merge production changes.
            Review the diff and approve to create a draft PR.
          </p>
          <button
            onClick={onApprove}
            disabled={approving}
            style={{
              padding: "0.5rem 1.25rem",
              borderRadius: 8,
              border: "1px solid #22c55e",
              background: approving ? "#0f2a1a" : "linear-gradient(135deg, #16a34a, #15803d)",
              color: "#fff",
              cursor: approving ? "not-allowed" : "pointer",
              fontWeight: 600,
            }}
          >
            {approving ? "⏳ Creating PR..." : "✅ Approve → Create PR"}
          </button>
        </div>
      )}

      {candidate.discard_reason && (
        <div
          style={{
            padding: "0.75rem",
            borderRadius: 8,
            background: "#2a0f0f",
            border: "1px solid #991b1b",
            marginTop: "1rem",
            color: "#f87171",
            fontSize: "0.8rem",
            fontFamily: "monospace",
          }}
        >
          ✗ Discard Reason: {candidate.discard_reason}
        </div>
      )}
    </div>
  );
}

function ValidationStageRow({ stage }: { stage: { stage: string; status: string; passed: boolean | null; evidence_label: string | null; duration_seconds: number | null; exit_code: number | null; stdout_excerpt: string | null; stderr_excerpt: string | null } }) {
  const [expanded, setExpanded] = useState(false);
  const icon = stage.passed === true ? "✅" : stage.passed === false ? "❌" : "⏳";
  return (
    <div
      style={{
        borderRadius: 6,
        border: `1px solid ${stage.passed ? "#166534" : stage.passed === false ? "#991b1b" : "#374151"}`,
        background: stage.passed ? "#0f2a1a20" : stage.passed === false ? "#2a0f0f20" : "#0f0f1a",
        overflow: "hidden",
      }}
    >
      <div
        onClick={() => setExpanded(!expanded)}
        style={{
          display: "flex",
          alignItems: "center",
          gap: "0.5rem",
          padding: "0.5rem 0.75rem",
          cursor: "pointer",
        }}
      >
        <span>{icon}</span>
        <strong style={{ fontSize: "0.8rem", color: "#e2e8f0", flex: 1 }}>
          {stage.stage.toUpperCase()}
        </strong>
        {stage.evidence_label && <EvidenceBadge label={stage.evidence_label} />}
        {stage.duration_seconds && (
          <span style={{ fontSize: "0.7rem", color: "#6b7280" }}>
            {stage.duration_seconds.toFixed(1)}s
          </span>
        )}
        <span style={{ color: "#6b7280", fontSize: "0.75rem" }}>{expanded ? "▲" : "▼"}</span>
      </div>
      {expanded && (stage.stdout_excerpt || stage.stderr_excerpt) && (
        <div style={{ padding: "0 0.75rem 0.75rem" }}>
          {stage.stderr_excerpt && !stage.passed && (
            <pre style={{ fontSize: "0.7rem", color: "#f87171", background: "#1a0808", padding: "0.4rem", borderRadius: 4, overflowX: "auto", whiteSpace: "pre-wrap", wordBreak: "break-all", maxHeight: 200, overflowY: "auto" }}>
              {stage.stderr_excerpt}
            </pre>
          )}
          {stage.stdout_excerpt && stage.passed && (
            <pre style={{ fontSize: "0.7rem", color: "#86efac", background: "#080f08", padding: "0.4rem", borderRadius: 4, overflowX: "auto", whiteSpace: "pre-wrap", wordBreak: "break-all", maxHeight: 200, overflowY: "auto" }}>
              {stage.stdout_excerpt}
            </pre>
          )}
        </div>
      )}
    </div>
  );
}

function MetricCard({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <div style={{ padding: "0.75rem", borderRadius: 8, background: "#0f172a", border: "1px solid #1f2937", textAlign: "center" }}>
      <div style={{ fontSize: "1.25rem", fontWeight: 700, color, marginBottom: 2 }}>{value}</div>
      <div style={{ fontSize: "0.7rem", color: "#6b7280", textTransform: "uppercase", letterSpacing: "0.05em" }}>{label}</div>
    </div>
  );
}

function IncidentSummary({ incident }: { incident: IncidentDetail }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
      <div>
        <div style={{ fontSize: "0.7rem", color: "#6b7280", textTransform: "uppercase", letterSpacing: "0.1em", marginBottom: 4 }}>Title</div>
        <div style={{ color: "#e2e8f0", fontSize: "0.875rem" }}>{incident.title}</div>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.75rem" }}>
        <div>
          <div style={{ fontSize: "0.7rem", color: "#6b7280", marginBottom: 2 }}>STATUS</div>
          <div style={{ color: "#f1f5f9", fontSize: "0.8rem" }}>{STATUS_LABELS[incident.status] ?? incident.status}</div>
        </div>
        <div>
          <div style={{ fontSize: "0.7rem", color: "#6b7280", marginBottom: 2 }}>SEVERITY</div>
          <div style={{ color: SEVERITY_LABELS[incident.severity] ?? "#9ca3af", fontSize: "0.8rem" }}>{incident.severity}</div>
        </div>
      </div>
      {incident.commit_sha && (
        <div>
          <div style={{ fontSize: "0.7rem", color: "#6b7280", marginBottom: 2 }}>COMMIT</div>
          <div style={{ color: "#60a5fa", fontFamily: "monospace", fontSize: "0.8rem" }}>{incident.commit_sha.slice(0, 12)}</div>
        </div>
      )}
    </div>
  );
}

// ── Helpers ────────────────────────────────────────────────────────────────────

function riskColor(level: string): string {
  return { low: "#4ade80", medium: "#facc15", high: "#f97316", critical: "#ef4444" }[level] ?? "#9ca3af";
}

function getEventColor(action: string): string {
  if (action.includes("resolved")) return "#22c55e";
  if (action.includes("failed") || action.includes("rejected")) return "#ef4444";
  if (action.includes("created") || action.includes("generated")) return "#7c3aed";
  if (action.includes("started") || action.includes("running")) return "#3b82f6";
  if (action.includes("selected") || action.includes("approved")) return "#10b981";
  return "#6b7280";
}

function formatAction(action: string): string {
  return action
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}
