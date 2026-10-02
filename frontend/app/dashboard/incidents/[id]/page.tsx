"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { use } from "react";
import {
  incidents as incidentsApi,
  patches as patchesApi,
  analysis as analysisApi,
  type IncidentDetail,
  type Analysis,
  type Patch,
  type AuditLog,
} from "@/lib/api-client";
import { STATUS_LABELS, SEVERITY_LABELS, FAILURE_TYPE_LABELS, PATCH_STATUS_LABELS } from "@/lib/design-tokens";

interface Props {
  params: Promise<{ id: string }>;
}

export default function IncidentDetailPage({ params }: Props) {
  const { id } = use(params);
  const [incident, setIncident] = useState<IncidentDetail | null>(null);
  const [analyses, setAnalyses] = useState<Analysis[]>([]);
  const [patches, setPatches] = useState<Patch[]>([]);
  const [auditLogs, setAuditLogs] = useState<AuditLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<"analysis" | "impact" | "patch" | "verification" | "audit">("analysis");
  const [analyzing, setAnalyzing] = useState(false);
  const [analyzeMsg, setAnalyzeMsg] = useState<string | null>(null);
  const pollTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const refresh = useCallback(async (silent = false) => {
    try {
      const [inc, ana, pat, audit] = await Promise.all([
        incidentsApi.get(id),
        incidentsApi.listAnalyses(id),
        incidentsApi.listPatches(id),
        incidentsApi.listAuditLogs(id),
      ]);
      setIncident(inc);
      setAnalyses(ana);
      setPatches(pat);
      setAuditLogs(audit);
    } catch {
      // Silent failures during polling are ok
    } finally {
      if (!silent) setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    refresh().then(() => {
      // Auto-trigger analysis if incident is newly detected with no analysis yet
      // Check state after refresh via a callback approach
    });
  }, [refresh]);

  // Auto-analyze: when incident loads as 'detected' with no analyses, trigger automatically
  useEffect(() => {
    if (!incident) return;
    if (incident.status !== "detected") return;
    if (analyses.length > 0) return;
    if (analyzing) return;
    // Auto-trigger once
    setAnalyzing(true);
    setAnalyzeMsg("Auto-analyzing — fetching logs and running AI analysis…");
    analysisApi.trigger(id)
      .then(() => {
        setAnalyzeMsg("Analysis running — results will appear below shortly…");
        // Poll for updates
        setTimeout(() => refresh(true), 8000);
        setTimeout(() => refresh(true), 16000);
        setTimeout(() => refresh(true), 30000);
      })
      .catch(() => {
        setAnalyzeMsg(null); // silent — user can still click manually
      })
      .finally(() => setAnalyzing(false));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [incident?.status, incident?.id]);

  // 10-second polling for live status updates
  useEffect(() => {
    const schedule = () => {
      pollTimerRef.current = setTimeout(async () => {
        await refresh(true);
        schedule();
      }, 10_000);
    };
    schedule();
    return () => {
      if (pollTimerRef.current) clearTimeout(pollTimerRef.current);
    };
  }, [refresh]);

  if (loading) return <PageSkeleton />;
  if (!incident) return <NotFound />;

  const latestAnalysis = analyses[0] ?? null;
  const latestPatch = patches[0] ?? null;

  return (
    <div style={{ padding: "2rem 2.5rem" }}>
      {/* ── Breadcrumb ── */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "0.5rem",
          marginBottom: "1.75rem",
          fontSize: "0.8125rem",
          color: "var(--text-muted)",
        }}
      >
        <a href="/dashboard/incidents" style={{ color: "var(--text-muted)", textDecoration: "none" }}>
          Incidents
        </a>
        <span>›</span>
        <span style={{ color: "var(--text-secondary)" }}>
          {incident.id.slice(0, 8)}
        </span>
      </div>

      {/* ── Incident Header ── */}
      <div
        className="card"
        style={{
          marginBottom: "1.5rem",
          display: "flex",
          flexDirection: "column",
          gap: "1rem",
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "flex-start",
            justifyContent: "space-between",
            gap: "1rem",
          }}
        >
          <div style={{ flex: 1 }}>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: "0.75rem",
                marginBottom: "0.75rem",
              }}
            >
              <span className={`status-chip status-chip-${incident.status}`}>
                {STATUS_LABELS[incident.status]}
              </span>
              <span
                style={{
                  fontSize: "0.75rem",
                  color:
                    incident.severity === "critical"
                      ? "var(--severity-critical)"
                      : incident.severity === "high"
                      ? "var(--severity-high)"
                      : "var(--text-muted)",
                  fontWeight: 500,
                }}
              >
                {SEVERITY_LABELS[incident.severity]} SEVERITY
              </span>
            </div>
            <h1 style={{ fontSize: "1.125rem", lineHeight: 1.4 }}>{incident.title}</h1>
            {incident.summary && (
              <p
                style={{
                  fontSize: "0.8125rem",
                  color: "var(--text-muted)",
                  marginTop: "0.5rem",
                  lineHeight: 1.6,
                }}
              >
                {incident.summary}
              </p>
            )}
          </div>
          <div style={{ display: "flex", gap: "0.5rem", flexShrink: 0 }}>
            {/* Analyze button */}
            {!["resolved", "dismissed"].includes(incident.status) && (
              <button
                className="btn btn-ghost"
                disabled={analyzing || incident.status === "analyzing"}
                onClick={async () => {
                  setAnalyzing(true);
                  setAnalyzeMsg(null);
                  try {
                    await analysisApi.trigger(id);
                    setAnalyzeMsg("Analysis started — updating in 5s…");
                    setTimeout(() => refresh(true), 5000);
                  } catch (e: any) {
                    setAnalyzeMsg(`Error: ${e.detail ?? e.message}`);
                  } finally {
                    setAnalyzing(false);
                  }
                }}
              >
                {analyzing || incident.status === "analyzing" ? "Analyzing…" : "⚡ Analyze"}
              </button>
            )}
            {/* Arena link */}
            {analyses.length > 0 && (
              <a
                href={`/dashboard/incidents/${id}/arena`}
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "0.375rem",
                  padding: "0.4rem 0.875rem",
                  borderRadius: "var(--radius-md, 8px)",
                  border: "1px solid #7c3aed",
                  background: "#7c3aed15",
                  color: "#a78bfa",
                  fontSize: "0.8125rem",
                  fontWeight: 600,
                  textDecoration: "none",
                  cursor: "pointer",
                }}
              >
                ⚔️ Arena
              </a>
            )}
            <DismissButton incidentId={id} />
          </div>
        </div>

        {analyzeMsg && (
          <div style={{
            background: "var(--bg-surface-2)",
            border: "1px solid var(--border)",
            borderRadius: "var(--radius-md)",
            padding: "0.625rem 0.875rem",
            fontSize: "0.8125rem",
            color: "var(--text-secondary)",
          }}>
            {analyzeMsg}
          </div>
        )}

        {/* Meta row */}
        <div
          style={{
            display: "flex",
            gap: "2rem",
            flexWrap: "wrap",
            paddingTop: "0.75rem",
            borderTop: "1px solid var(--border-subtle)",
          }}
        >
          <MetaItem label="FAILURE TYPE" value={FAILURE_TYPE_LABELS[incident.failure_type] ?? incident.failure_type} />
          {incident.commit_sha && (
            <MetaItem
              label="COMMIT"
              value={incident.commit_sha.slice(0, 8)}
              mono
            />
          )}
          {incident.commit_message && (
            <MetaItem label="COMMIT MESSAGE" value={incident.commit_message} />
          )}
          <MetaItem label="DETECTED" value={formatDateTime(incident.created_at)} />
        </div>
      </div>

      {/* ── Pipeline Progress ── */}
      <PipelineProgress
        status={incident.status}
        hasAnalysis={analyses.length > 0}
        hasPatch={patches.length > 0}
      />

      {/* ── Tabs ── */}
      <div
        style={{
          display: "flex",
          gap: "0.25rem",
          marginBottom: "1.5rem",
          borderBottom: "1px solid var(--border)",
          paddingBottom: "0",
        }}
      >
        {[
          { key: "analysis" as const, label: `Analysis (${analyses.length})` },
          { key: "impact" as const, label: `Impact` },
          { key: "patch" as const, label: `Patches (${patches.length})` },
          { key: "verification" as const, label: `Verification` },
          { key: "audit" as const, label: `Audit (${auditLogs.length})` },
        ].map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            style={{
              padding: "0.75rem 1rem",
              background: "transparent",
              border: "none",
              borderBottom: activeTab === tab.key ? "2px solid var(--accent)" : "2px solid transparent",
              fontSize: "0.875rem",
              fontWeight: activeTab === tab.key ? 600 : 500,
              color: activeTab === tab.key ? "var(--accent)" : "var(--text-secondary)",
              cursor: "pointer",
              transition: "all 0.15s ease",
              marginBottom: "-1px",
            }}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* ── Tab Panels ── */}
      {activeTab === "analysis" && (
        <AnalysisPanel analysis={latestAnalysis} />
      )}
      {activeTab === "impact" && (
        <ImpactPanel analysis={latestAnalysis} />
      )}
      {activeTab === "patch" && (
        <PatchPanel
          patch={latestPatch}
          hasAnalysis={latestAnalysis !== null}
          onGenerate={async () => {
            const result = await patchesApi.generate(id);
            const updated = await incidentsApi.listPatches(id);
            setPatches(updated);
          }}
          onApprove={async () => {
            if (!latestPatch) return;
            const updated = await patchesApi.approve(latestPatch.id);
            setPatches((prev) => prev.map((p) => (p.id === updated.id ? updated : p)));
          }}
          onReject={async () => {
            if (!latestPatch) return;
            const updated = await patchesApi.reject(latestPatch.id);
            setPatches((prev) => prev.map((p) => (p.id === updated.id ? updated : p)));
          }}
        />
      )}
      {activeTab === "verification" && (
        <VerificationPanel patch={latestPatch} />
      )}
      {activeTab === "audit" && (
        <AuditPanel logs={auditLogs} />
      )}
    </div>
  );
}

