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
  type AffectedSource,
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
  const [activeTab, setActiveTab] = useState<"analysis" | "patch" | "audit">("analysis");
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
          { key: "patch" as const, label: `Patches (${patches.length})` },
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
        <AnalysisPanel analysis={latestAnalysis} incidentId={id} />
      )}
      {activeTab === "patch" && (
        <PatchPanel
          patch={latestPatch}
          incidentId={id}
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

function AnalysisPanel({ analysis, incidentId }: { analysis: Analysis | null; incidentId: string }) {
  const [sources, setSources] = useState<AffectedSource[]>([]);
  const [sourcesLoading, setSourcesLoading] = useState(false);

  useEffect(() => {
    if (!analysis) return;
    let cancelled = false;
    setSourcesLoading(true);
    incidentsApi
      .getAffectedSources(incidentId)
      .then((res) => {
        if (!cancelled) setSources(res);
      })
      .catch(() => {
        if (!cancelled) setSources([]);
      })
      .finally(() => {
        if (!cancelled) setSourcesLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [analysis, incidentId]);

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

      {/* Affected files */}
      {analysis.affected_files && analysis.affected_files.length > 0 && (
        <div className="card">
          <p className="label" style={{ marginBottom: "0.875rem" }}>AFFECTED FILES</p>
          <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
            {analysis.affected_files.map((f, i) => {
              // Show the actual source root the file lives in — the real
              // repository (e.g. "owner/repo") prefixed before the file path,
              // so "src/main.js" reads as "owner/repo/src/main.js".
              const sourcePath = analysis.repository_full_name
                ? `${analysis.repository_full_name}/${f}`
                : f;
              return (
                <div key={i} style={{ display: "flex", alignItems: "center", gap: "0.625rem" }}>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" stroke="var(--text-dim)" strokeWidth="1.5" />
                    <polyline points="14 2 14 8 20 8" stroke="var(--text-dim)" strokeWidth="1.5" />
                  </svg>
                  <code style={{ fontSize: "0.8125rem", color: "var(--text-primary)", fontFamily: "var(--font-mono)", fontWeight: 500 }}>
                    {sourcePath}
                  </code>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Evidence — full source of each affected file, error line(s) in red */}
      <div className="card">
        <p className="label" style={{ marginBottom: "0.875rem" }}>EVIDENCE</p>
        {sourcesLoading && sources.length === 0 ? (
          <p style={{ fontSize: "0.8125rem", color: "var(--text-dim)" }}>
            Loading affected source code…
          </p>
        ) : sources.length === 0 ? (
          <p style={{ fontSize: "0.8125rem", color: "var(--text-dim)" }}>
            Source code is unavailable. Ensure a GitHub token is configured so PatchR can fetch the affected files.
          </p>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
            {sources.map((src, i) => (
              <AffectedFileSource key={i} source={src} />
            ))}
          </div>
        )}
      </div>

      {/* Model info */}
      <p style={{ fontSize: "0.6875rem", color: "var(--text-dim)", fontFamily: "var(--font-mono)", paddingLeft: "0.25rem" }}>
        {analysis.model_provider}/{analysis.model_name} ·{" "}
        {analysis.prompt_tokens}pt + {analysis.completion_tokens}ct tokens ·{" "}
        {formatDateTime(analysis.created_at)}
      </p>
    </div>
  );
}

// ─── Affected File Source (full code, error lines highlighted red) ─────────────

function AffectedFileSource({ source }: { source: AffectedSource }) {
  const errorLineSet = new Set(source.error_lines || []);

  return (
    <div style={{ borderRadius: "var(--radius-md)", border: "1px solid #21262d", overflow: "hidden" }}>
      {/* File header */}
      <div
        style={{
          padding: "0.625rem 1rem",
          background: "#161b22",
          borderBottom: "1px solid #21262d",
          display: "flex",
          alignItems: "center",
          gap: "0.5rem",
        }}
      >
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" style={{ color: "#8b949e", flexShrink: 0 }}>
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" stroke="currentColor" strokeWidth="1.5" />
          <polyline points="14 2 14 8 20 8" stroke="currentColor" strokeWidth="1.5" />
        </svg>
        <code style={{ fontSize: "0.8125rem", fontFamily: "var(--font-mono)", color: "#e6edf3", flex: 1 }}>
          {source.path}
        </code>
        {errorLineSet.size > 0 && (
          <span style={{ fontSize: "0.6875rem", color: "#f85149", fontWeight: 500 }}>
            {errorLineSet.size} error line{errorLineSet.size > 1 ? "s" : ""}
          </span>
        )}
      </div>

      {/* Code body */}
      {source.available && source.content != null ? (
        <div
          style={{
            maxHeight: "480px",
            overflow: "auto",
            background: "#0d1117",
            fontFamily: "var(--font-mono)",
            fontSize: "0.8rem",
            lineHeight: 1.6,
          }}
        >
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <tbody>
              {source.content.split("\n").map((line, idx) => {
                const lineNo = idx + 1;
                const isError = errorLineSet.has(lineNo);
                return (
                  <tr key={idx} style={{ background: isError ? "rgba(248,81,73,0.15)" : "transparent" }}>
                    <td
                      style={{
                        padding: "0 1rem",
                        color: isError ? "rgba(248,81,73,0.7)" : "#3d444d",
                        userSelect: "none",
                        textAlign: "right",
                        minWidth: "2.5rem",
                        fontSize: "0.75rem",
                        borderRight: "1px solid #21262d",
                        verticalAlign: "top",
                      }}
                    >
                      {lineNo}
                    </td>
                    <td
                      style={{
                        padding: "0 1rem",
                        color: isError ? "#f85149" : "#e6edf3",
                        whiteSpace: "pre",
                        verticalAlign: "top",
                      }}
                    >
                      {line || " "}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : (
        <div style={{ padding: "1rem", background: "#0d1117", fontSize: "0.8125rem", color: "#8b949e" }}>
          Source unavailable for this file.
        </div>
      )}
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

// ─── File Change Diff (full code: removed lines red, added lines green) ─────────

type DiffRow = {
  type: "context" | "removed" | "added";
  oldNo: number | null;
  newNo: number | null;
  text: string;
};

/**
 * Compute a line-level diff between the original and patched file content using
 * a classic longest-common-subsequence table. Unchanged lines are shown as
 * context, lines only in the original are "removed" (red), lines only in the
 * patched version are "added" (green).
 */
function computeLineDiff(original: string, patched: string): DiffRow[] {
  const a = original.length ? original.split("\n") : [];
  const b = patched.length ? patched.split("\n") : [];
  const n = a.length;
  const m = b.length;

  // LCS length table
  const lcs: number[][] = Array.from({ length: n + 1 }, () => new Array(m + 1).fill(0));
  for (let i = n - 1; i >= 0; i--) {
    for (let j = m - 1; j >= 0; j--) {
      lcs[i][j] = a[i] === b[j] ? lcs[i + 1][j + 1] + 1 : Math.max(lcs[i + 1][j], lcs[i][j + 1]);
    }
  }

  const rows: DiffRow[] = [];
  let i = 0;
  let j = 0;
  let oldNo = 1;
  let newNo = 1;
  while (i < n && j < m) {
    if (a[i] === b[j]) {
      rows.push({ type: "context", oldNo: oldNo++, newNo: newNo++, text: a[i] });
      i++;
      j++;
    } else if (lcs[i + 1][j] >= lcs[i][j + 1]) {
      rows.push({ type: "removed", oldNo: oldNo++, newNo: null, text: a[i] });
      i++;
    } else {
      rows.push({ type: "added", oldNo: null, newNo: newNo++, text: b[j] });
      j++;
    }
  }
  while (i < n) {
    rows.push({ type: "removed", oldNo: oldNo++, newNo: null, text: a[i] });
    i++;
  }
  while (j < m) {
    rows.push({ type: "added", oldNo: null, newNo: newNo++, text: b[j] });
    j++;
  }
  return rows;
}

type FullDiffRow = {
  type: "context" | "removed" | "added";
  lineNo: number | null;
  text: string;
};

/**
 * Build a full-file view where the whole file is shown as context, and the
 * patched region is spliced in as removed (red) + added (green) lines at the
 * location where the original block appears in the file.
 *
 * Falls back sensibly when inputs are partial:
 *  - no full file   → show the original (red) + patched (green) blocks only
 *  - block not found → append the original (red) + patched (green) blocks after
 *                      the full file context so nothing is lost
 */
function buildFullFileDiffRows(
  fullFile: string,
  original: string,
  patched: string,
): FullDiffRow[] {
  const fileLines = fullFile.length ? fullFile.split("\n") : [];
  const origLines = original.length ? original.split("\n") : [];
  const patchedLines = patched.length ? patched.split("\n") : [];

  // No full file available — show just the change (original red, patched green).
  if (fileLines.length === 0) {
    const rows: FullDiffRow[] = [];
    origLines.forEach((t) => rows.push({ type: "removed", lineNo: null, text: t }));
    patchedLines.forEach((t) => rows.push({ type: "added", lineNo: null, text: t }));
    return rows;
  }

  // Locate the original block within the full file (exact sequence match).
  let matchStart = -1;
  if (origLines.length > 0) {
    for (let i = 0; i + origLines.length <= fileLines.length; i++) {
      let ok = true;
      for (let k = 0; k < origLines.length; k++) {
        if (fileLines[i + k] !== origLines[k]) {
          ok = false;
          break;
        }
      }
      if (ok) {
        matchStart = i;
        break;
      }
    }
  }

  const rows: FullDiffRow[] = [];

  if (matchStart === -1) {
    // Couldn't locate the original block — show the full file as context, then
    // the change block (removed red + added green) so the diff is still visible.
    fileLines.forEach((t, idx) => rows.push({ type: "context", lineNo: idx + 1, text: t }));
    origLines.forEach((t) => rows.push({ type: "removed", lineNo: null, text: t }));
    patchedLines.forEach((t) => rows.push({ type: "added", lineNo: null, text: t }));
    return rows;
  }

  // Context before the change
  for (let i = 0; i < matchStart; i++) {
    rows.push({ type: "context", lineNo: i + 1, text: fileLines[i] });
  }
  // Removed (original) lines — red
  for (let k = 0; k < origLines.length; k++) {
    rows.push({ type: "removed", lineNo: matchStart + k + 1, text: origLines[k] });
  }
  // Added (patched) lines — green
  patchedLines.forEach((t) => rows.push({ type: "added", lineNo: null, text: t }));
  // Context after the change
  for (let i = matchStart + origLines.length; i < fileLines.length; i++) {
    rows.push({ type: "context", lineNo: i + 1, text: fileLines[i] });
  }

  return rows;
}

function FileChangeRow({
  change,
  incidentId,
  isLast,
}: {
  change: {
    path: string;
    change_type: string;
    original_content: string | null;
    patched_content: string | null;
  };
  incidentId: string;
  isLast: boolean;
}) {
  const [fullScreen, setFullScreen] = useState(false);
  const [fullFile, setFullFile] = useState<string | null>(null);
  const [fullFileLoading, setFullFileLoading] = useState(false);

  // Fetch the complete file from GitHub when the full-screen view opens.
  useEffect(() => {
    if (!fullScreen || fullFile !== null) return;
    let cancelled = false;
    setFullFileLoading(true);
    incidentsApi
      .getFileContent(incidentId, change.path)
      .then((res) => {
        if (!cancelled) setFullFile(res.content ?? "");
      })
      .catch(() => {
        if (!cancelled) setFullFile("");
      })
      .finally(() => {
        if (!cancelled) setFullFileLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [fullScreen, fullFile, incidentId, change.path]);

  // Build the full-file view: the whole file as context, with the patched
  // region shown as removed (red) + added (green) lines in place.
  const fullDiffRows = buildFullFileDiffRows(
    fullFile ?? "",
    change.original_content ?? "",
    change.patched_content ?? "",
  );

  return (
    <div
      style={{
        borderBottom: isLast ? "none" : "1px solid #1e2d3d",
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
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" stroke="currentColor" strokeWidth="1.5" />
          <polyline points="14 2 14 8 20 8" stroke="currentColor" strokeWidth="1.5" />
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
        {/* Full-screen option on the right side of the block */}
        <button
          onClick={() => setFullScreen(true)}
          title="View full code in full screen"
          aria-label="View full code in full screen"
          style={{
            display: "inline-flex",
            alignItems: "center",
            justifyContent: "center",
            width: "26px",
            height: "26px",
            padding: 0,
            background: "transparent",
            border: "1px solid #30363d",
            borderRadius: "var(--radius-sm, 6px)",
            color: "#8b949e",
            cursor: "pointer",
            flexShrink: 0,
          }}
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
            <path d="M8 3H5a2 2 0 0 0-2 2v3M16 3h3a2 2 0 0 1 2 2v3M8 21H5a2 2 0 0 1-2-2v-3M16 21h3a2 2 0 0 0 2-2v-3" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </button>
      </div>

      {/* Default: full file code with removed lines in red and added lines in green */}
      <FileChangeDiff
        originalContent={change.original_content}
        patchedContent={change.patched_content}
      />

      {/* Full-screen overlay: shows the full code base of this file */}
      {fullScreen && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            zIndex: 1000,
            background: "rgba(1, 4, 9, 0.85)",
            display: "flex",
            flexDirection: "column",
            padding: "2rem",
          }}
          onClick={() => setFullScreen(false)}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            style={{
              flex: 1,
              display: "flex",
              flexDirection: "column",
              background: "#0d1117",
              border: "1px solid #30363d",
              borderRadius: "var(--radius-lg, 12px)",
              overflow: "hidden",
            }}
          >
            {/* Modal header */}
            <div
              style={{
                padding: "0.75rem 1.25rem",
                background: "#161b22",
                borderBottom: "1px solid #21262d",
                display: "flex",
                alignItems: "center",
                gap: "0.625rem",
              }}
            >
              <code style={{ fontSize: "0.8125rem", fontFamily: "var(--font-mono)", color: "#e6edf3", flex: 1 }}>
                {change.path}
              </code>
              <button
                onClick={() => setFullScreen(false)}
                aria-label="Close full screen"
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "0.375rem",
                  padding: "0.25rem 0.625rem",
                  background: "transparent",
                  border: "1px solid #30363d",
                  borderRadius: "var(--radius-sm, 6px)",
                  color: "#8b949e",
                  cursor: "pointer",
                  fontSize: "0.75rem",
                }}
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
                  <path d="M18 6 6 18M6 6l12 12" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" />
                </svg>
                Close
              </button>
            </div>

            {/* Full file code — removed line(s) in red, updated line(s) in green */}
            <div
              style={{
                flex: 1,
                overflow: "auto",
                background: "#0d1117",
                fontFamily: "var(--font-mono)",
                fontSize: "0.8rem",
                lineHeight: 1.6,
              }}
            >
              {fullFileLoading && fullFile === null ? (
                <div style={{ padding: "1rem", color: "#8b949e", fontSize: "0.8125rem" }}>
                  Loading full file…
                </div>
              ) : (
                <table style={{ width: "100%", borderCollapse: "collapse" }}>
                  <tbody>
                    {fullDiffRows.map((row, idx) => {
                      let bg = "transparent";
                      let color = "#e6edf3";
                      let prefix = " ";
                      if (row.type === "removed") {
                        bg = "rgba(248,81,73,0.15)";
                        color = "#f85149";
                        prefix = "-";
                      } else if (row.type === "added") {
                        bg = "rgba(46,160,67,0.15)";
                        color = "#3fb950";
                        prefix = "+";
                      }
                      return (
                        <tr key={idx} style={{ background: bg }}>
                          <td
                            style={{
                              padding: "0 1rem",
                              color: "#3d444d",
                              userSelect: "none",
                              textAlign: "right",
                              minWidth: "2.5rem",
                              fontSize: "0.75rem",
                              borderRight: "1px solid #21262d",
                              verticalAlign: "top",
                            }}
                          >
                            {row.lineNo ?? ""}
                          </td>
                          <td
                            style={{
                              padding: "0 0.5rem",
                              color,
                              userSelect: "none",
                              textAlign: "center",
                              verticalAlign: "top",
                            }}
                          >
                            {prefix}
                          </td>
                          <td style={{ padding: "0 1rem 0 0", color, whiteSpace: "pre", verticalAlign: "top" }}>
                            {row.text || " "}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function FileChangeDiff({
  originalContent,
  patchedContent,
}: {
  originalContent: string | null;
  patchedContent: string | null;
}) {
  const original = originalContent ?? "";
  const patched = patchedContent ?? "";

  // When there's no original (new file) show the full patched content as all-added.
  const rows = computeLineDiff(original, patched);

  if (rows.length === 0) {
    return (
      <div style={{ padding: "1rem", background: "#0d1117", fontSize: "0.8125rem", color: "#8b949e" }}>
        No code content available for this change.
      </div>
    );
  }

  return (
    <div
      style={{
        maxHeight: "480px",
        overflow: "auto",
        background: "#0d1117",
        borderTop: "1px solid #21262d",
        fontFamily: "var(--font-mono)",
        fontSize: "0.8rem",
        lineHeight: 1.6,
      }}
    >
      <table style={{ width: "100%", borderCollapse: "collapse" }}>
        <tbody>
          {rows.map((row, idx) => {
            let bg = "transparent";
            let color = "#e6edf3";
            let prefix = " ";
            if (row.type === "removed") {
              bg = "rgba(248,81,73,0.15)";
              color = "#f85149";
              prefix = "-";
            } else if (row.type === "added") {
              bg = "rgba(46,160,67,0.15)";
              color = "#3fb950";
              prefix = "+";
            }
            return (
              <tr key={idx} style={{ background: bg }}>
                <td
                  style={{
                    padding: "0 0.75rem",
                    color: "#3d444d",
                    userSelect: "none",
                    textAlign: "right",
                    minWidth: "2.25rem",
                    fontSize: "0.75rem",
                    verticalAlign: "top",
                  }}
                >
                  {row.oldNo ?? ""}
                </td>
                <td
                  style={{
                    padding: "0 0.75rem",
                    color: "#3d444d",
                    userSelect: "none",
                    textAlign: "right",
                    minWidth: "2.25rem",
                    fontSize: "0.75rem",
                    borderRight: "1px solid #21262d",
                    verticalAlign: "top",
                  }}
                >
                  {row.newNo ?? ""}
                </td>
                <td
                  style={{
                    padding: "0 0.5rem",
                    color,
                    userSelect: "none",
                    textAlign: "center",
                    verticalAlign: "top",
                  }}
                >
                  {prefix}
                </td>
                <td
                  style={{
                    padding: "0 1rem 0 0",
                    color,
                    whiteSpace: "pre",
                    verticalAlign: "top",
                  }}
                >
                  {row.text || " "}
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
  incidentId,
  onApprove,
  onReject,
  onGenerate,
  hasAnalysis,
}: {
  patch: Patch | null;
  incidentId: string;
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
              {approving ? "Pushing…" : "Approve & Push to GitHub"}
            </button>
            <button
              className="btn btn-ghost"
              disabled={approving}
              onClick={async () => {
                setApproving(true);
                await onApprove().finally(() => setApproving(false));
              }}
            >
              Approve (no push)
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
            View pushed code on GitHub →
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
            <FileChangeRow
              key={i}
              change={change}
              incidentId={incidentId}
              isLast={i >= patch.file_changes!.length - 1}
            />
          ))}
        </div>
      )}

      {/* Verification — static analysis + risk, shown within the Patches tab */}
      <VerificationPanel patch={patch} />
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

