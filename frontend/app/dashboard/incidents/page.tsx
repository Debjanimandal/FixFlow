"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { incidents as incidentsApi, repositories as reposApi, type IncidentListItem, type IncidentStatus } from "@/lib/api-client";
import { STATUS_LABELS, SEVERITY_LABELS, FAILURE_TYPE_LABELS } from "@/lib/design-tokens";

const STATUS_FILTERS: { label: string; value: IncidentStatus | "all" }[] = [
  { label: "All", value: "all" },
  { label: "Active", value: "detected" },
  { label: "Analyzing", value: "analyzing" },
  { label: "Patch Ready", value: "patch_ready" },
  { label: "Verified", value: "verified" },
  { label: "Resolved", value: "resolved" },
];

export default function IncidentsPage() {
  const [incidents, setIncidents] = useState<IncidentListItem[]>([]);
  const [activeFilter, setActiveFilter] = useState<IncidentStatus | "all">("all");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [scanning, setScanning] = useState(false);
  const [scanMsg, setScanMsg] = useState<string | null>(null);

  function loadIncidents() {
    setLoading(true);
    incidentsApi
      .list({
        status_filter: activeFilter === "all" ? undefined : activeFilter,
        limit: 50,
      })
      .then(setIncidents)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }

  // Auto-scan on first mount, then load incidents
  useEffect(() => {
    setScanning(true);
    reposApi.scanAll()
      .then((res) => {
        if (res.incidents_created > 0) {
          setScanMsg(`Found ${res.incidents_created} new incident(s)`);
        }
      })
      .catch(() => {}) // silent — no GitHub token or no failures is fine
      .finally(() => {
        setScanning(false);
        loadIncidents();
      });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    loadIncidents();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeFilter]);

  async function handleScanNow() {
    setScanning(true);
    setScanMsg(null);
    try {
      const res = await reposApi.scanAll();
      setScanMsg(
        res.incidents_created > 0
          ? `Scan complete — ${res.incidents_created} new incident(s) found`
          : `Scan complete — no new failures found across ${res.repos_scanned} repo(s)`
      );
      loadIncidents();
    } catch {
      setScanMsg("Scan failed — check backend logs");
    } finally {
      setScanning(false);
    }
  }

  return (
    <div style={{ padding: "2rem 2.5rem" }}>
      {/* ── Header ── */}
      <div style={{ marginBottom: "2.5rem", display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: "1rem", flexWrap: "wrap" }}>
        <div>
          <h1 style={{ marginBottom: "0.5rem" }}>Incidents</h1>
          <p style={{ fontSize: "0.875rem", color: "var(--text-muted)" }}>
            All detected failures and their current resolution state.
          </p>
          {scanMsg && (
            <p style={{ fontSize: "0.8rem", marginTop: "0.5rem", color: scanMsg.includes("new") ? "#10B981" : "var(--text-secondary)" }}>
              {scanMsg}
            </p>
          )}
        </div>
        <button
          onClick={handleScanNow}
          disabled={scanning}
          className="btn btn-primary"
          style={{ padding: "0.5rem 1.25rem", fontSize: "0.8125rem", display: "flex", alignItems: "center", gap: "0.5rem", whiteSpace: "nowrap" }}
        >
          {scanning ? (
            <>
              <span style={{ display: "inline-block", width: 12, height: 12, borderRadius: "50%", border: "2px solid rgba(255,255,255,0.3)", borderTopColor: "white", animation: "spin 0.7s linear infinite" }} />
              Scanning…
            </>
          ) : (
            <>
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2"><path d="M23 4v6h-6"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg>
              Scan Now
            </>
          )}
        </button>
      </div>

      {/* ── Filters Bar ── */}
      <div
        style={{
          display: "flex",
          gap: "1rem",
          marginBottom: "1.5rem",
          alignItems: "center",
          flexWrap: "wrap",
        }}
      >
        <div style={{ position: "relative", width: "320px" }}>
          <svg style={{ position: "absolute", left: "0.875rem", top: "50%", transform: "translateY(-50%)", color: "var(--text-dim)" }} width="16" height="16" viewBox="0 0 24 24" fill="none">
            <circle cx="11" cy="11" r="8" stroke="currentColor" strokeWidth="1.5" />
            <path d="M21 21l-4.35-4.35" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
          </svg>
          <input
            type="text"
            placeholder="Search incidents, repos, commits..."
            className="input"
            style={{ paddingLeft: "2.5rem", background: "var(--bg-surface)", height: "36px" }}
          />
        </div>

        <div style={{ display: "flex", gap: "0.375rem" }}>
          {STATUS_FILTERS.map((f) => (
            <button
              key={f.value}
              onClick={() => setActiveFilter(f.value)}
              style={{
                padding: "0 0.875rem",
                height: "36px",
                borderRadius: "var(--radius-md)",
                border: "1px solid",
                fontSize: "0.75rem",
                fontWeight: activeFilter === f.value ? 600 : 500,
                cursor: "pointer",
                transition: "all 0.15s ease",
                background: activeFilter === f.value ? "var(--bg-surface-2)" : "var(--bg-surface)",
                color: activeFilter === f.value ? "var(--text-primary)" : "var(--text-secondary)",
                borderColor: activeFilter === f.value ? "var(--border-strong)" : "var(--border)",
                boxShadow: activeFilter === f.value ? "var(--shadow-sm)" : "none",
              }}
            >
              {f.label}
            </button>
          ))}
        </div>
      </div>

      {/* ── List ── */}
      <div className="card" style={{ padding: 0, overflowX: "auto" }}>
        {loading && <LoadingState />}
        {error && (
          <div style={{ color: "var(--severity-critical)", fontSize: "0.875rem", padding: "3rem", textAlign: "center" }}>
            {error}
          </div>
        )}
        {!loading && !error && incidents.length === 0 && (
          <EmptyState filter={activeFilter} />
        )}
        {!loading && !error && incidents.length > 0 && (
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr style={{ borderBottom: "1px solid var(--border)", background: "var(--bg-surface-2)" }}>
                {["Status", "Incident", "Severity", "Type", "Repository", "When"].map((col) => (
                  <th
                    key={col}
                    style={{
                      padding: "0.875rem 1.5rem",
                      textAlign: "left",
                      fontSize: "0.6875rem",
                      fontWeight: 600,
                      letterSpacing: "0.06em",
                      textTransform: "uppercase",
                      color: "var(--text-muted)",
                      whiteSpace: "nowrap",
                    }}
                  >
                    {col}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {incidents.map((incident, i) => (
                <IncidentRow key={incident.id} incident={incident} index={i} />
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

function IncidentRow({ incident, index }: { incident: IncidentListItem; index: number }) {
  return (
    <tr
      style={{
        borderBottom: "1px solid var(--border-subtle)",
        cursor: "pointer",
        transition: "background 0.1s ease",
        animationDelay: `${index * 0.04}s`,
      }}
      onMouseEnter={(e) => {
        (e.currentTarget as HTMLTableRowElement).style.background = "var(--bg-surface-2)";
      }}
      onMouseLeave={(e) => {
        (e.currentTarget as HTMLTableRowElement).style.background = "transparent";
      }}
      onClick={() => {
        window.location.href = `/dashboard/incidents/${incident.id}`;
      }}
    >
      <td style={{ padding: "0.875rem 1.25rem", whiteSpace: "nowrap" }}>
        <span className={`status-chip status-chip-${incident.status}`}>
          {STATUS_LABELS[incident.status] ?? incident.status.toUpperCase()}
        </span>
      </td>
      <td style={{ padding: "0.875rem 1.25rem", minWidth: "200px", maxWidth: "350px" }}>
        <p
          style={{
            fontSize: "0.8125rem",
            color: "var(--text-primary)",
            fontWeight: 500,
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
          }}
        >
          {incident.title}
        </p>
        {incident.commit_sha && (
          <p
            style={{
              fontSize: "0.6875rem",
              color: "var(--text-dim)",
              fontFamily: "var(--font-mono)",
              marginTop: "0.125rem",
            }}
          >
            {incident.commit_sha.slice(0, 8)}
          </p>
        )}
      </td>
      <td style={{ padding: "0.875rem 1.25rem", whiteSpace: "nowrap" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "0.375rem" }}>
          <div
            style={{
              width: "6px",
              height: "6px",
              borderRadius: "50%",
              background:
                incident.severity === "critical"
                  ? "var(--severity-critical)"
                  : incident.severity === "high"
                  ? "var(--severity-high)"
                  : incident.severity === "medium"
                  ? "var(--severity-medium)"
                  : "var(--text-dim)",
            }}
          />
          <span className={`severity-${incident.severity}`} style={{ fontSize: "0.75rem", fontWeight: 500 }}>
            {SEVERITY_LABELS[incident.severity] ?? incident.severity}
          </span>
        </div>
      </td>
      <td style={{ padding: "0.875rem 1.25rem", whiteSpace: "nowrap" }}>
        <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
          {FAILURE_TYPE_LABELS[incident.failure_type] ?? incident.failure_type}
        </span>
      </td>
      <td style={{ padding: "0.875rem 1.25rem", whiteSpace: "nowrap" }}>
        <span
          style={{
            fontSize: "0.75rem",
            color: "var(--text-muted)",
            fontFamily: "var(--font-mono)",
          }}
        >
          {incident.repository_full_name ?? "—"}
        </span>
      </td>
      <td style={{ padding: "0.875rem 1.25rem", whiteSpace: "nowrap" }}>
        <span style={{ fontSize: "0.75rem", color: "var(--text-dim)" }}>
          {formatRelative(incident.created_at)}
        </span>
      </td>
    </tr>
  );
}

function EmptyState({ filter }: { filter: string }) {
  return (
    <div
      style={{
        padding: "4rem 0",
        textAlign: "center",
        color: "var(--text-muted)",
        fontSize: "0.875rem",
      }}
    >
      {filter === "all"
        ? "No incidents yet. Connect a repository to start monitoring."
        : `No incidents with status "${filter}".`}
    </div>
  );
}

function LoadingState() {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
      {[...Array(5)].map((_, i) => (
        <div
          key={i}
          style={{
            height: "5rem",
            background: "var(--bg-surface)",
            border: "1px solid var(--border)",
            borderRadius: "var(--radius-md)",
            opacity: 1 - i * 0.15,
            animation: "pulse-subtle 1.5s ease-in-out infinite",
            animationDelay: `${i * 0.1}s`,
          }}
        />
      ))}
    </div>
  );
}

function formatRelative(dateStr: string): string {
  const date = new Date(dateStr);
  const now = new Date();
  const diff = now.getTime() - date.getTime();
  const mins = Math.floor(diff / 60000);
  const hours = Math.floor(diff / 3600000);
  const days = Math.floor(diff / 86400000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  if (hours < 24) return `${hours}h ago`;
  return `${days}d ago`;
}