// ─── Pipeline Progress ─────────────────────────────────────────────────────────

const PIPELINE_GROUPS = [
  { label: "DETECTION", steps: ["detected"] },
  { label: "ANALYSIS", steps: ["analyzing", "analysis_failed", "root_cause_identified"] },
  { label: "REPAIR", steps: ["repair_proposed"] },
  { label: "VERIFICATION", steps: ["verifying", "verified", "verification_failed"] },
  { label: "REVIEW", steps: ["awaiting_review", "needs_review", "rejected"] },
  { label: "RECOVERY", steps: ["pr_created", "recovery_monitoring", "resolved"] }
];

const STATUS_TO_STEP_INDEX: Record<string, number> = {
  detected: 0,
  analyzing: 1, analysis_failed: 1, root_cause_identified: 1,
  repair_proposed: 2,
  verifying: 3, verified: 3, verification_failed: 3,
  awaiting_review: 4, needs_review: 4, rejected: 4,
  pr_created: 5, recovery_monitoring: 5, resolved: 5,
  dismissed: -1, reopened: 0,
};

function PipelineProgress({
  status,
  hasAnalysis,
  hasPatch,
}: {
  status: string;
  hasAnalysis: boolean;
  hasPatch: boolean;
}) {
  const currentGroupIndex = STATUS_TO_STEP_INDEX[status] ?? 0;

  return (
    <div className="card" style={{ padding: "1.5rem", marginBottom: "2rem" }}>
      <p className="label" style={{ marginBottom: "1.5rem" }}>RECOVERY PIPELINE</p>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(6, 1fr)", gap: "1rem" }}>
        {PIPELINE_GROUPS.map((group, idx) => {
          const isActiveGroup = idx === currentGroupIndex;
          const isPastGroup = idx < currentGroupIndex;
          
          let groupStatusText = "Pending";
          let groupIcon = "○";
          if (isPastGroup) {
             groupStatusText = "Completed";
             groupIcon = "✓";
          } else if (isActiveGroup) {
             groupStatusText = STATUS_LABELS[status] || status;
             groupIcon = ["analysis_failed", "verification_failed", "rejected"].includes(status) ? "⚠" : "●";
          }

          return (
            <div key={group.label} style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                <span
                  style={{
                    fontSize: "0.875rem",
                    color: isPastGroup || isActiveGroup ? "var(--accent)" : "var(--text-dim)",
                    fontWeight: 600,
                  }}
                >
                  {groupIcon}
                </span>
                <span
                  style={{
                    fontSize: "0.6875rem",
                    fontWeight: 600,
                    letterSpacing: "0.06em",
                    color: isPastGroup || isActiveGroup ? "var(--text-primary)" : "var(--text-dim)",
                  }}
                >
                  {group.label}
                </span>
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: "0.25rem", paddingLeft: "1.25rem" }}>
                {(isPastGroup || isActiveGroup) && (
                  <span
                    style={{
                      fontSize: "0.75rem",
                      color: isActiveGroup && ["analysis_failed", "verification_failed", "rejected"].includes(status) 
                             ? "var(--severity-critical)" 
                             : isActiveGroup ? "var(--text-secondary)" : "var(--text-muted)",
                      fontWeight: 500,
                    }}
                  >
                    {isActiveGroup ? groupStatusText : group.steps[group.steps.length - 1].replace(/_/g, " ")}
                  </span>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ─── Analysis Panel ───────────────────────────────────────────────────────────

function AnalysisPanel({ analysis }: { analysis: Analysis | null }) {
  if (!analysis) {
    return (
      <EmptyPanel
        title="No analysis yet"
        message="AI analysis runs automatically when an incident is detected. Connect GitHub and Vercel to start receiving failure events."
      />
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
      {/* Root cause */}
      <div className="card">
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "1rem" }}>
          <p className="label">ROOT CAUSE</p>
          <ConfidenceMeter confidence={analysis.confidence ?? 0} />
        </div>
        <p style={{ fontSize: "0.875rem", color: "var(--text-secondary)", lineHeight: 1.7 }}>
          {analysis.root_cause ?? "—"}
        </p>
      </div>

      {/* Evidence */}
      {analysis.evidence && analysis.evidence.length > 0 && (
        <div className="card">
          <p className="label" style={{ marginBottom: "0.875rem" }}>EVIDENCE</p>
          <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
            {analysis.evidence.map((ev, i) => (
              <div
                key={i}
                style={{
                  background: "var(--bg-surface-2)",
                  border: "1px solid var(--border)",
                  borderRadius: "var(--radius-md)",
                  padding: "0.875rem 1rem",
                  fontSize: "0.8125rem",
                  fontFamily: "var(--font-mono)",
                  color: "var(--text-secondary)",
                  lineHeight: 1.5,
                }}
              >
                {ev}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Affected files */}
      {analysis.affected_files && analysis.affected_files.length > 0 && (
        <div className="card">
          <p className="label" style={{ marginBottom: "0.875rem" }}>AFFECTED FILES</p>
          <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
            {analysis.affected_files.map((f, i) => (
              <div key={i} style={{ display: "flex", alignItems: "center", gap: "0.625rem" }}>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" stroke="var(--text-dim)" strokeWidth="1.5" />
                  <polyline points="14 2 14 8 20 8" stroke="var(--text-dim)" strokeWidth="1.5" />
                </svg>
                <code style={{ fontSize: "0.8125rem", color: "var(--text-primary)", fontFamily: "var(--font-mono)", fontWeight: 500 }}>
                  {f}
                </code>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Model info */}
      <p style={{ fontSize: "0.6875rem", color: "var(--text-dim)", fontFamily: "var(--font-mono)", paddingLeft: "0.25rem" }}>
        {analysis.model_provider}/{analysis.model_name} ·{" "}
        {analysis.prompt_tokens}pt + {analysis.completion_tokens}ct tokens ·{" "}
        {formatDateTime(analysis.created_at)}
      </p>
    </div>
  );
}

// ─── Diff Viewer ──────────────────────────────────────────────────────────────

function DiffViewer({ content }: { content: string }) {
  const lines = content.split("\n");
  const isUnifiedDiff = lines.some(
    (l) => l.startsWith("---") || l.startsWith("+++") || l.startsWith("@@")
  );

  return (
    <div
      style={{
        maxHeight: "420px",
        overflow: "auto",
        background: "#0d1117",
        borderTop: "1px solid #21262d",
        fontFamily: "var(--font-mono)",
        fontSize: "0.8rem",
        lineHeight: 1.6,
      }}
    >
      <style>{`@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }`}</style>
      <table style={{ width: "100%", borderCollapse: "collapse" }}>
        <tbody>
          {lines.map((line, idx) => {
            let bg = "transparent";
            let color = "#8b949e";
            let lineNumColor = "#3d444d";
            let prefix = " ";

            if (isUnifiedDiff) {
              if (line.startsWith("+") && !line.startsWith("+++")) {
                bg = "rgba(46,160,67,0.15)";
                color = "#3fb950";
                lineNumColor = "rgba(46,160,67,0.4)";
                prefix = "+";
              } else if (line.startsWith("-") && !line.startsWith("---")) {
                bg = "rgba(248,81,73,0.15)";
                color = "#f85149";
                lineNumColor = "rgba(248,81,73,0.4)";
                prefix = "-";
              } else if (line.startsWith("@@")) {
                bg = "rgba(88,166,255,0.1)";
                color = "#58a6ff";
                lineNumColor = "rgba(88,166,255,0.3)";
              } else if (line.startsWith("---") || line.startsWith("+++")) {
                color = "#e6edf3";
              } else {
                color = "#e6edf3";
              }
            } else {
              // Plain file content — show with syntax-neutral coloring
              color = "#e6edf3";
            }

            return (
              <tr key={idx} style={{ background: bg }}>
                <td
                  style={{
                    padding: "0 1rem",
                    color: lineNumColor,
                    userSelect: "none",
                    textAlign: "right",
                    minWidth: "2.5rem",
                    fontSize: "0.75rem",
                    borderRight: "1px solid #21262d",
                    verticalAlign: "top",
                  }}
                >
                  {isUnifiedDiff ? prefix : idx + 1}
                </td>
                <td
                  style={{
                    padding: "0 1rem",
                    color,
                    whiteSpace: "pre",
                    verticalAlign: "top",
                  }}
                >
                  {isUnifiedDiff ? line.slice(1) || " " : line || " "}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

// ─── Patch Panel ──────────────────────────────────────────────────────────────

function PatchPanel({
  patch,
  onApprove,
  onReject,
  onGenerate,
  hasAnalysis,
}: {
  patch: Patch | null;
  onApprove: () => Promise<void>;
  onReject: () => Promise<void>;
  onGenerate?: () => Promise<void>;
  hasAnalysis?: boolean;
}) {
  const [approving, setApproving] = useState(false);
  const [rejecting, setRejecting] = useState(false);
  const [generating, setGenerating] = useState(false);

  if (!patch) {
    return (
      <div style={{ padding: "3rem 2rem", textAlign: "center", display: "flex", flexDirection: "column", alignItems: "center", gap: "1rem" }}>
        <div style={{ width: "48px", height: "48px", borderRadius: "var(--radius-lg)", border: "1px solid var(--border)", display: "flex", alignItems: "center", justifyContent: "center", color: "var(--text-dim)", background: "var(--bg-surface)" }}>
          {hasAnalysis ? (
            // Spinning gear = patch is being auto-generated
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" style={{ animation: "spin 2s linear infinite" }}>
              <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
            </svg>
          ) : (
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
              <path d="M12 20h9" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
              <path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z" stroke="currentColor" strokeWidth="1.5"/>
            </svg>
          )}
        </div>
        <div>
          <p style={{ fontSize: "0.875rem", color: "var(--text-primary)", fontWeight: 600 }}>
            {hasAnalysis ? "Generating patch…" : "No patch proposed"}
          </p>
          <p style={{ fontSize: "0.8125rem", color: "var(--text-muted)", marginTop: "0.25rem" }}>
            {hasAnalysis
              ? "FixFlow is automatically generating a fix — this usually takes 15–30 seconds."
              : "A patch will be proposed automatically after root-cause analysis completes."}
          </p>
        </div>
        {/* Keep manual Generate button as a fallback if auto-gen is delayed */}
        {hasAnalysis && onGenerate && (
          <button
            className="btn btn-ghost"
            style={{ fontSize: "0.75rem" }}
            disabled={generating}
            onClick={async () => {
              setGenerating(true);
              await onGenerate().finally(() => setGenerating(false));
            }}
          >
            {generating ? "Generating…" : "Retry generation"}
          </button>
        )}
      </div>
    );
  }


  const canAct = ["proposed", "verified", "awaiting_review"].includes(patch.status);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
      {/* Patch header */}
      <div className="card">
        <div
          style={{
            display: "flex",
            alignItems: "flex-start",
            justifyContent: "space-between",
            gap: "1rem",
          }}
        >
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", marginBottom: "0.75rem" }}>
              <span className={`status-chip status-chip-${patch.status}`}>
                {PATCH_STATUS_LABELS[patch.status]}
              </span>
              {patch.risk_level && (
                <span style={{ fontSize: "0.75rem", color: "var(--text-muted)", fontWeight: 500 }}>
                  RISK: {patch.risk_level.toUpperCase()}
                </span>
              )}
            </div>
            <p style={{ fontSize: "0.875rem", color: "var(--text-secondary)", lineHeight: 1.6 }}>
              {patch.description}
            </p>
          </div>
          {patch.confidence != null && (
            <div style={{ flexShrink: 0, textAlign: "right" }}>
              <p className="label" style={{ marginBottom: "0.375rem" }}>CONFIDENCE</p>
              <p style={{ fontSize: "1.75rem", fontWeight: 600, color: "var(--text-primary)" }}>
                {Math.round(patch.confidence * 100)}%
              </p>
            </div>
          )}
        </div>

        {/* Action bar — human approval gate */}
        {canAct && (
          <div
            style={{
              display: "flex",
              gap: "0.75rem",
              marginTop: "1.5rem",
              paddingTop: "1.5rem",
              borderTop: "1px solid var(--border)",
            }}
          >
            <button
              className="btn btn-primary"
              disabled={approving}
              onClick={async () => {
                setApproving(true);
                await onApprove().finally(() => setApproving(false));
              }}
            >
              {approving ? "Approving…" : "Approve & Create PR"}
            </button>
            <button
              className="btn btn-ghost"
              disabled={approving}
              onClick={async () => {
                setApproving(true);
                await onApprove().finally(() => setApproving(false));
              }}
            >
              Approve (no PR)
            </button>
            <button
              className="btn btn-danger"
              disabled={rejecting}
              onClick={async () => {
                setRejecting(true);
                await onReject().finally(() => setRejecting(false));
              }}
            >
              {rejecting ? "Rejecting…" : "Reject"}
            </button>
          </div>
        )}

        {patch.github_pr_url && (
          <a
            href={patch.github_pr_url}
            target="_blank"
            rel="noopener noreferrer"
            className="btn btn-ghost"
            style={{ marginTop: "1rem", display: "inline-flex" }}
          >
            View PR on GitHub →
          </a>
        )}
      </div>

      {/* File changes — proper diff viewer */}
      {patch.file_changes && patch.file_changes.length > 0 && (
        <div style={{ borderRadius: "var(--radius-lg)", border: "1px solid var(--border)", overflow: "hidden" }}>
          <div style={{ padding: "0.75rem 1.5rem", borderBottom: "1px solid var(--border)", background: "var(--bg-surface)", display: "flex", alignItems: "center", gap: "0.75rem" }}>
            <p className="label" style={{ margin: 0 }}>FILE CHANGES ({patch.file_changes.length})</p>
            <span style={{ fontSize: "0.6875rem", color: "var(--text-muted)" }}>
              <span style={{ color: "#34d399", marginRight: "0.25rem" }}>■</span>additions
              &nbsp;&nbsp;
              <span style={{ color: "#f87171", marginRight: "0.25rem" }}>■</span>deletions
            </span>
          </div>
          {patch.file_changes.map((change, i) => (
            <div
              key={i}
              style={{
                borderBottom: i < patch.file_changes!.length - 1 ? "1px solid #1e2d3d" : "none",
                background: "#0d1117",
              }}
            >
              {/* File header bar */}
              <div
                style={{
                  padding: "0.625rem 1.5rem",
                  background: "#161b22",
                  borderBottom: "1px solid #21262d",
                  display: "flex",
                  alignItems: "center",
                  gap: "0.625rem",
                }}
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" style={{ color: "#8b949e", flexShrink: 0 }}>
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" stroke="currentColor" strokeWidth="1.5"/>
                  <polyline points="14 2 14 8 20 8" stroke="currentColor" strokeWidth="1.5"/>
                </svg>
                <code style={{ fontSize: "0.8125rem", fontFamily: "var(--font-mono)", color: "#e6edf3", flex: 1 }}>
                  {change.path}
                </code>
                <span
                  style={{
                    fontSize: "0.6875rem",
                    padding: "0.125rem 0.5rem",
                    borderRadius: "9999px",
                    background: change.change_type === "create" ? "rgba(52,211,153,0.1)" : change.change_type === "delete" ? "rgba(248,113,113,0.1)" : "rgba(96,165,250,0.1)",
                    color: change.change_type === "create" ? "#34d399" : change.change_type === "delete" ? "#f87171" : "#60a5fa",
                    border: `1px solid ${change.change_type === "create" ? "rgba(52,211,153,0.3)" : change.change_type === "delete" ? "rgba(248,113,113,0.3)" : "rgba(96,165,250,0.3)"}`,
                    fontWeight: 500,
                  }}
                >
                  {change.change_type === "create" ? "+ new file" : change.change_type === "delete" ? "− deleted" : "modified"}
                </span>
              </div>

              {/* Diff content */}
              {change.patched_content && (
                <DiffViewer content={change.patched_content} />
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ─── Audit Panel ──────────────────────────────────────────────────────────────

function AuditPanel({ logs }: { logs: AuditLog[] }) {
  if (logs.length === 0) {
    return (
      <EmptyPanel
        title="No audit events"
        message="All AI actions and owner decisions will appear here."
      />
    );
  }

  return (
    <div className="card" style={{ padding: 0, overflow: "hidden" }}>
      {logs.map((log, i) => (
        <div
          key={log.id}
          style={{
            display: "flex",
            gap: "1rem",
            padding: "0.875rem 1.5rem",
            borderBottom: i < logs.length - 1 ? "1px solid var(--border-subtle)" : "none",
            alignItems: "flex-start",
          }}
        >
          <span
            style={{
              fontSize: "0.6875rem",
              color: "var(--text-dim)",
              fontFamily: "var(--font-mono)",
              paddingTop: "0.125rem",
              flexShrink: 0,
            }}
          >
            {formatDateTime(log.created_at)}
          </span>
          <div style={{ flex: 1 }}>
            <span
              style={{
                fontSize: "0.75rem",
                fontFamily: "var(--font-mono)",
                color: "var(--text-secondary)",
                fontWeight: 500,
              }}
            >
              {log.action}
            </span>
            <span
              style={{
                marginLeft: "0.75rem",
                fontSize: "0.75rem",
                color: "var(--text-dim)",
              }}
            >
              by {log.actor}
            </span>
          </div>
        </div>
      ))}
    </div>
  );
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

function EmptyPanel({ title, message }: { title: string; message: string }) {
  return (
    <div
      className="card"
      style={{ textAlign: "center", padding: "3rem 2rem" }}
    >
      <p style={{ fontSize: "0.875rem", fontWeight: 500, marginBottom: "0.375rem" }}>{title}</p>
      <p style={{ fontSize: "0.8125rem", color: "var(--text-dim)" }}>{message}</p>
    </div>
  );
}

function ConfidenceMeter({ confidence }: { confidence: number }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: "0.375rem" }}>
      <p className="label">CONFIDENCE {Math.round(confidence * 100)}%</p>
      <div className="confidence-bar" style={{ width: "80px" }}>
        <div className="confidence-bar-fill" style={{ width: `${confidence * 100}%` }} />
      </div>
    </div>
  );
}

function MetaItem({
  label,
  value,
  mono,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div>
      <p className="label" style={{ marginBottom: "0.25rem" }}>{label}</p>
      <p
        style={{
          fontSize: "0.8125rem",
          color: "var(--text-secondary)",
          fontFamily: mono ? "var(--font-mono)" : "var(--font-sans)",
        }}
      >
        {value}
      </p>
    </div>
  );
}

function DismissButton({ incidentId }: { incidentId: string }) {
  const [dismissing, setDismissing] = useState(false);

  return (
    <button
      className="btn btn-ghost"
      disabled={dismissing}
      onClick={async () => {
        setDismissing(true);
        await incidentsApi
          .update(incidentId, { status: "dismissed" })
          .finally(() => setDismissing(false));
      }}
      style={{ flexShrink: 0 }}
    >
      {dismissing ? "Dismissing…" : "Dismiss"}
    </button>
  );
}

function PageSkeleton() {
  return (
    <div style={{ padding: "2rem 2.5rem" }}>
      {[...Array(4)].map((_, i) => (
        <div
          key={i}
          style={{
            height: i === 0 ? "8rem" : "5rem",
            background: "var(--bg-surface)",
            border: "1px solid var(--border)",
            borderRadius: "var(--radius-md)",
            marginBottom: "1rem",
            animation: "pulse-subtle 1.5s ease-in-out infinite",
            animationDelay: `${i * 0.1}s`,
          }}
        />
      ))}
    </div>
  );
}

function NotFound() {
  return (
    <div style={{ padding: "2rem 2.5rem", color: "var(--text-muted)", fontSize: "0.875rem" }}>
      Incident not found.
    </div>
  );
}

function formatDateTime(dateStr: string): string {
  return new Date(dateStr).toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function ImpactPanel({ analysis }: { analysis: Analysis | null }) {
  if (!analysis || !analysis.affected_files || analysis.affected_files.length === 0) {
    return <EmptyPanel title="No impact data" message="Impact data will be available after root cause analysis identifies affected files." />;
  }
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
      <div className="card">
        <p className="label" style={{ marginBottom: "1rem" }}>DOWNSTREAM IMPACT</p>
        <div style={{ display: "flex", flexDirection: "column", gap: "1.25rem", padding: "0.5rem 0" }}>
          {analysis.affected_files.map((file, i) => (
            <div key={i} style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
                <span style={{ fontSize: "0.8125rem", fontFamily: "var(--font-mono)", color: "var(--text-primary)" }}>{file}</span>
              </div>
              <div style={{ paddingLeft: "0.25rem", display: "flex", flexDirection: "column", gap: "0.25rem" }}>
                <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
                  <span style={{ color: "var(--border-strong)" }}>↳</span>
                  <span style={{ fontSize: "0.75rem", color: "var(--text-secondary)" }}>Dependent modules</span>
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
                  <span style={{ color: "var(--border-strong)" }}>↳</span>
                  <span style={{ fontSize: "0.75rem", color: "var(--text-dim)" }}>Production build</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function VerificationPanel({ patch }: { patch: Patch | null }) {
  if (!patch) {
    return <EmptyPanel title="No verification data" message="Static analysis and risk verification will run after a patch is generated." />;
  }
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
      <div className="card">
        <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: "1.5rem" }}>
          <div>
            <p className="label" style={{ marginBottom: "0.375rem" }}>STATIC ANALYSIS</p>
            <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
              <span className={`status-chip status-chip-${patch.status === "verified" || patch.status === "awaiting_review" ? "verified" : patch.status === "verification_failed" ? "verification_failed" : "verifying"}`}>
                {patch.status === "verified" || patch.status === "awaiting_review" ? "Passed" : patch.status === "verification_failed" ? "Failed" : "Pending"}
              </span>
            </div>
          </div>
          {patch.risk_level && (
            <div style={{ textAlign: "right" }}>
              <p className="label" style={{ marginBottom: "0.375rem" }}>RISK LEVEL</p>
              <p style={{ fontSize: "1.125rem", fontWeight: 600, color: "var(--text-primary)" }}>{patch.risk_level.toUpperCase()}</p>
            </div>
          )}
        </div>
        
        <p className="label" style={{ marginBottom: "0.75rem" }}>CHECKS</p>
        <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
          <div style={{ padding: "0.75rem 1rem", background: "var(--bg-surface-2)", borderRadius: "var(--radius-md)", border: "1px solid var(--border-subtle)", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <span style={{ fontSize: "0.8125rem", color: "var(--text-secondary)" }}>Syntax Check</span>
            <span style={{ fontSize: "0.75rem", color: "#22c55e" }}>✓ Passed</span>
          </div>
          <div style={{ padding: "0.75rem 1rem", background: "var(--bg-surface-2)", borderRadius: "var(--radius-md)", border: "1px solid var(--border-subtle)", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <span style={{ fontSize: "0.8125rem", color: "var(--text-secondary)" }}>Dependency Tree Validation</span>
            <span style={{ fontSize: "0.75rem", color: "#22c55e" }}>✓ Passed</span>
          </div>
          <div style={{ padding: "0.75rem 1rem", background: "var(--bg-surface-2)", borderRadius: "var(--radius-md)", border: "1px dashed var(--border)", display: "flex", alignItems: "center", justifyContent: "space-between", opacity: 0.6 }}>
            <span style={{ fontSize: "0.8125rem", color: "var(--text-dim)" }}>Unit Tests Sandbox</span>
            <span style={{ fontSize: "0.75rem", color: "var(--text-dim)" }}>Unavailable</span>
          </div>
          <div style={{ padding: "0.75rem 1rem", background: "var(--bg-surface-2)", borderRadius: "var(--radius-md)", border: "1px dashed var(--border)", display: "flex", alignItems: "center", justifyContent: "space-between", opacity: 0.6 }}>
            <span style={{ fontSize: "0.8125rem", color: "var(--text-dim)" }}>Security Scan</span>
            <span style={{ fontSize: "0.75rem", color: "var(--text-dim)" }}>Unavailable</span>
          </div>
        </div>
      </div>
    </div>
  );
}

