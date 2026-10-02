"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { auth } from "@/lib/api-client";

export default function IntegrationsPage() {
  const [githubConnected, setGithubConnected] = useState(false);
  const [vercelConnected, setVercelConnected] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = typeof window !== "undefined" ? localStorage.getItem("patchr_token") : null;
    setGithubConnected(!!token);

    auth.getVercelTokenStatus()
      .then((status) => setVercelConnected(status.has_token))
      .catch(() => setVercelConnected(false))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div style={{ padding: '2.5rem' }}>
      <div style={{ marginBottom: "2rem" }}>
        <h1 style={{ fontSize: '1.25rem', marginBottom: '0.25rem' }}>Integrations</h1>
        <p style={{ fontSize: '0.875rem', color: 'var(--text-muted)' }}>
          Manage connections to external services.
        </p>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))", gap: "1.5rem" }}>
        {/* GitHub */}
        <div className="card" style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
          <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between" }}>
            <div style={{ width: "40px", height: "40px", borderRadius: "8px", background: "var(--bg-surface-2)", border: "1px solid var(--border)", display: "flex", alignItems: "center", justifyContent: "center" }}>
              <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
                <path d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z"/>
              </svg>
            </div>
            <StatusBadge connected={githubConnected} />
          </div>
          <div>
            <p style={{ fontSize: "1rem", fontWeight: 600, color: "var(--text-primary)" }}>GitHub</p>
            <p style={{ fontSize: "0.8125rem", color: "var(--text-secondary)", marginTop: "0.25rem" }}>
              Source control, webhook events, and PR creation.
            </p>
          </div>
          <Link href="/dashboard/settings" className="btn btn-ghost" style={{ width: "100%", marginTop: "0.5rem", textAlign: "center" }}>
            {githubConnected ? "Manage" : "Connect"}
          </Link>
        </div>

        {/* Vercel */}
        <div className="card" style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
          <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between" }}>
            <div style={{ width: "40px", height: "40px", borderRadius: "8px", background: "var(--bg-dark-surface)", border: "1px solid var(--border)", display: "flex", alignItems: "center", justifyContent: "center", color: "#fff" }}>
              <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
                <path d="M12 2L2 22h20L12 2z" />
              </svg>
            </div>
            {loading ? (
              <span style={{ fontSize: "0.6875rem", fontWeight: 600, padding: "0.25rem 0.625rem", borderRadius: "9999px", background: "var(--bg-surface-2)", color: "var(--text-muted)", border: "1px solid var(--border)" }}>Checking…</span>
            ) : (
              <StatusBadge connected={vercelConnected} />
            )}
          </div>
          <div>
            <p style={{ fontSize: "1rem", fontWeight: 600, color: "var(--text-primary)" }}>Vercel</p>
            <p style={{ fontSize: "0.8125rem", color: "var(--text-secondary)", marginTop: "0.25rem" }}>
              Deployment events and runtime log ingestion.
            </p>
          </div>
          <Link href="/dashboard/settings" className="btn btn-ghost" style={{ width: "100%", marginTop: "0.5rem", textAlign: "center" }}>
            {vercelConnected ? "Manage" : "Connect"}
          </Link>
        </div>

        {/* NVIDIA NIM */}
        <div className="card" style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
          <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between" }}>
            <div style={{ width: "40px", height: "40px", borderRadius: "8px", background: "#76B900", border: "1px solid #5a8d00", display: "flex", alignItems: "center", justifyContent: "center", color: "#fff", fontWeight: 800, fontSize: "1rem", letterSpacing: "-1px" }}>
              NIM
            </div>
            <span style={{ fontSize: "0.6875rem", fontWeight: 600, padding: "0.25rem 0.625rem", borderRadius: "9999px", background: "#D1FAE5", color: "#047857", border: "1px solid #A7F3D0" }}>Active</span>
          </div>
          <div>
            <p style={{ fontSize: "1rem", fontWeight: 600, color: "var(--text-primary)" }}>NVIDIA NIM</p>
            <p style={{ fontSize: "0.8125rem", color: "var(--text-secondary)", marginTop: "0.25rem" }}>
              AI models for root cause analysis and patch generation.
            </p>
          </div>
          <Link href="/dashboard/settings" className="btn btn-ghost" style={{ width: "100%", marginTop: "0.5rem", textAlign: "center" }}>
            Configured via .env
          </Link>
        </div>
      </div>
    </div>
  );
}

function StatusBadge({ connected }: { connected: boolean }) {
  return connected ? (
    <span style={{ fontSize: "0.6875rem", fontWeight: 600, padding: "0.25rem 0.625rem", borderRadius: "9999px", background: "#D1FAE5", color: "#047857", border: "1px solid #A7F3D0" }}>Connected</span>
  ) : (
    <span style={{ fontSize: "0.6875rem", fontWeight: 600, padding: "0.25rem 0.625rem", borderRadius: "9999px", background: "var(--bg-surface-2)", color: "var(--text-muted)", border: "1px solid var(--border)" }}>Not connected</span>
  );
}
