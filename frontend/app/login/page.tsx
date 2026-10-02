"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { githubLoginUrl } from "@/lib/api-client";

export default function LoginPage() {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  // Read ?error= query param set by backend OAuth failure redirect
  useEffect(() => {
    const oauthError = new URLSearchParams(window.location.search).get("error");
    if (oauthError) setError(decodeURIComponent(oauthError));
  }, []);

  // Already authenticated — skip login
  useEffect(() => {
    const token = localStorage.getItem("patchr_token");
    if (token) router.replace("/dashboard");
  }, [router]);

  function handleGitHubLogin() {
    setLoading(true);
    setError(null);
    // Navigate directly to the backend — it returns 302 → GitHub OAuth
    window.location.href = githubLoginUrl;
  }

  return (
    <div className="login-root">
      {/* Ambient background blobs */}
      <div className="login-blob login-blob-1" />
      <div className="login-blob login-blob-2" />

      <div className="login-wrapper">
        {/* Logo mark */}
        <div className="login-logo">
          <FixFlowMark />
          <span className="login-logo-name">FixFlow</span>
        </div>

        <p className="login-tagline">Autonomous Self-Healing Platform</p>

        {/* Card */}
        <div className="login-card">
          <div className="login-card-header">
            <h1 className="login-title">Sign in to continue</h1>
            <p className="login-subtitle">
              Connect your GitHub account to monitor repositories and
              auto-remediate deployment failures.
            </p>
          </div>

          {/* Error banner */}
          {error && (
            <div className="login-error" role="alert">
              <ErrorIcon />
              <span>{error}</span>
            </div>
          )}

          {/* GitHub OAuth button — the ONLY login method */}
          <button
            id="github-login-btn"
            onClick={handleGitHubLogin}
            disabled={loading}
            className="login-github-btn"
            aria-busy={loading}
          >
            {loading ? (
              <>
                <SpinnerIcon />
                Redirecting to GitHub…
              </>
            ) : (
              <>
                <GitHubIcon />
                Continue with GitHub
              </>
            )}
          </button>

          <p className="login-scope-note">
            FixFlow requests <code>read:user</code>, <code>user:email</code>, and{" "}
            <code>repo</code> scopes to fetch your repositories and commit
            context for AI analysis.
          </p>
        </div>

        <p className="login-footer">
          No account needed — your GitHub identity is your account.
        </p>
      </div>

      <style>{`
        /* ── Layout ───────────────────────────────────────────────── */
        .login-root {
          min-height: 100vh;
          display: flex;
          align-items: center;
          justify-content: center;
          background: #0a0a0f;
          padding: 2rem;
          position: relative;
          overflow: hidden;
          font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
        }

        /* ── Ambient blobs ────────────────────────────────────────── */
        .login-blob {
          position: absolute;
          border-radius: 50%;
          filter: blur(80px);
          opacity: 0.18;
          pointer-events: none;
          animation: blobFloat 8s ease-in-out infinite alternate;
        }
        .login-blob-1 {
          width: 500px; height: 500px;
          background: radial-gradient(circle, #6366f1 0%, #8b5cf6 60%, transparent 100%);
          top: -120px; left: -100px;
          animation-delay: 0s;
        }
        .login-blob-2 {
          width: 400px; height: 400px;
          background: radial-gradient(circle, #06b6d4 0%, #3b82f6 60%, transparent 100%);
          bottom: -80px; right: -80px;
          animation-delay: -4s;
        }
        @keyframes blobFloat {
          from { transform: translate(0, 0) scale(1); }
          to   { transform: translate(20px, -20px) scale(1.05); }
        }

        /* ── Wrapper ─────────────────────────────────────────────── */
        .login-wrapper {
          position: relative;
          z-index: 1;
          width: 100%;
          max-width: 400px;
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: 1rem;
        }

        /* ── Logo ────────────────────────────────────────────────── */
        .login-logo {
          display: flex;
          align-items: center;
          gap: 0.6rem;
          margin-bottom: 0.25rem;
        }
        .login-logo-name {
          font-size: 1.75rem;
          font-weight: 800;
          letter-spacing: -0.04em;
          color: #f1f5f9;
        }

        /* ── Tagline ─────────────────────────────────────────────── */
        .login-tagline {
          font-size: 0.78rem;
          font-weight: 600;
          letter-spacing: 0.12em;
          text-transform: uppercase;
          color: #818cf8;
          margin: 0 0 0.5rem;
        }

        /* ── Card ────────────────────────────────────────────────── */
        .login-card {
          width: 100%;
          background: rgba(255, 255, 255, 0.04);
          backdrop-filter: blur(20px);
          -webkit-backdrop-filter: blur(20px);
          border: 1px solid rgba(255, 255, 255, 0.10);
          border-radius: 20px;
          padding: 2.25rem 2rem;
          display: flex;
          flex-direction: column;
          gap: 1.5rem;
          box-shadow:
            0 0 0 1px rgba(99, 102, 241, 0.12),
            0 20px 60px -10px rgba(0, 0, 0, 0.5),
            inset 0 1px 0 rgba(255, 255, 255, 0.08);
        }

        .login-card-header {
          text-align: center;
        }

        .login-title {
          font-size: 1.2rem;
          font-weight: 700;
          color: #f1f5f9;
          margin: 0 0 0.5rem;
          letter-spacing: -0.02em;
        }

        .login-subtitle {
          font-size: 0.875rem;
          color: #94a3b8;
          line-height: 1.6;
          margin: 0;
        }

        /* ── Error banner ─────────────────────────────────────────── */
        .login-error {
          display: flex;
          align-items: flex-start;
          gap: 0.6rem;
          background: rgba(239, 68, 68, 0.12);
          border: 1px solid rgba(239, 68, 68, 0.3);
          border-radius: 10px;
          padding: 0.75rem 1rem;
          font-size: 0.8125rem;
          color: #fca5a5;
          line-height: 1.5;
        }
        .login-error svg { flex-shrink: 0; margin-top: 1px; }

        /* ── GitHub button ───────────────────────────────────────── */
        .login-github-btn {
          width: 100%;
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 0.65rem;
          padding: 0.85rem 1.25rem;
          background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
          border: 1px solid rgba(255, 255, 255, 0.15);
          border-radius: 12px;
          color: #f1f5f9;
          font-size: 0.9375rem;
          font-weight: 600;
          cursor: pointer;
          letter-spacing: -0.01em;
          transition: all 0.2s ease;
          position: relative;
          overflow: hidden;
          box-shadow: 0 2px 8px rgba(0,0,0,0.3), inset 0 1px 0 rgba(255,255,255,0.08);
        }
        .login-github-btn::before {
          content: '';
          position: absolute;
          inset: 0;
          background: linear-gradient(135deg, rgba(99,102,241,0.15) 0%, rgba(139,92,246,0.1) 100%);
          opacity: 0;
          transition: opacity 0.2s ease;
        }
        .login-github-btn:hover:not(:disabled)::before { opacity: 1; }
        .login-github-btn:hover:not(:disabled) {
          border-color: rgba(99, 102, 241, 0.4);
          box-shadow: 0 4px 20px rgba(99, 102, 241, 0.2), inset 0 1px 0 rgba(255,255,255,0.12);
          transform: translateY(-1px);
        }
        .login-github-btn:active:not(:disabled) {
          transform: translateY(0);
        }
        .login-github-btn:disabled {
          opacity: 0.7;
          cursor: not-allowed;
        }

        /* ── Scope note ──────────────────────────────────────────── */
        .login-scope-note {
          font-size: 0.75rem;
          color: #64748b;
          line-height: 1.6;
          margin: 0;
          text-align: center;
        }
        .login-scope-note code {
          font-family: 'JetBrains Mono', 'Fira Code', monospace;
          font-size: 0.7rem;
          background: rgba(255, 255, 255, 0.06);
          border: 1px solid rgba(255, 255, 255, 0.08);
          border-radius: 4px;
          padding: 0.1em 0.35em;
          color: #a5b4fc;
        }

        /* ── Footer ─────────────────────────────────────────────── */
        .login-footer {
          font-size: 0.75rem;
          color: #475569;
          text-align: center;
          margin: 0;
        }

        /* ── Spinner ─────────────────────────────────────────────── */
        @keyframes spin {
          to { transform: rotate(360deg); }
        }
        .login-spinner {
          animation: spin 0.8s linear infinite;
        }
      `}</style>
    </div>
  );
}

// ─── Icons ────────────────────────────────────────────────────────────────────

function FixFlowMark() {
  return (
    <svg width="32" height="32" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
      <rect x="2" y="2" width="28" height="28" rx="8" fill="url(#pm-grad)" />
      <path d="M10 16h12M16 10v12" stroke="white" strokeWidth="2" strokeLinecap="round" />
      <defs>
        <linearGradient id="pm-grad" x1="2" y1="2" x2="30" y2="30" gradientUnits="userSpaceOnUse">
          <stop stopColor="#6366f1" />
          <stop offset="1" stopColor="#8b5cf6" />
        </linearGradient>
      </defs>
    </svg>
  );
}

function GitHubIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
      <path d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z" />
    </svg>
  );
}

function SpinnerIcon() {
  return (
    <svg
      className="login-spinner"
      width="16" height="16" viewBox="0 0 24 24" fill="none"
    >
      <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="2.5"
        strokeDasharray="31.4" strokeDashoffset="10" strokeLinecap="round" />
    </svg>
  );
}

function ErrorIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10" />
      <line x1="12" y1="8" x2="12" y2="12" />
      <line x1="12" y1="16" x2="12.01" y2="16" />
    </svg>
  );
}
