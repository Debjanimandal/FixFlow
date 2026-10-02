"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  repositories as reposApi,
  type Repository,
  type GitHubRepo,
  type VercelProject,
  type DeploymentStatusResponse,
} from "@/lib/api-client";

// ─────────────────────────────────────────────────────────────────────────────
// Page
// ─────────────────────────────────────────────────────────────────────────────

export default function RepositoriesPage() {
  const [repos, setRepos] = useState<Repository[]>([]);
  const [loadingRepos, setLoadingRepos] = useState(true);
  const [fetchError, setFetchError] = useState<string | null>(null);
  const [showPicker, setShowPicker] = useState(false);
  const [vercelProjects, setVercelProjects] = useState<VercelProject[]>([]);

  function loadRepos() {
    setLoadingRepos(true);
    setFetchError(null);
    reposApi
      .list()
      .then((data) => { setRepos(data); setFetchError(null); })
      .catch((e) => setFetchError(e?.detail ?? e?.message ?? "Cannot reach backend. Is the server running?"))
      .finally(() => setLoadingRepos(false));
    // Load Vercel projects, then auto-sync to populate DB matches
    reposApi.listVercelProjects()
      .then((projects) => {
        // Deduplicate by project id — Vercel API can return the same project
        // more than once when a team and personal account share a project.
        const unique = Array.from(new Map(projects.map((p) => [p.id, p])).values());
        setVercelProjects(unique);

        if (projects.length > 0) {
          // Auto-match repos to Vercel projects via linked_repo field
          reposApi.vercelSync().then(() => {
            // Reload repos so any auto-matched vercel_project_name appears
            reposApi.list().then(setRepos).catch(() => {});
          }).catch(() => {});
        }
      })
      .catch(() => {}); // silent fail — just means no picker
  }

  useEffect(() => { loadRepos(); }, []);

  function handleConnected(repo: Repository) {
    setRepos((prev) => [repo, ...prev]);
    setShowPicker(false);
  }

  async function handleDisconnect(id: string) {
    if (!confirm("Disconnect this repository? All associated incidents will remain but monitoring stops.")) return;
    await reposApi.delete(id);
    setRepos((prev) => prev.filter((r) => r.id !== id));
  }

  function handleVercelLinked(repoId: string, projectId: string, projectName: string) {
    setRepos((prev) =>
      prev.map((r) =>
        r.id === repoId ? { ...r, vercel_project_id: projectId, vercel_project_name: projectName } : r
      )
    );
  }

  return (
    <div style={{ padding: "2.5rem" }}>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: "2.5rem" }}>
        <div>
          <h1 style={{ fontSize: "1.25rem", marginBottom: "0.25rem" }}>Repositories</h1>
          <p style={{ fontSize: "0.875rem", color: "var(--text-muted)" }}>
            GitHub repositories connected to FixFlow for autonomous monitoring.
          </p>
        </div>
        <button
          className="btn btn-primary"
          onClick={() => setShowPicker(!showPicker)}
          style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}
        >
          {showPicker ? (
            "Cancel"
          ) : (
            <>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
                <path d="M12 5v14M5 12h14" />
              </svg>
              Import Repository
            </>
          )}
        </button>
      </div>

      {/* GitHub Repo Picker (Vercel-style) */}
      {showPicker && (
        <GitHubRepoPicker
          connectedRepos={repos}
          onConnected={handleConnected}
        />
      )}

      {/* Backend / DB error banner */}
      {fetchError && (
        <div style={{
          marginBottom: "1.5rem", padding: "1rem 1.25rem",
          background: "rgba(239,68,68,0.07)", border: "1px solid rgba(239,68,68,0.3)",
          borderRadius: "10px", display: "flex", alignItems: "center", gap: "1rem",
        }}>
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#f87171" strokeWidth="2" strokeLinecap="round" style={{ flexShrink: 0 }}>
            <circle cx="12" cy="12" r="10" /><line x1="12" y1="8" x2="12" y2="12" /><line x1="12" y1="16" x2="12.01" y2="16" />
          </svg>
          <div style={{ flex: 1 }}>
            <p style={{ fontSize: "0.875rem", fontWeight: 600, color: "#f87171", margin: "0 0 0.125rem" }}>
              Backend unreachable
            </p>
            <p style={{ fontSize: "0.8125rem", color: "var(--text-muted)", margin: 0 }}>
              {fetchError}
            </p>
          </div>
          <button
            onClick={loadRepos}
            className="btn btn-ghost"
            style={{ fontSize: "0.75rem", flexShrink: 0 }}
          >
            Retry
          </button>
        </div>
      )}

      {/* Connected repos list */}
      {loadingRepos ? (
        <LoadingSkeleton />
      ) : repos.length === 0 && !showPicker && !fetchError ? (
        <EmptyState onImport={() => setShowPicker(true)} />
      ) : repos.length > 0 ? (
        <div className="card" style={{ padding: 0, overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr style={{ borderBottom: "1px solid var(--border)", background: "var(--bg-surface-2)" }}>
                {["Repository", "Integrations", "Monitoring", ""].map((col) => (
                  <th key={col} style={{
                    padding: "0.875rem 1.5rem", textAlign: "left",
                    fontSize: "0.6875rem", fontWeight: 600, letterSpacing: "0.06em",
                    textTransform: "uppercase", color: "var(--text-muted)", whiteSpace: "nowrap",
                  }}>
                    {col}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {repos.map((repo, i) => (
                <RepoRow
                  key={repo.id}
                  repo={repo}
                  onDisconnect={handleDisconnect}
                  index={i}
                  vercelProjects={vercelProjects}
                  onVercelLinked={handleVercelLinked}
                />
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// GitHub Repo Picker — Vercel-style
// ─────────────────────────────────────────────────────────────────────────────

function GitHubRepoPicker({
  connectedRepos,
  onConnected,
}: {
  connectedRepos: Repository[];
  onConnected: (repo: Repository) => void;
}) {
  const [githubRepos, setGithubRepos] = useState<GitHubRepo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [connecting, setConnecting] = useState<string | null>(null); // full_name being connected
  const [connectError, setConnectError] = useState<string | null>(null);

  const connectedSet = new Set(connectedRepos.map((r) => r.full_name));

  useEffect(() => {
    reposApi
      .listGitHubRepos()
      .then(setGithubRepos)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  const filtered = githubRepos.filter((r) =>
    r.full_name.toLowerCase().includes(search.toLowerCase())
  );

  async function handleImport(ghRepo: GitHubRepo) {
    if (connecting) return;
    setConnecting(ghRepo.full_name);
    setConnectError(null);
    try {
      const repo = await reposApi.create({ full_name: ghRepo.full_name });
      onConnected(repo);
    } catch (e: any) {
      setConnectError(e.detail ?? e.message ?? "Failed to connect");
      setConnecting(null);
    }
  }

  return (
    <div className="card" style={{ marginBottom: "2rem", padding: 0, overflow: "hidden" }}>
      {/* Title bar */}
      <div style={{
        padding: "1.25rem 1.5rem",
        borderBottom: "1px solid var(--border-subtle)",
        display: "flex", alignItems: "center", gap: "0.75rem",
      }}>
        <GitHubIcon size={18} />
        <span style={{ fontSize: "0.9375rem", fontWeight: 600, color: "var(--text-primary)" }}>
          Import Git Repository
        </span>
        <span style={{
          marginLeft: "auto", fontSize: "0.6875rem", color: "var(--text-muted)",
          fontWeight: 500,
        }}>
          {loading ? "Loading…" : `${githubRepos.length} repositories`}
        </span>
      </div>

      {/* Search */}
      <div style={{ padding: "0.875rem 1.5rem", borderBottom: "1px solid var(--border-subtle)" }}>
        <div style={{ position: "relative" }}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
            style={{ position: "absolute", left: "0.75rem", top: "50%", transform: "translateY(-50%)", color: "var(--text-dim)", pointerEvents: "none" }}>
            <circle cx="11" cy="11" r="8" /><path d="M21 21l-4.35-4.35" strokeLinecap="round" />
          </svg>
          <input
            type="text"
            placeholder="Search repositories…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            style={{
              width: "100%", height: "36px", paddingLeft: "2.25rem", paddingRight: "1rem",
              background: "var(--bg-surface-2)", border: "1px solid var(--border)",
              borderRadius: "8px", fontSize: "0.875rem", color: "var(--text-primary)",
              outline: "none",
            }}
          />
        </div>
      </div>

      {/* Error banner */}
      {connectError && (
        <div style={{
          margin: "0 1.5rem", marginTop: "1rem",
          padding: "0.75rem 1rem", borderRadius: "8px",
          background: "rgba(239,68,68,0.08)", border: "1px solid rgba(239,68,68,0.3)",
          fontSize: "0.8125rem", color: "#f87171",
        }}>
          {connectError}
        </div>
      )}

      {/* List */}
      <div style={{ maxHeight: "460px", overflowY: "auto" }}>
        {loading ? (
          <div style={{ padding: "3rem", textAlign: "center" }}>
            <LoadingSpinner />
            <p style={{ marginTop: "1rem", fontSize: "0.875rem", color: "var(--text-muted)" }}>
              Fetching your GitHub repositories…
            </p>
          </div>
        ) : error ? (
          <div style={{ padding: "2rem 1.5rem", textAlign: "center" }}>
            <p style={{ fontSize: "0.875rem", color: "var(--severity-critical)" }}>{error}</p>
            <p style={{ fontSize: "0.8125rem", color: "var(--text-muted)", marginTop: "0.5rem" }}>
              Make sure GITHUB_TOKEN is set in your .env file.
            </p>
          </div>
        ) : filtered.length === 0 ? (
          <div style={{ padding: "2rem 1.5rem", textAlign: "center" }}>
            <p style={{ fontSize: "0.875rem", color: "var(--text-muted)" }}>
              No repositories found{search ? ` matching "${search}"` : ""}.
            </p>
          </div>
        ) : (
          filtered.map((repo) => {
            const isConnected = connectedSet.has(repo.full_name);
            const isConnecting = connecting === repo.full_name;
            return (
              <div
                key={repo.id}
                style={{
                  display: "flex", alignItems: "center", gap: "1rem",
                  padding: "0.875rem 1.5rem",
                  borderBottom: "1px solid var(--border-subtle)",
                  transition: "background 0.1s",
                  background: isConnected ? "var(--bg-surface-2)" : "transparent",
                }}
                onMouseEnter={e => {
                  if (!isConnected) (e.currentTarget as HTMLDivElement).style.background = "var(--bg-surface-2)";
                }}
                onMouseLeave={e => {
                  if (!isConnected) (e.currentTarget as HTMLDivElement).style.background = "transparent";
                }}
              >
                {/* Repo icon / avatar */}
                <div style={{
                  width: "36px", height: "36px", borderRadius: "8px",
                  background: "var(--bg-surface)", border: "1px solid var(--border)",
                  display: "flex", alignItems: "center", justifyContent: "center",
                  flexShrink: 0, color: "var(--text-secondary)",
                }}>
                  {repo.private ? <LockIcon /> : <RepoIcon />}
                </div>

                {/* Info */}
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.125rem" }}>
                    <span style={{
                      fontSize: "0.875rem", fontWeight: 600,
                      color: "var(--text-primary)", fontFamily: "var(--font-mono)",
                      overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
                    }}>
                      {repo.full_name}
                    </span>
                    {repo.private && (
                      <span style={{
                        fontSize: "0.625rem", fontWeight: 600, padding: "0.125rem 0.375rem",
                        borderRadius: "9999px", border: "1px solid var(--border-strong)",
                        color: "var(--text-dim)", flexShrink: 0,
                      }}>
                        PRIVATE
                      </span>
                    )}
                    {repo.language && (
                      <span style={{ fontSize: "0.75rem", color: "var(--text-dim)", flexShrink: 0 }}>
                        {repo.language}
                      </span>
                    )}
                  </div>
                  <p style={{
                    fontSize: "0.75rem", color: "var(--text-muted)", margin: 0,
                    overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
                  }}>
                    {repo.description || `${repo.default_branch} · Updated ${formatDate(repo.updated_at)}`}
                  </p>
                </div>

                {/* Action */}
                {isConnected ? (
                  <span style={{
                    flexShrink: 0, fontSize: "0.75rem", fontWeight: 600,
                    padding: "0.375rem 0.875rem", borderRadius: "6px",
                    background: "#ECFDF5", color: "#047857", border: "1px solid #34D399",
                  }}>
                    Connected
                  </span>
                ) : (
                  <button
                    onClick={() => handleImport(repo)}
                    disabled={!!connecting}
                    style={{
                      flexShrink: 0, padding: "0.375rem 1rem", borderRadius: "6px",
                      fontSize: "0.8125rem", fontWeight: 600, cursor: connecting ? "not-allowed" : "pointer",
                      background: isConnecting ? "var(--accent-dim)" : "var(--accent)",
                      color: "#fff", border: "none",
                      opacity: (connecting && !isConnecting) ? 0.5 : 1,
                      display: "flex", alignItems: "center", gap: "0.375rem",
                      transition: "opacity 0.15s",
                    }}
                  >
                    {isConnecting ? (
                      <>
                        <MiniSpinner />
                        Connecting…
                      </>
                    ) : (
                      "Import"
                    )}
                  </button>
                )}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Connected Repo Row
// ─────────────────────────────────────────────────────────────────────────────

function RepoRow({ repo, onDisconnect, index, vercelProjects, onVercelLinked }: {
  repo: Repository;
  onDisconnect: (id: string) => void;
  index: number;
  vercelProjects: VercelProject[];
  onVercelLinked: (repoId: string, projectId: string, projectName: string) => void;
}) {
  const [showVercelPicker, setShowVercelPicker] = useState(false);
  const [selectedProjectId, setSelectedProjectId] = useState("");
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState("");
  const [depStatus, setDepStatus] = useState<DeploymentStatusResponse | null>(null);

  // Fetch live deployment status (works for all repos via GitHub Deployments API)
  useEffect(() => {
    let cancelled = false;
    function fetchStatus() {
      reposApi.getDeploymentStatus(repo.id)
        .then((data) => { if (!cancelled) setDepStatus(data); })
        .catch(() => {});
    }
    fetchStatus();
    const interval = setInterval(fetchStatus, 30000);
    return () => { cancelled = true; clearInterval(interval); };
  }, [repo.id]);

  // Auto-save Vercel link when an auto-match is found (no button click required)
  useEffect(() => {
    if (repo.vercel_project_id) return; // already linked
    const autoMatch = vercelProjects.find(
      (p) => p.linked_repo?.toLowerCase() === repo.full_name.toLowerCase()
    );
    if (!autoMatch) return;
    // Silently link in the background
    reposApi.linkVercel(repo.id, autoMatch.id)
      .then((updated) => {
        if (updated.vercel_project_id && updated.vercel_project_name) {
          onVercelLinked(repo.id, updated.vercel_project_id, updated.vercel_project_name);
        }
      })
      .catch(() => {}); // silent — user can still manually link via picker
  }, [repo.id, repo.full_name, repo.vercel_project_id, vercelProjects]);


  async function handleSaveVercelLink() {
    if (!selectedProjectId) return;
    setSaving(true);
    setSaveError("");
    try {
      const updated = await reposApi.linkVercel(repo.id, selectedProjectId);
      onVercelLinked(repo.id, updated.vercel_project_id!, updated.vercel_project_name!);
      setShowVercelPicker(false);
      setSelectedProjectId("");
    } catch (e: any) {
      setSaveError(e.detail ?? "Verification failed — this project may not exist in your Vercel account.");
    } finally {
      setSaving(false);
    }
  }

  async function handleUnlinkVercel() {
    if (!confirm(`Unlink "${repo.vercel_project_name}" from this repository?`)) return;
    try {
      await reposApi.update(repo.id, { vercel_project_id: "", vercel_project_name: "" });
      onVercelLinked(repo.id, "", "");
    } catch (e: any) {
      alert(e.detail ?? "Failed to unlink");
    }
  }

  return (
    <>
      <tr
        style={{ borderBottom: showVercelPicker ? "none" : "1px solid var(--border)", transition: "background 0.1s", animationDelay: `${index * 0.04}s` }}
        onMouseEnter={e => (e.currentTarget.style.background = "var(--bg-surface-2)")}
        onMouseLeave={e => (e.currentTarget.style.background = "transparent")}
      >
        <td style={{ padding: "1rem 1.5rem" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "1rem" }}>
            <div style={{
              width: "36px", height: "36px", borderRadius: "8px",
              border: "1px solid var(--border)", background: "var(--bg-surface)",
              display: "flex", alignItems: "center", justifyContent: "center",
              flexShrink: 0, color: "var(--text-secondary)",
            }}>
              <RepoIcon />
            </div>
            <div>
              <p style={{ fontSize: "0.875rem", fontWeight: 600, color: "var(--text-primary)", fontFamily: "var(--font-mono)", marginBottom: "0.125rem" }}>
                {repo.full_name}
              </p>
              <p style={{ fontSize: "0.75rem", color: "var(--text-dim)" }}>
                branch: {repo.default_branch} {repo.private && "· private"}
              </p>
            </div>
          </div>
        </td>
        <td style={{ padding: "1rem 1.5rem" }}>
          <div style={{ display: "flex", flexDirection: "column", gap: "0.375rem" }}>
            <span style={{ fontSize: "0.75rem", color: "var(--text-secondary)", display: "flex", alignItems: "center", gap: "0.375rem" }}>
              <GitHubIcon size={12} />
              GitHub
            </span>
            {repo.vercel_project_name ? (
              // ── Already linked ──────────────────────────────────
              <span style={{ fontSize: "0.75rem", color: "#10B981", display: "flex", alignItems: "center", gap: "0.375rem" }}>
                <VercelIcon size={11} color="#10B981" />
                Deployed on Vercel
                <button
                  onClick={handleUnlinkVercel}
                  style={{ fontSize: "0.625rem", color: "var(--text-dim)", background: "none", border: "none", cursor: "pointer", padding: 0, marginLeft: "0.125rem" }}
                  title="Unlink Vercel project"
                >
                  ✕
                </button>
              </span>
            ) : (() => {
              // Check if any Vercel project auto-matches this repo
              const autoMatch = vercelProjects.find(
                (p) => p.linked_repo?.toLowerCase() === repo.full_name.toLowerCase()
              );
              if (autoMatch) {
                // ── Auto-match found — show Connect button ────────
                return (
                  <button
                    onClick={() => {
                      setSelectedProjectId(autoMatch.id);
                      setShowVercelPicker(true);
                    }}
                    style={{
                      fontSize: "0.6875rem", fontWeight: 600,
                      color: "#6366f1", background: "rgba(99,102,241,0.08)",
                      border: "1px solid rgba(99,102,241,0.25)",
                      borderRadius: "9999px", cursor: "pointer",
                      padding: "0.2rem 0.6rem",
                      display: "flex", alignItems: "center", gap: "0.3rem",
                    }}
                  >
                    <VercelIcon size={10} color="#6366f1" />
                    Connect to {autoMatch.name}
                  </button>
                );
              }
              // ── No match — Not on Vercel ──────────────────────
              return (
                <span style={{ fontSize: "0.75rem", color: "var(--text-dim)", display: "flex", alignItems: "center", gap: "0.375rem" }}>
                  <VercelIcon size={11} color="var(--text-dim)" />
                  Not deployed on Vercel
                  {vercelProjects.length > 0 && (
                    <button
                      onClick={() => setShowVercelPicker((v) => !v)}
                      style={{ fontSize: "0.6875rem", color: "var(--accent)", background: "none", border: "none", cursor: "pointer", padding: 0, marginLeft: "0.125rem" }}
                    >
                      {showVercelPicker ? "cancel" : "link anyway"}
                    </button>
                  )}
                </span>
              );
            })()}
          </div>
        </td>
        <td style={{ padding: "1rem 1.5rem" }}>
          {depStatus?.latest_state ? (
            <LiveDeployBadge state={depStatus.latest_state} />
          ) : (
            <span style={{
              fontSize: "0.75rem", fontWeight: 500, display: "flex", alignItems: "center", gap: "0.375rem",
              color: repo.webhook_active ? "#10B981" : "var(--text-dim)",
            }}>
              <span style={{ width: "6px", height: "6px", borderRadius: "50%", background: repo.webhook_active ? "#10B981" : "var(--border-strong)", display: "inline-block" }} />
              {repo.webhook_active ? "Webhook Active" : "Waiting for events"}
            </span>
          )}
        </td>
        <td style={{ padding: "1rem 1.5rem", textAlign: "right" }}>
          <div style={{ display: "flex", gap: "0.5rem", justifyContent: "flex-end" }}>
            <Link href={`/dashboard/repositories/${repo.id}`} className="btn btn-ghost" style={{ fontSize: "0.75rem", padding: "0.375rem 0.75rem" }}>
              Open
            </Link>
            <button
              className="btn btn-ghost"
              style={{ fontSize: "0.75rem", color: "var(--severity-critical)", padding: "0.375rem 0.75rem" }}
              onClick={() => onDisconnect(repo.id)}
            >
              Disconnect
            </button>
          </div>
        </td>
      </tr>
      {/* Inline Vercel project picker */}
      {showVercelPicker && (
        <tr style={{ borderBottom: "1px solid var(--border)" }}>
          <td colSpan={4} style={{ padding: "0.75rem 1.5rem 1rem", background: "var(--bg-surface-2)" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", flexWrap: "wrap" }}>
              <VercelIcon size={14} />
              <span style={{ fontSize: "0.8125rem", color: "var(--text-secondary)", fontWeight: 500 }}>Link to Vercel project:</span>
              {vercelProjects.length === 0 ? (
                <span style={{ fontSize: "0.8125rem", color: "var(--text-dim)" }}>No Vercel projects found — check VERCEL_ACCESS_TOKEN in .env</span>
              ) : (
                <>
                  <select
                    value={selectedProjectId}
                    onChange={(e) => setSelectedProjectId(e.target.value)}
                    style={{
                      flex: 1, minWidth: "200px", padding: "0.375rem 0.75rem",
                      background: "var(--bg-surface)", border: "1px solid var(--border)",
                      borderRadius: "6px", color: "var(--text-primary)", fontSize: "0.8125rem",
                    }}
                  >
                    <option value="">— select a project —</option>
                    {Array.from(new Map(vercelProjects.map((p) => [p.id, p])).values()).map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.name}{p.linked_repo ? ` (${p.linked_repo})` : ""}
                      </option>
                    ))}

                  </select>
                  <button
                    onClick={handleSaveVercelLink}
                    disabled={!selectedProjectId || saving}
                    className="btn btn-primary"
                    style={{ padding: "0.375rem 0.875rem", fontSize: "0.75rem" }}
                  >
                    {saving ? "Saving…" : "Save"}
                  </button>
                </>
              )}
              {saveError && <span style={{ fontSize: "0.75rem", color: "#f87171" }}>{saveError}</span>}
            </div>
          </td>
        </tr>
      )}
    </>
  );
}


// ─────────────────────────────────────────────────────────────────────────────
// Empty state
// ─────────────────────────────────────────────────────────────────────────────

function EmptyState({ onImport }: { onImport: () => void }) {
  return (
    <div style={{
      border: "1px dashed var(--border-strong)", borderRadius: "12px",
      padding: "5rem 2rem", textAlign: "center",
    }}>
      <div style={{
        width: "52px", height: "52px", borderRadius: "12px",
        border: "1px solid var(--border)", background: "var(--bg-surface)",
        display: "flex", alignItems: "center", justifyContent: "center",
        color: "var(--text-dim)", margin: "0 auto 1.5rem",
      }}>
        <GitHubIcon size={24} />
      </div>
      <p style={{ fontSize: "0.9375rem", fontWeight: 600, color: "var(--text-primary)", marginBottom: "0.5rem" }}>
        No repositories connected yet
      </p>
      <p style={{ fontSize: "0.875rem", color: "var(--text-muted)", marginBottom: "2rem", maxWidth: "380px", margin: "0 auto 2rem" }}>
        Import a GitHub repository to start autonomous monitoring and AI-powered patch generation.
      </p>
      <button className="btn btn-primary" onClick={onImport} style={{ display: "inline-flex", alignItems: "center", gap: "0.5rem" }}>
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
          <path d="M12 5v14M5 12h14" />
        </svg>
        Import Repository
      </button>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Live Deployment Badge (for repo list)
// ─────────────────────────────────────────────────────────────────────────────

function LiveDeployBadge({ state }: { state: string }) {
  const colorMap: Record<string, string> = {
    READY: "#10B981",
    ERROR: "#EF4444",
    BUILDING: "#F59E0B",
    QUEUED: "#6366F1",
    CANCELED: "#6B7280",
  };
  const labelMap: Record<string, string> = {
    READY: "Deployed",
    ERROR: "Build Failed",
    BUILDING: "Building...",
    QUEUED: "Queued",
    CANCELED: "Canceled",
  };
  const color = colorMap[state] ?? "#6B7280";
  const label = labelMap[state] ?? state;

  return (
    <span style={{
      fontSize: "0.6875rem", fontWeight: 600, padding: "0.2rem 0.6rem",
      borderRadius: "9999px",
      background: `${color}15`,
      color,
      border: `1px solid ${color}40`,
      display: "inline-flex", alignItems: "center", gap: "0.3rem",
      whiteSpace: "nowrap",
    }}>
      <span style={{
        width: "6px", height: "6px", borderRadius: "50%", background: color,
        display: "inline-block",
        animation: state === "BUILDING" ? "pulse 1.5s ease-in-out infinite" : "none",
      }} />
      {label}
    </span>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Utilities & Icons
// ─────────────────────────────────────────────────────────────────────────────

function formatDate(iso: string): string {
  if (!iso) return "";
  try {
    const d = new Date(iso);
    const now = new Date();
    const diffDays = Math.floor((now.getTime() - d.getTime()) / 86400000);
    if (diffDays === 0) return "today";
    if (diffDays === 1) return "yesterday";
    if (diffDays < 30) return `${diffDays}d ago`;
    if (diffDays < 365) return `${Math.floor(diffDays / 30)}mo ago`;
    return `${Math.floor(diffDays / 365)}y ago`;
  } catch { return ""; }
}

function GitHubIcon({ size = 16 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="currentColor">
      <path d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z" />
    </svg>
  );
}

function RepoIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M9 19c-5 1.5-5-2.5-7-3m14 6v-3.87a3.37 3.37 0 0 0-.94-2.61c3.14-.35 6.44-1.54 6.44-7A5.44 5.44 0 0 0 20 4.77 5.07 5.07 0 0 0 19.91 1S18.73.65 16 2.48a13.38 13.38 0 0 0-7 0C6.27.65 5.09 1 5.09 1A5.07 5.07 0 0 0 5 4.77a5.44 5.44 0 0 0-1.5 3.78c0 5.42 3.3 6.61 6.44 7A3.37 3.37 0 0 0 9 18.13V22" />
    </svg>
  );
}

function VercelIcon({ size = 16, color = "white" }: { size?: number; color?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill={color}>
      <path d="M12 1L24 22H0L12 1Z" />
    </svg>
  );
}

function LockIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
      <path d="M7 11V7a5 5 0 0110 0v4" />
    </svg>
  );
}

function LoadingSpinner() {
  return (
    <svg width="36" height="36" viewBox="0 0 36 36" fill="none" style={{ animation: "spin 0.9s linear infinite", margin: "0 auto", display: "block" }}>
      <circle cx="18" cy="18" r="14" stroke="rgba(99,102,241,0.15)" strokeWidth="3" />
      <circle cx="18" cy="18" r="14" stroke="#6366f1" strokeWidth="3" strokeDasharray="44" strokeDashoffset="14" strokeLinecap="round" />
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </svg>
  );
}

function MiniSpinner() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none" style={{ animation: "spin 0.9s linear infinite" }}>
      <circle cx="7" cy="7" r="5" stroke="rgba(255,255,255,0.3)" strokeWidth="2" />
      <circle cx="7" cy="7" r="5" stroke="white" strokeWidth="2" strokeDasharray="16" strokeDashoffset="6" strokeLinecap="round" />
    </svg>
  );
}

function LoadingSkeleton() {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
      {[...Array(4)].map((_, i) => (
        <div key={i} style={{
          height: "4.5rem", background: "var(--bg-surface)", border: "1px solid var(--border)",
          borderRadius: "10px", animation: "pulse-subtle 1.5s ease-in-out infinite", animationDelay: `${i * 0.1}s`,
        }} />
      ))}
    </div>
  );
}
