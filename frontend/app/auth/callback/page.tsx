"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

export default function GitHubOAuthCallbackPage() {
  return (
    <Suspense fallback={<CallbackScreen status="loading" message="Completing GitHub sign-in…" />}>
      <CompleteGitHubOAuth />
    </Suspense>
  );
}

function CompleteGitHubOAuth() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [status, setStatus] = useState<"loading" | "success" | "error">("loading");
  const [message, setMessage] = useState("Completing GitHub sign-in…");

  useEffect(() => {
    const token = searchParams.get("token");

    if (!token) {
      setStatus("error");
      setMessage("GitHub sign-in did not return a session.");
      setTimeout(() => {
        router.replace("/login?error=GitHub+sign-in+did+not+return+a+session");
      }, 2000);
      return;
    }

    // Store the JWT — the user is now authenticated
    localStorage.setItem("patchr_token", token);
    setStatus("success");
    setMessage("Signed in! Taking you to the dashboard…");

    setTimeout(() => {
      router.replace("/dashboard");
    }, 800);
  }, [router, searchParams]);

  return <CallbackScreen status={status} message={message} />;
}

function CallbackScreen({
  status,
  message,
}: {
  status: "loading" | "success" | "error";
  message: string;
}) {
  return (
    <main style={{
      minHeight: "100vh",
      display: "flex",
      flexDirection: "column",
      alignItems: "center",
      justifyContent: "center",
      gap: "1.5rem",
      padding: "2rem",
      background: "#0a0a0f",
      color: "#94a3b8",
      fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, sans-serif",
    }}>
      {/* Animated icon */}
      <div style={{ position: "relative" }}>
        {status === "loading" && <LoadingRing />}
        {status === "success" && <SuccessIcon />}
        {status === "error" && <ErrorIcon />}
      </div>

      {/* FixFlow wordmark */}
      <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
        <FixFlowMark />
        <span style={{ fontSize: "1.25rem", fontWeight: 800, letterSpacing: "-0.03em", color: "#f1f5f9" }}>
          FixFlow
        </span>
      </div>

      <p style={{
        fontSize: "0.9375rem",
        color: status === "error" ? "#fca5a5" : status === "success" ? "#86efac" : "#94a3b8",
        textAlign: "center",
        maxWidth: "320px",
        lineHeight: 1.6,
        margin: 0,
      }}>
        {message}
      </p>

      <style>{`
        @keyframes spin { to { transform: rotate(360deg); } }
        @keyframes fadeIn { from { opacity: 0; transform: scale(0.8); } to { opacity: 1; transform: scale(1); } }
        .callback-ring { animation: spin 0.9s linear infinite; }
        .callback-appear { animation: fadeIn 0.3s ease forwards; }
      `}</style>
    </main>
  );
}

function LoadingRing() {
  return (
    <svg className="callback-ring" width="48" height="48" viewBox="0 0 48 48" fill="none">
      <circle cx="24" cy="24" r="20" stroke="rgba(99,102,241,0.2)" strokeWidth="3" />
      <circle cx="24" cy="24" r="20" stroke="#6366f1" strokeWidth="3"
        strokeDasharray="60" strokeDashoffset="20" strokeLinecap="round" />
    </svg>
  );
}

function SuccessIcon() {
  return (
    <svg className="callback-appear" width="48" height="48" viewBox="0 0 48 48" fill="none">
      <circle cx="24" cy="24" r="22" fill="rgba(134, 239, 172, 0.12)" stroke="#86efac" strokeWidth="2" />
      <path d="M15 24l7 7 11-14" stroke="#86efac" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function ErrorIcon() {
  return (
    <svg className="callback-appear" width="48" height="48" viewBox="0 0 48 48" fill="none">
      <circle cx="24" cy="24" r="22" fill="rgba(239, 68, 68, 0.12)" stroke="#f87171" strokeWidth="2" />
      <path d="M17 17l14 14M31 17L17 31" stroke="#f87171" strokeWidth="2.5" strokeLinecap="round" />
    </svg>
  );
}

function FixFlowMark() {
  return (
    <svg width="28" height="28" viewBox="0 0 32 32" fill="none">
      <rect x="2" y="2" width="28" height="28" rx="8" fill="url(#cb-grad)" />
      <path d="M10 16h12M16 10v12" stroke="white" strokeWidth="2" strokeLinecap="round" />
      <defs>
        <linearGradient id="cb-grad" x1="2" y1="2" x2="30" y2="30" gradientUnits="userSpaceOnUse">
          <stop stopColor="#6366f1" />
          <stop offset="1" stopColor="#8b5cf6" />
        </linearGradient>
      </defs>
    </svg>
  );
}
