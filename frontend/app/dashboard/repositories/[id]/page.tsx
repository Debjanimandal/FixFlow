"use client";

import { useEffect, useState, useCallback } from "react";
import { use } from "react";
import Link from "next/link";
import {
  auth,
  repositories as reposApi,
  type Repository,
  type DeploymentStatusResponse,
  type DeploymentStatusItem,
  type DeploymentLogsResponse,
  type BuildLogEntry,
} from "@/lib/api-client";

interface Props {
  params: Promise<{ id: string }>;
}

export default function RepositoryDetailPage({ params }: Props) {
  const { id } = use(params);
  const [repo, setRepo] = useState<Repository | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Deployment status
  const [depStatus, setDepStatus] = useState<DeploymentStatusResponse | null>(null);
  const [depLoading, setDepLoading] = useState(false);

  // Build logs drawer
  const [logsDrawerOpen, setLogsDrawerOpen] = useState(false);
  const [logsData, setLogsData] = useState<DeploymentLogsResponse | null>(null);
  const [logsLoading, setLogsLoading] = useState(false);
  const [selectedDeployment, setSelectedDeployment] = useState<DeploymentStatusItem | null>(null);

  // Scan status
  const [scanMessage, setScanMessage] = useState<string | null>(null);
  const [scanMode, setScanMode] = useState<"builds" | "runtime" | null>(null);
  const [scanning, setScanning] = useState(false);

  useEffect(() => {
    reposApi
      .get(id)
      .then(setRepo)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [id]);

  // Fetch deployment status on load + poll every 30s
  const fetchDeploymentStatus = useCallback(() => {
    if (!id) return;
    setDepLoading(true);
    reposApi
      .getDeploymentStatus(id)
      .then(setDepStatus)
      .catch(() => {}) // silent — non-critical
      .finally(() => setDepLoading(false));
  }, [id]);

  useEffect(() => {
    fetchDeploymentStatus();
    const interval = setInterval(fetchDeploymentStatus, 30000);
    return () => clearInterval(interval);
  }, [fetchDeploymentStatus]);

  // Open build logs drawer
  function handleViewLogs(deployment: DeploymentStatusItem) {
    setSelectedDeployment(deployment);
    setLogsDrawerOpen(true);
    setLogsLoading(true);
    setLogsData(null);
    reposApi
      .getDeploymentLogs(id, deployment.id)
      .then(setLogsData)
      .catch(() => setLogsData({ deployment_id: deployment.id, log_count: 0, logs: [] }))
      .finally(() => setLogsLoading(false));
  }

  // Scan for deployment failures
  async function handleScanDeployments() {
    setScanMode("builds");
    setScanning(true);
    setScanMessage("Scanning builds...");
    try {
      const result = await reposApi.scanDeployments(id);
      setScanMessage(result.message);
      if (result.incidents_created > 0) {
        fetchDeploymentStatus();
      }
    } catch (e: any) {
      setScanMessage(e.detail ?? "Scan failed");
    } finally {
      setScanning(false);
    }
  }

  // Scan runtime errors (500s in Vercel logs)
  async function handleScanRuntime() {
    setScanMode("runtime");
    setScanning(true);
    setScanMessage("Scanning runtime logs...");
    try {
      const result = await reposApi.scanRuntime(id, 60);
      setScanMessage(result.message);
    } catch (e: any) {
      setScanMessage(e.detail ?? "Runtime scan failed");
    } finally {
      setScanning(false);
    }
  }

  // Trigger a simulated runtime failure to verify end-to-end AI diagnosis and patching
  async function handleSimulateRuntime() {
    setScanMode("runtime");
    setScanning(true);
    setScanMessage("Simulating runtime crash & queueing AI diagnosis...");
    try {
      const result = await reposApi.simulateRuntime(id);
      setScanMessage(`Runtime Incident created! ${result.title} — AI root-cause analysis and patch queued.`);
    } catch (e: any) {
      setScanMessage(e.detail ?? "Failed to simulate runtime error");
    } finally {
      setScanning(false);
    }
  }

  if (loading) return <PageSkeleton />;
  if (error || !repo) return <NotFound />;

  return (
    <div style={{ padding: "2.5rem" }}>
      {/* Breadcrumb */}
      <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "2rem", fontSize: "0.875rem", color: "var(--text-muted)" }}>
        <Link href="/dashboard/repositories" style={{ color: "var(--text-muted)", textDecoration: "none" }}>Repositories</Link>
        <span>&rsaquo;</span>
        <span style={{ color: "var(--text-secondary)", fontWeight: 500 }}>{repo.full_name}</span>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 340px", gap: "2rem" }}>
        {/* Left Column */}
        <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
          {/* Header Card */}
          <div className="card" style={{ padding: "1.75rem 2rem" }}>
            <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "1.25rem" }}>
                <div style={{ width: "56px", height: "56px", borderRadius: "var(--radius-lg)", border: "1px solid var(--border)", background: "var(--bg-surface)", display: "flex", alignItems: "center", justifyContent: "center", color: "var(--text-secondary)", boxShadow: "var(--shadow-sm)" }}>
                  <svg width="28" height="28" viewBox="0 0 24 24" fill="none"><path d="M9 19c-5 1.5-5-2.5-7-3m14 6v-3.87a3.37 3.37 0 0 0-.94-2.61c3.14-.35 6.44-1.54 6.44-7A5.44 5.44 0 0 0 20 4.77 5.07 5.07 0 0 0 19.91 1S18.73.65 16 2.48a13.38 13.38 0 0 0-7 0C6.27.65 5.09 1 5.09 1A5.07 5.07 0 0 0 5 4.77a5.44 5.44 0 0 0-1.5 3.78c0 5.42 3.3 6.61 6.44 7A3.37 3.37 0 0 0 9 18.13V22" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" /></svg>
                </div>
                <div>
                  <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
                    <h1 style={{ fontSize: "1.5rem", fontWeight: 600, color: "var(--text-primary)", fontFamily: "var(--font-mono)", marginBottom: "0.25rem" }}>
                      {repo.full_name}
                    </h1>
                    {depStatus?.latest_state && <DeploymentBadge state={depStatus.latest_state} />}
                  </div>
                  <p style={{ fontSize: "0.875rem", color: "var(--text-muted)" }}>
                    Added {new Date(repo.created_at).toLocaleDateString()}
                    {depStatus?.vercel_project_name && (
                      <> &middot; Vercel: <span style={{ fontWeight: 500, color: "var(--text-secondary)" }}>{depStatus.vercel_project_name}</span></>
                    )}
                  </p>
                </div>
              </div>
              <div style={{ display: "flex", gap: "0.75rem" }}>
                <button
                  onClick={handleScanDeployments}
                  disabled={scanning}
                  className="btn btn-primary"
                  style={{
                    fontSize: "0.8125rem",
                    opacity: scanMode === "runtime" ? 0.6 : 1,
                    outline: scanMode === "builds" ? "2px solid var(--accent)" : "none",
                    outlineOffset: "2px",
                  }}
                >
                  {scanning && scanMode === "builds" ? "Scanning..." : "Scan Builds"}
                </button>
                <button
                  onClick={handleScanRuntime}
                  disabled={scanning}
                  className="btn btn-primary"
                  style={{
                    fontSize: "0.8125rem",
                    background: "#7C3AED",
                    opacity: scanMode === "builds" ? 0.6 : 1,
                    outline: scanMode === "runtime" ? "2px solid #7C3AED" : "none",
                    outlineOffset: "2px",
                  }}
                >
                  {scanning && scanMode === "runtime" ? "Scanning..." : "Scan Runtime"}
                </button>
                <button
                  onClick={handleSimulateRuntime}
                  disabled={scanning}
                  className="btn"
                  title="Simulate a live runtime exception to test AI analysis and automated patching"
                  style={{
                    fontSize: "0.8125rem",
                    background: "rgba(239, 68, 68, 0.1)",
                    color: "var(--severity-critical)",
                    border: "1px solid rgba(239, 68, 68, 0.3)",
                    fontWeight: 600,
                  }}
                >
                  ⚡ Simulate Runtime Crash
                </button>
                <a href={`https://github.com/${repo.full_name}`} target="_blank" rel="noreferrer" className="btn btn-ghost" style={{ fontSize: "0.8125rem" }}>
                  View on GitHub &#8599;
                </a>
              </div>
            </div>
          </div>

          {/* Scan result message — persists until user clicks the other scan button */}
          {scanMessage && scanMode && (
            <div style={{
              padding: "0.875rem 1.25rem", borderRadius: "8px",
              background: scanMessage.includes("Found") || scanMessage.includes("created")
                ? "rgba(16,185,129,0.1)"
                : scanMessage.includes("Scanning")
                  ? "rgba(99,102,241,0.06)"
                  : scanMessage.includes("error") || scanMessage.includes("Could not")
                    ? "rgba(239,68,68,0.08)"
                    : "rgba(99,102,241,0.08)",
              border: `1px solid ${
                scanMessage.includes("Found") || scanMessage.includes("created")
                  ? "rgba(16,185,129,0.3)"
                  : scanMessage.includes("error") || scanMessage.includes("Could not")
                    ? "rgba(239,68,68,0.3)"
                    : "rgba(99,102,241,0.2)"
              }`,
              fontSize: "0.8125rem",
              color: scanMessage.includes("Found") || scanMessage.includes("created")
                ? "#10B981"
                : scanMessage.includes("error") || scanMessage.includes("Could not")
                  ? "#f87171"
                  : "var(--text-secondary)",
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
            }}>
              <div style={{ display: "flex", alignItems: "center", gap: "0.625rem" }}>
                <span style={{
                  fontSize: "0.6875rem", fontWeight: 600, padding: "0.15rem 0.5rem",
                  borderRadius: "4px",
                  background: scanMode === "builds" ? "rgba(99,102,241,0.15)" : "rgba(124,58,237,0.15)",
                  color: scanMode === "builds" ? "var(--accent)" : "#7C3AED",
                }}>
                  {scanMode === "builds" ? "BUILDS" : "RUNTIME"}
                </span>
                <span>{scanMessage}</span>
              </div>
              {!scanning && (
                <button
                  onClick={() => { setScanMessage(null); setScanMode(null); }}
                  style={{ background: "none", border: "none", cursor: "pointer", color: "var(--text-dim)", fontSize: "1rem", lineHeight: 1, padding: "0 0.25rem" }}
                  title="Dismiss"
                >
                  &times;
                </button>
              )}
            </div>
          )}

          {/* Deployment History Card */}
          <div className="card" style={{ padding: "1.75rem 2rem" }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "1.25rem" }}>
              <h2 style={{ fontSize: "1rem", fontWeight: 600, color: "var(--text-primary)" }}>Recent Deployments</h2>
              <button
                onClick={fetchDeploymentStatus}
                className="btn btn-ghost"
                style={{ fontSize: "0.75rem", padding: "0.25rem 0.625rem", display: "flex", alignItems: "center", gap: "0.375rem" }}
              >
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" style={{ animation: depLoading ? "spin 1s linear infinite" : "none" }}>
                  <path d="M23 4v6h-6M1 20v-6h6" />
                  <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15" />
                </svg>
                Refresh
              </button>
            </div>

            {!depStatus || !depStatus.linked ? (
              <div style={{ textAlign: "center", padding: "3rem 2rem", border: "2px dashed var(--border)", borderRadius: "var(--radius-md)" }}>
                <VercelIcon size={24} color="var(--text-dim)" />
                <p style={{ fontSize: "0.875rem", color: "var(--text-muted)", marginTop: "1rem" }}>
                  No deployments detected. Deploy this repo on Vercel to see live status here.
                </p>
              </div>
            ) : depStatus.deployments.length === 0 ? (
              <div style={{ textAlign: "center", padding: "3rem 2rem", border: "2px dashed var(--border)", borderRadius: "var(--radius-md)" }}>
                <p style={{ fontSize: "0.875rem", color: "var(--text-muted)" }}>No deployments found yet. Push a commit to trigger a build.</p>
              </div>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: "0" }}>
                {depStatus.deployments.map((dep, i) => (
                  <DeploymentRow key={dep.id} deployment={dep} isLast={i === depStatus.deployments.length - 1} onViewLogs={handleViewLogs} />
                ))}
              </div>
            )}
          </div>

          {/* Incidents shortcut */}
          <div className="card">
            <h2 style={{ fontSize: "1rem", fontWeight: 600, marginBottom: "1rem", color: "var(--text-primary)" }}>Incidents</h2>
            <div style={{ textAlign: "center", padding: "3rem 2rem", border: "2px dashed var(--border)", borderRadius: "var(--radius-md)", background: "transparent" }}>
              <p style={{ fontSize: "0.875rem", color: "var(--text-secondary)", marginBottom: "1rem" }}>Use the global Incidents page to view and search incidents for this repository.</p>
              <Link href="/dashboard/incidents" className="btn btn-ghost">Go to Incidents</Link>
            </div>
          </div>
        </div>

        {/* Right Column — Sidebar */}
        <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
          {/* Integrations */}
          <div className="card" style={{ padding: "1.5rem" }}>
            <h2 style={{ fontSize: "0.8125rem", fontWeight: 600, marginBottom: "1.25rem", color: "var(--text-muted)", letterSpacing: "0.06em", textTransform: "uppercase" }}>INTEGRATIONS</h2>
            <div style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}>
              <div>
                <p className="label" style={{ marginBottom: "0.25rem" }}>GITHUB BRANCH</p>
                <p style={{ fontSize: "0.875rem", fontFamily: "var(--font-mono)", color: "var(--text-primary)", fontWeight: 500 }}>{repo.default_branch}</p>
              </div>
              <div>
                <p className="label" style={{ marginBottom: "0.25rem" }}>VERCEL PROJECT</p>
                {(repo.vercel_project_name || depStatus?.vercel_project_name) ? (
                  <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                    <VercelIcon size={12} color="#10B981" />
                    <p style={{ fontSize: "0.875rem", fontFamily: "var(--font-mono)", color: "#10B981", fontWeight: 500 }}>
                      {repo.vercel_project_name || depStatus?.vercel_project_name}
                    </p>
                  </div>
                ) : (
                  <div>
                    <p style={{ fontSize: "0.875rem", color: "var(--text-dim)", fontWeight: 500, marginBottom: "0.5rem" }}>Unlinked</p>
                    <Link
                      href="/dashboard/settings"
                      style={{ fontSize: "0.75rem", color: "var(--accent)", textDecoration: "none", fontWeight: 600 }}
                    >
                      Connect Vercel Account &rarr;
                    </Link>
                  </div>
                )}
              </div>
              <div>
                <p className="label" style={{ marginBottom: "0.25rem" }}>WEBHOOK STATE</p>
                <div style={{ display: "flex", alignItems: "center", gap: "0.375rem" }}>
                  <span style={{ width: "8px", height: "8px", borderRadius: "50%", background: repo.webhook_active ? "#10B981" : "var(--border-strong)", display: "inline-block" }} />
                  <span style={{ fontSize: "0.875rem", fontWeight: 500, color: repo.webhook_active ? "var(--text-primary)" : "var(--text-dim)" }}>
                    {repo.webhook_active ? "Active" : "Waiting for events"}
                  </span>
                </div>
              </div>
              {depStatus?.latest_state && (
                <div>
                  <p className="label" style={{ marginBottom: "0.25rem" }}>LATEST DEPLOY</p>
                  <DeploymentBadge state={depStatus.latest_state} />
                </div>
              )}
            </div>
          </div>

          {/* Danger Zone */}
          <div className="card" style={{ padding: "1.5rem" }}>
            <h2 style={{ fontSize: "0.8125rem", fontWeight: 600, marginBottom: "1.25rem", color: "var(--severity-critical)", letterSpacing: "0.06em", textTransform: "uppercase" }}>DANGER ZONE</h2>
            <p style={{ fontSize: "0.8125rem", color: "var(--text-secondary)", marginBottom: "1.25rem", lineHeight: 1.6 }}>
              Disconnecting this repository will remove it from FixFlow and delete all associated incidents, patches, and AI analyses permanently.
            </p>
            <button
              className="btn btn-danger"
              style={{ width: "100%", justifyContent: "center" }}
              onClick={async () => {
                if (confirm("Disconnect this repository?")) {
                  await reposApi.delete(repo.id);
                  window.location.href = "/dashboard/repositories";
                }
              }}
            >
              Disconnect Repository
            </button>
          </div>
        </div>
      </div>

      {/* Build Logs Drawer */}
      {logsDrawerOpen && (
        <LogsDrawer
          deployment={selectedDeployment}
          logsData={logsData}
          loading={logsLoading}
          onClose={() => { setLogsDrawerOpen(false); setLogsData(null); setSelectedDeployment(null); }}
        />
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Deployment Row
// ─────────────────────────────────────────────────────────────────────────────

function DeploymentRow({ deployment, isLast, onViewLogs }: {
  deployment: DeploymentStatusItem;
  isLast: boolean;
  onViewLogs: (dep: DeploymentStatusItem) => void;
}) {
  const time = deployment.created_at ? formatTimestamp(deployment.created_at) : "";
  const stateColor = getStateColor(deployment.state);
  const stateIcon = getStateIcon(deployment.state);

  return (
    <div style={{
      display: "flex", alignItems: "center", gap: "1rem",
      padding: "0.875rem 0",
      borderBottom: isLast ? "none" : "1px solid var(--border-subtle)",
    }}>
      {/* State indicator */}
      <div style={{ width: "28px", height: "28px", borderRadius: "50%", background: `${stateColor}15`, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
        <span style={{ fontSize: "0.875rem" }}>{stateIcon}</span>
      </div>

      {/* Info */}
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.125rem" }}>
          <DeploymentBadge state={deployment.state} small />
          {deployment.branch && (
            <span style={{ fontSize: "0.75rem", color: "var(--text-dim)", fontFamily: "var(--font-mono)" }}>
              {deployment.branch}
            </span>
          )}
        </div>
        <p style={{ fontSize: "0.75rem", color: "var(--text-muted)", margin: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
          {deployment.commit_message
            ? `${deployment.commit_sha?.slice(0, 7) || ""} ${deployment.commit_message}`
            : deployment.commit_sha?.slice(0, 7) || deployment.id.slice(0, 10)}
        </p>
      </div>

      {/* Time */}
      <span style={{ fontSize: "0.75rem", color: "var(--text-dim)", whiteSpace: "nowrap", flexShrink: 0 }}>{time}</span>

      {/* View logs button */}
      <button
        onClick={() => onViewLogs(deployment)}
        className="btn btn-ghost"
        style={{ fontSize: "0.6875rem", padding: "0.25rem 0.5rem", flexShrink: 0 }}
      >
        View logs
      </button>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Build Logs Drawer (slide-in panel)
// ─────────────────────────────────────────────────────────────────────────────

function LogsDrawer({ deployment, logsData, loading, onClose }: {
  deployment: DeploymentStatusItem | null;
  logsData: DeploymentLogsResponse | null;
  loading: boolean;
  onClose: () => void;
}) {
  return (
    <>
      {/* Backdrop */}
      <div
        onClick={onClose}
        style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.4)", zIndex: 900, cursor: "pointer" }}
      />
      {/* Drawer */}
      <div style={{
        position: "fixed", top: 0, right: 0, bottom: 0, width: "min(680px, 90vw)",
        background: "var(--bg-base)", borderLeft: "1px solid var(--border)",
        zIndex: 901, display: "flex", flexDirection: "column",
        boxShadow: "-8px 0 32px rgba(0,0,0,0.2)",
      }}>
        {/* Header */}
        <div style={{ padding: "1.25rem 1.5rem", borderBottom: "1px solid var(--border)", display: "flex", alignItems: "center", justifyContent: "space-between", flexShrink: 0 }}>
          <div>
            <h3 style={{ fontSize: "0.9375rem", fontWeight: 600, color: "var(--text-primary)", margin: "0 0 0.25rem" }}>Build Logs</h3>
            {deployment && (
              <p style={{ fontSize: "0.75rem", color: "var(--text-muted)", margin: 0 }}>
                {deployment.id.slice(0, 12)} &middot; <DeploymentBadge state={deployment.state} small />
              </p>
            )}
          </div>
          <button onClick={onClose} style={{ background: "none", border: "none", cursor: "pointer", color: "var(--text-muted)", fontSize: "1.25rem", padding: "0.25rem" }}>
            &#10005;
          </button>
        </div>

        {/* Log content */}
        <div style={{
          flex: 1, overflow: "auto", padding: "1rem 1.5rem",
          fontFamily: "var(--font-mono)", fontSize: "0.75rem", lineHeight: 1.7,
          background: "#0d1117",
        }}>
          {loading ? (
            <div style={{ padding: "2rem", textAlign: "center", color: "#8b949e" }}>
              <p>Loading build logs...</p>
            </div>
          ) : !logsData || logsData.logs.length === 0 ? (
            <div style={{ padding: "2rem", textAlign: "center", color: "#8b949e" }}>
              <p>No build logs available for this deployment.</p>
            </div>
          ) : (
            <div>
              {logsData.logs.map((log, i) => (
                <LogLine key={i} log={log} />
              ))}
            </div>
          )}
        </div>

        {/* Footer */}
        {deployment?.url && (
          <div style={{ padding: "0.75rem 1.5rem", borderTop: "1px solid var(--border)", flexShrink: 0 }}>
            <a
              href={`https://${deployment.url}`}
              target="_blank"
              rel="noreferrer"
              style={{ fontSize: "0.75rem", color: "var(--accent)", textDecoration: "none" }}
            >
              Open deployment &#8599;
            </a>
          </div>
        )}
      </div>
    </>
  );
}

function LogLine({ log }: { log: BuildLogEntry }) {
  const color = log.is_error ? "#f85149" : log.type === "command" ? "#79c0ff" : "#c9d1d9";
  return (
    <div style={{ color, whiteSpace: "pre-wrap", wordBreak: "break-all" }}>
      {log.text}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Deployment Badge
// ─────────────────────────────────────────────────────────────────────────────

function DeploymentBadge({ state, small = false }: { state: string; small?: boolean }) {
  const color = getStateColor(state);
  const label = state === "READY" ? "Ready" : state === "ERROR" ? "Error" : state === "BUILDING" ? "Building" : state === "QUEUED" ? "Queued" : state === "CANCELED" ? "Canceled" : state;
  const fontSize = small ? "0.625rem" : "0.6875rem";
  const padding = small ? "0.125rem 0.4rem" : "0.2rem 0.6rem";

  return (
    <span style={{
      fontSize, fontWeight: 600, padding,
      borderRadius: "9999px",
      background: `${color}15`,
      color,
      border: `1px solid ${color}40`,
      display: "inline-flex", alignItems: "center", gap: "0.25rem",
      whiteSpace: "nowrap",
    }}>
      <span style={{ width: "6px", height: "6px", borderRadius: "50%", background: color, display: "inline-block", animation: state === "BUILDING" ? "pulse 1.5s ease-in-out infinite" : "none" }} />
      {label}
    </span>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Utilities
// ─────────────────────────────────────────────────────────────────────────────

function getStateColor(state: string): string {
  switch (state) {
    case "READY": return "#10B981";
    case "ERROR": return "#EF4444";
    case "BUILDING": return "#F59E0B";
    case "QUEUED": return "#6366F1";
    case "CANCELED": return "#6B7280";
    default: return "#6B7280";
  }
}

function getStateIcon(state: string): string {
  switch (state) {
    case "READY": return "\u2705";
    case "ERROR": return "\u274C";
    case "BUILDING": return "\u2692\uFE0F";
    case "QUEUED": return "\u23F3";
    case "CANCELED": return "\u26D4";
    default: return "\u2022";
  }
}

function formatTimestamp(unixMs: number): string {
  if (!unixMs) return "";
  const d = new Date(unixMs);
  const now = new Date();
  const diffMs = now.getTime() - d.getTime();
  const diffMin = Math.floor(diffMs / 60000);
  if (diffMin < 1) return "just now";
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHrs = Math.floor(diffMin / 60);
  if (diffHrs < 24) return `${diffHrs}h ago`;
  const diffDays = Math.floor(diffHrs / 24);
  if (diffDays < 7) return `${diffDays}d ago`;
  return d.toLocaleDateString();
}

function VercelIcon({ size = 16, color = "white" }: { size?: number; color?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill={color}>
      <path d="M12 1L24 22H0L12 1Z" />
    </svg>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Loading / Error States
// ─────────────────────────────────────────────────────────────────────────────

function PageSkeleton() {
  return (
    <div style={{ padding: "2rem 2.5rem" }}>
      <div style={{ height: "16px", width: "150px", background: "var(--bg-surface)", borderRadius: "var(--radius-sm)", marginBottom: "2rem" }} />
      <div style={{ display: "grid", gridTemplateColumns: "1fr 320px", gap: "1.5rem" }}>
        <div style={{ height: "150px", background: "var(--bg-surface)", borderRadius: "var(--radius-md)" }} />
        <div style={{ height: "300px", background: "var(--bg-surface)", borderRadius: "var(--radius-md)" }} />
      </div>
    </div>
  );
}

function NotFound() {
  return (
    <div style={{ padding: "2rem 2.5rem", color: "var(--text-muted)", fontSize: "0.875rem" }}>
      Repository not found.
    </div>
  );
}
