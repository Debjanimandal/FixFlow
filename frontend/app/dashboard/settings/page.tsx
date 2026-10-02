"use client";

import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { auth, repositories as reposApi, type VercelProject } from "@/lib/api-client";

function decodeJwtPayload(token: string): Record<string, string> | null {
  try {
    const base64 = token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/");
    return JSON.parse(atob(base64));
  } catch {
    return null;
  }
}

const VERCEL_OAUTH_ERROR_MESSAGES: Record<string, string> = {
  invalid_state: "Vercel sign-in session expired. Please try connecting again.",
  state_mismatch: "Vercel sign-in could not be verified. Please try connecting again.",
  token_exchange_failed: "Vercel rejected the connection request. Please try again.",
  no_token: "Vercel did not return an access token. Please try again.",
  user_not_found: "Could not find your FixFlow account. Please sign in again.",
  invalid_user_id: "Your user session could not be verified. Please try connecting again.",
};

export default function SettingsPage() {
  return (
    <Suspense fallback={null}>
      <SettingsPageInner />
    </Suspense>
  );
}

function SettingsPageInner() {
  const searchParams = useSearchParams();
  const [githubUser, setGithubUser] = useState<{ login: string; name: string; avatar: string } | null>(null);

  // Vercel OAuth (account-level "Sign in with Vercel")
  const [vercelOAuthStatus, setVercelOAuthStatus] = useState<{ connected: boolean; message: string } | null>(null);
  const [connectingOAuth, setConnectingOAuth] = useState(false);
  const [oauthMsg, setOauthMsg] = useState<{ type: "success" | "error"; text: string } | null>(null);

  // Vercel token state
  const [vercelTokenInput, setVercelTokenInput] = useState("");
  const [vercelTokenStatus, setVercelTokenStatus] = useState<{ has_token: boolean; token_preview?: string } | null>(null);
  const [savingToken, setSavingToken] = useState(false);
  const [tokenMsg, setTokenMsg] = useState<{ type: "success" | "error"; text: string } | null>(null);

  // Vercel projects (loaded after token is confirmed)
  const [vercelProjects, setVercelProjects] = useState<VercelProject[]>([]);
  const [loadingProjects, setLoadingProjects] = useState(false);

  useEffect(() => {
    const token = localStorage.getItem("patchr_token");
    if (!token) return;
    const payload = decodeJwtPayload(token);
    if (payload?.github_login) {
      setGithubUser({
        login: payload.github_login,
        name: payload.github_name || payload.github_login,
        avatar: payload.github_avatar || "",
      });
    }
    // Check if user already has a vercel token saved (PAT or OAuth-issued — both
    // are stored on the same column and power the same downstream API calls)
    auth.getVercelTokenStatus()
      .then((status) => {
        setVercelTokenStatus(status);
        if (status.has_token) loadProjects();
      })
      .catch(() => {});
    auth.getVercelConnectionStatus()
      .then(setVercelOAuthStatus)
      .catch(() => {});
  }, []);

  // Handle the redirect back from /auth/vercel/callback
  useEffect(() => {
    const vercelResult = searchParams.get("vercel");
    if (!vercelResult) return;
    if (vercelResult === "connected") {
      setOauthMsg({ type: "success", text: "Vercel account connected. You can now scan runtime logs." });
      auth.getVercelConnectionStatus().then((status) => {
        setVercelOAuthStatus(status);
        if (status.connected) loadProjects();
      }).catch(() => {});
    } else if (vercelResult === "error") {
      const reason = searchParams.get("reason") ?? "";
      setOauthMsg({
        type: "error",
        text: VERCEL_OAUTH_ERROR_MESSAGES[reason] ?? "Could not connect your Vercel account. Please try again.",
      });
    }
  }, [searchParams]);

  async function handleConnectVercelOAuth() {
    setConnectingOAuth(true);
    setOauthMsg(null);
    try {
      await auth.startVercelOAuth();
      // startVercelOAuth navigates away on success; nothing else to do here.
    } catch (e: any) {
      setOauthMsg({ type: "error", text: e.detail ?? e.message ?? "Failed to start Vercel connection" });
      setConnectingOAuth(false);
    }
  }

  async function loadProjects() {
    setLoadingProjects(true);
    try {
      const projects = await reposApi.listVercelProjects();
      setVercelProjects(projects);
    } catch {
      setVercelProjects([]);
    } finally {
      setLoadingProjects(false);
    }
  }

  async function handleSaveToken() {
    if (!vercelTokenInput.trim()) return;
    setSavingToken(true);
    setTokenMsg(null);
    try {
      const result = await auth.saveVercelToken(vercelTokenInput.trim());
      setVercelTokenStatus({ has_token: result.has_token, token_preview: vercelTokenInput.trim().slice(0, 8) + "…" });
      setVercelTokenInput("");
      setTokenMsg({ type: "success", text: result.message });
      if (result.has_token) loadProjects();
    } catch (e: any) {
      setTokenMsg({ type: "error", text: e.detail ?? e.message ?? "Failed to save token" });
    } finally {
      setSavingToken(false);
    }
  }

  async function handleRemoveToken() {
    setSavingToken(true);
    setOauthMsg(null);
    try {
      await auth.saveVercelToken("");
      setVercelOAuthStatus({ connected: false, message: "" });
      setVercelTokenStatus({ has_token: false });
      setVercelProjects([]);
      setOauthMsg({ type: "success", text: "Vercel account disconnected." });
    } catch (e: any) {
      setOauthMsg({ type: "error", text: e.detail ?? "Failed to disconnect Vercel" });
    } finally {
      setSavingToken(false);
    }
  }

  return (
    <div style={{ padding: "2.5rem", maxWidth: "720px" }}>
      <div style={{ marginBottom: "2.5rem" }}>
        <h1 style={{ fontSize: "1.25rem", marginBottom: "0.25rem" }}>Settings</h1>
        <p style={{ fontSize: "0.875rem", color: "var(--text-muted)" }}>
          Manage your connected accounts and integrations.
        </p>
      </div>

      {/* ── GitHub Connected Account ──────────────────────────────── */}
      <div className="card" style={{ marginBottom: "1.5rem" }}>
        <p className="label" style={{ marginBottom: "1.25rem" }}>CONNECTED GIT ACCOUNT</p>
        {githubUser ? (
          <div style={{ display: "flex", alignItems: "center", gap: "1rem", padding: "1rem", background: "var(--bg-surface-2)", border: "1px solid var(--border-subtle)", borderRadius: "10px" }}>
            {githubUser.avatar ? (
              <img src={githubUser.avatar} alt={githubUser.login} width={44} height={44} style={{ borderRadius: "50%", flexShrink: 0 }} />
            ) : (
              <div style={{ width: "44px", height: "44px", borderRadius: "50%", background: "var(--accent-dim)", color: "var(--accent)", display: "flex", alignItems: "center", justifyContent: "center", fontWeight: 700, fontSize: "1rem", flexShrink: 0 }}>
                {githubUser.login[0].toUpperCase()}
              </div>
            )}
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.125rem" }}>
                <GitHubIcon size={15} />
                <span style={{ fontSize: "0.875rem", fontWeight: 600, color: "var(--text-primary)" }}>GitHub</span>
                <ConnectedBadge />
              </div>
              <p style={{ fontSize: "0.8125rem", color: "var(--text-secondary)", margin: 0 }}>
                {githubUser.name}
                <span style={{ color: "var(--text-dim)", marginLeft: "0.375rem" }}>@{githubUser.login}</span>
              </p>
            </div>
            <a href={`https://github.com/${githubUser.login}`} target="_blank" rel="noopener noreferrer"
              style={{ display: "flex", alignItems: "center", gap: "0.375rem", padding: "0.375rem 0.75rem", borderRadius: "6px", fontSize: "0.75rem", color: "var(--text-secondary)", border: "1px solid var(--border)", textDecoration: "none", flexShrink: 0 }}>
              <ExternalLinkIcon />View profile
            </a>
          </div>
        ) : (
          <div style={{ padding: "1rem", background: "var(--bg-surface-2)", border: "1px dashed var(--border)", borderRadius: "10px", textAlign: "center" }}>
            <p style={{ fontSize: "0.875rem", color: "var(--text-muted)" }}>Not connected. <a href="/login" style={{ color: "var(--accent)" }}>Sign in with GitHub</a></p>
          </div>
        )}
      </div>

      {/* ── Vercel Account ────────────────────────────────────────── */}
      <div className="card" style={{ marginBottom: "1.5rem" }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "1.25rem" }}>
          <p className="label">VERCEL ACCOUNT</p>
          {vercelOAuthStatus?.connected && (
            <ConnectedBadge />
          )}
        </div>

        {/* OAuth connect row */}
        <div style={{ display: "flex", alignItems: "center", gap: "1rem", padding: "1rem", background: "var(--bg-surface-2)", border: "1px solid var(--border-subtle)", borderRadius: "10px", marginBottom: "1.25rem" }}>
          <div style={{ width: "44px", height: "44px", borderRadius: "10px", background: "#000", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
            <VercelIcon />
          </div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <p style={{ fontSize: "0.875rem", fontWeight: 600, color: "var(--text-primary)", margin: 0 }}>Connect with Vercel</p>
            <p style={{ fontSize: "0.8125rem", color: "var(--text-muted)", margin: 0 }}>
              {vercelOAuthStatus?.connected
                ? "Your Vercel account is linked. FixFlow can read your runtime logs."
                : "One-click authorization — grants FixFlow access to your runtime logs."}
            </p>
          </div>
          {vercelOAuthStatus?.connected ? (
            <button
              onClick={handleRemoveToken}
              disabled={savingToken}
              style={{ fontSize: "0.75rem", color: "var(--severity-critical)", background: "none", border: "1px solid rgba(239,68,68,0.3)", borderRadius: "6px", padding: "0.375rem 0.75rem", cursor: "pointer", flexShrink: 0 }}
            >
              {savingToken ? "Disconnecting…" : "Disconnect"}
            </button>
          ) : (
            <button
              onClick={handleConnectVercelOAuth}
              disabled={connectingOAuth}
              className="btn btn-primary"
              style={{ padding: "0.5rem 1rem", fontSize: "0.8125rem", flexShrink: 0 }}
            >
              {connectingOAuth ? "Redirecting…" : "Connect Vercel"}
            </button>
          )}
        </div>

        {/* OAuth feedback message */}
        {oauthMsg && (
          <div style={{
            padding: "0.75rem 1rem", borderRadius: "8px",
            background: oauthMsg.type === "success" ? "rgba(16,185,129,0.08)" : "rgba(239,68,68,0.08)",
            border: `1px solid ${oauthMsg.type === "success" ? "rgba(16,185,129,0.3)" : "rgba(239,68,68,0.3)"}`,
            fontSize: "0.8125rem", color: oauthMsg.type === "success" ? "#10B981" : "#f87171",
          }}>
            {oauthMsg.text}
          </div>
        )}

        {/* Vercel projects preview — shown after OAuth connection */}
        {vercelOAuthStatus?.connected && (
          <div style={{ marginTop: "1.25rem" }}>
            <p className="label" style={{ marginBottom: "0.75rem" }}>
              YOUR VERCEL PROJECTS {vercelProjects.length > 0 && `(${vercelProjects.length})`}
            </p>
            {loadingProjects ? (
              <p style={{ fontSize: "0.875rem", color: "var(--text-muted)" }}>Loading projects…</p>
            ) : vercelProjects.length > 0 ? (
              <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
                {vercelProjects.map((p) => (
                  <div key={p.id} style={{ display: "flex", alignItems: "center", gap: "0.875rem", padding: "0.75rem 1rem", background: "var(--bg-surface-2)", border: "1px solid var(--border-subtle)", borderRadius: "8px" }}>
                    <div style={{ width: "28px", height: "28px", borderRadius: "6px", background: "#000", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
                      <VercelIcon size={14} />
                    </div>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <p style={{ fontSize: "0.875rem", fontWeight: 600, color: "var(--text-primary)", margin: 0 }}>{p.name}</p>
                      {p.linked_repo ? (
                        <p style={{ fontSize: "0.75rem", color: "var(--text-muted)", margin: 0, display: "flex", alignItems: "center", gap: "0.3rem" }}>
                          <GitHubIcon size={11} />{p.linked_repo}
                        </p>
                      ) : (
                        <p style={{ fontSize: "0.75rem", color: "var(--text-dim)", margin: 0 }}>No GitHub repo linked in Vercel</p>
                      )}
                    </div>
                    {p.framework && (
                      <span style={{ fontSize: "0.6875rem", color: "var(--text-dim)", border: "1px solid var(--border)", borderRadius: "9999px", padding: "0.125rem 0.5rem" }}>
                        {p.framework}
                      </span>
                    )}
                  </div>
                ))}
                <p style={{ fontSize: "0.75rem", color: "var(--text-dim)", marginTop: "0.5rem" }}>
                  Go to <strong>Repositories</strong> → click <strong>"Link Vercel project"</strong> on any repo to connect it.
                </p>
              </div>
            ) : (
              <p style={{ fontSize: "0.875rem", color: "var(--text-muted)" }}>
                No Vercel projects found. Make sure you authorized FixFlow on the correct Vercel account.
              </p>
            )}
          </div>
        )}
      </div>

      {/* ── Webhook Endpoints ─────────────────────────────────────── */}
      <div className="card" style={{ marginBottom: "1.5rem" }}>
        <p className="label" style={{ marginBottom: "0.875rem" }}>WEBHOOK ENDPOINTS</p>
        <p style={{ fontSize: "0.875rem", color: "var(--text-muted)", marginBottom: "1.5rem" }}>
          Auto-registered when you connect a repository. For local development, expose port 8000 via{" "}
          <code style={{ fontFamily: "var(--font-mono)", fontSize: "0.8125rem", color: "var(--text-secondary)", background: "var(--bg-surface-2)", padding: "0.125rem 0.25rem", borderRadius: "4px" }}>ngrok http 8000</code>
          {" "}and set <code style={{ fontFamily: "var(--font-mono)", fontSize: "0.8125rem" }}>API_BASE_URL</code> in <code style={{ fontFamily: "var(--font-mono)", fontSize: "0.8125rem" }}>backend/.env</code>.
        </p>
        <div style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}>
          <WebhookEndpoint label="GitHub Webhook" path="/api/v1/webhooks/github" />
          <WebhookEndpoint label="Vercel Webhook" path="/api/v1/webhooks/vercel" />
        </div>
      </div>

      {/* ── Environment Variables ─────────────────────────────────── */}
      <div className="card">
        <p className="label" style={{ marginBottom: "0.875rem" }}>ENVIRONMENT VARIABLES</p>
        <p style={{ fontSize: "0.875rem", color: "var(--text-muted)", marginBottom: "1.5rem" }}>
          Required in <code style={{ fontFamily: "var(--font-mono)", color: "var(--text-secondary)", background: "var(--bg-surface-2)", padding: "0.125rem 0.25rem", borderRadius: "var(--radius-sm)" }}>backend/.env</code>
        </p>
        <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
          {[
            { key: "GITHUB_CLIENT_ID", desc: "GitHub OAuth App Client ID", set: true },
            { key: "GITHUB_CLIENT_SECRET", desc: "GitHub OAuth App Client Secret", set: true },
            { key: "GITHUB_TOKEN", desc: "GitHub PAT — needs admin:repo_hook scope", set: true },
            { key: "NVIDIA_API_KEY", desc: "NVIDIA NIM API key for AI diagnosis", set: true },
            { key: "DATABASE_URL", desc: "PostgreSQL connection string (Supabase)", set: true },
            { key: "API_BASE_URL", desc: "Your public backend URL (ngrok URL locally)", set: false },
            { key: "GITHUB_WEBHOOK_SECRET", desc: "HMAC secret for webhook verification", set: true },
            { key: "JWT_SECRET", desc: "JWT signing secret", set: true },
          ].map((env) => (
            <div key={env.key} style={{ display: "flex", gap: "1rem", alignItems: "flex-start", paddingBottom: "0.75rem", borderBottom: "1px solid var(--border)" }}>
              <code style={{ fontFamily: "var(--font-mono)", fontSize: "0.75rem", color: "var(--text-secondary)", width: "220px", flexShrink: 0, paddingTop: "0.125rem", fontWeight: 500 }}>
                {env.key}
              </code>
              <span style={{ fontSize: "0.8125rem", color: "var(--text-muted)", flex: 1, paddingTop: "0.125rem" }}>{env.desc}</span>
              <span style={{
                flexShrink: 0, fontSize: "0.625rem", fontWeight: 600, padding: "0.2rem 0.5rem", borderRadius: "9999px",
                background: env.set ? "rgba(16,185,129,0.1)" : "rgba(234,179,8,0.1)",
                color: env.set ? "#10B981" : "#CA8A04",
                border: `1px solid ${env.set ? "rgba(16,185,129,0.3)" : "rgba(234,179,8,0.3)"}`,
              }}>
                {env.set ? "SET" : "NEEDED"}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ── Small components & icons ─────────────────────────────────────────────────

function ConnectedBadge() {
  return (
    <span style={{ fontSize: "0.6875rem", fontWeight: 600, padding: "0.2rem 0.5rem", borderRadius: "9999px", background: "#ECFDF5", color: "#047857", border: "1px solid #34D399" }}>
      CONNECTED
    </span>
  );
}

function WebhookEndpoint({ label, path }: { label: string; path: string }) {
  const [url, setUrl] = useState(path);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    setUrl(`${window.location.protocol}//${window.location.hostname}:8000${path}`);
  }, [path]);

  function copy() {
    navigator.clipboard.writeText(url);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }
  return (
    <div>
      <p className="label" style={{ marginBottom: "0.5rem" }}>{label}</p>
      <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", background: "var(--bg-surface-2)", border: "1px solid var(--border)", borderRadius: "var(--radius-md)", padding: "0.625rem 1rem" }}>
        <code style={{ flex: 1, fontFamily: "var(--font-mono)", fontSize: "0.8125rem", color: "var(--text-secondary)" }}>{url}</code>
        <button onClick={copy} className="btn btn-ghost" style={{ padding: "0.375rem 0.75rem", fontSize: "0.75rem" }}>
          {copied ? "Copied!" : "Copy"}
        </button>
      </div>
    </div>
  );
}

function GitHubIcon({ size = 16 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="currentColor">
      <path d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z" />
    </svg>
  );
}

function VercelIcon({ size = 16 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="white">
      <path d="M12 1L24 22H0L12 1Z" />
    </svg>
  );
}

function ExternalLinkIcon() {
  return (
    <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6" />
      <polyline points="15 3 21 3 21 9" />
      <line x1="10" y1="14" x2="21" y2="3" />
    </svg>
  );
}
