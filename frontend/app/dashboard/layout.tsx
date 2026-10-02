"use client";

import { usePathname, useRouter } from "next/navigation";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";

interface DashboardLayoutProps {
  children: React.ReactNode;
}

export default function DashboardLayout({ children }: DashboardLayoutProps) {
  const pathname = usePathname();

  return (
    <div style={{ display: "flex", minHeight: "100vh", background: "var(--bg-main)" }}>
      {/* ── Sidebar ── */}
      <aside
        style={{
          width: "240px",
          flexShrink: 0,
          background: "var(--bg-surface)",
          borderRight: "1px solid var(--border-subtle)",
          display: "flex",
          flexDirection: "column",
          padding: "1.25rem 0",
        }}
      >
        {/* Logo */}
        <div style={{ padding: "0 1.25rem 1.25rem", borderBottom: "1px solid var(--border-subtle)", marginBottom: "1rem" }}>
          <Link href="/dashboard" style={{ display: "flex", alignItems: "center", gap: "0.5rem", textDecoration: "none" }}>
            <FixFlowLogo />
            <span style={{ fontSize: "1rem", fontWeight: 600, color: "var(--text-primary)" }}>FixFlow</span>
          </Link>
        </div>

        {/* Nav */}
        <nav style={{ flex: 1, padding: "0 0.75rem", display: "flex", flexDirection: "column", gap: "1.5rem", overflowY: "auto" }}>
          {/* Overview */}
          <div>
            <div style={{ display: "flex", flexDirection: "column", gap: "2px" }}>
              <NavItem href="/dashboard" label="Overview" icon={<DashboardIcon />} active={pathname === "/dashboard"} />
              <NavItem href="/dashboard/incidents" label="Incidents" icon={<IncidentsIcon />} active={pathname.startsWith("/dashboard/incidents")} />
              <NavItem href="/dashboard/repositories" label="Repositories" icon={<RepoIcon />} active={pathname.startsWith("/dashboard/repositories")} />
            </div>
          </div>

          {/* Intelligence */}
          <div>
            <p style={{ padding: "0 0.75rem", marginBottom: "0.5rem", fontSize: "0.6875rem", color: "var(--text-dim)", fontWeight: 500 }}>Intelligence</p>
            <div style={{ display: "flex", flexDirection: "column", gap: "2px" }}>
              <NavItem href="/dashboard/monitoring" label="Monitoring" icon={<MonitoringIcon />} active={pathname.startsWith("/dashboard/monitoring")} />
              <NavItem href="/dashboard/journeys" label="Journeys" icon={<JourneysIcon />} active={pathname.startsWith("/dashboard/journeys")} />
              <NavItem href="/dashboard/patches" label="Patches" icon={<PatchesIcon />} active={pathname.startsWith("/dashboard/patches")} />
              <NavItem href="/dashboard/verification" label="Verification" icon={<VerificationIcon />} active={pathname.startsWith("/dashboard/verification")} />
            </div>
          </div>

          {/* Operations & Workspace */}
          <div>
            <p style={{ padding: "0 0.75rem", marginBottom: "0.5rem", fontSize: "0.6875rem", color: "var(--text-dim)", fontWeight: 500 }}>System</p>
            <div style={{ display: "flex", flexDirection: "column", gap: "2px" }}>
              <NavItem href="/dashboard/activity" label="Activity" icon={<ActivityIcon />} active={pathname.startsWith("/dashboard/activity")} />
              <NavItem href="/dashboard/automations" label="Automations" icon={<AutomationsIcon />} active={pathname.startsWith("/dashboard/automations")} />
              <NavItem href="/dashboard/integrations" label="Integrations" icon={<IntegrationsIcon />} active={pathname.startsWith("/dashboard/integrations")} />
              <NavItem href="/dashboard/policies" label="Policies" icon={<PoliciesIcon />} active={pathname.startsWith("/dashboard/policies")} />
            </div>
          </div>
        </nav>

        {/* Footer Navigation */}
        <div style={{ padding: "0 0.75rem", marginTop: "auto", paddingTop: "1rem" }}>
          <div style={{ display: "flex", flexDirection: "column", gap: "2px" }}>
            <NavItem href="#" label="Help Center" icon={<PoliciesIcon />} active={false} />
            <NavItem href="/dashboard/settings" label="Settings" icon={<SettingsIcon />} active={pathname.startsWith("/dashboard/settings")} />
          </div>
        </div>
      </aside>

      {/* ── Main content ── */}
      <main style={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column", height: "100vh", overflow: "hidden" }}>
        
        {/* Top Header */}
        <header style={{ 
          height: "64px", 
          flexShrink: 0, 
          display: "flex", 
          alignItems: "center", 
          justifyContent: "space-between", 
          padding: "0 2.5rem",
          background: "transparent",
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: "1rem" }}>
             {/* Search */}
             <div style={{ position: "relative", width: "240px" }}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" style={{ position: "absolute", left: "0.75rem", top: "50%", transform: "translateY(-50%)", color: "var(--text-dim)" }}>
                <circle cx="11" cy="11" r="8" stroke="currentColor" strokeWidth="2" />
                <path d="M21 21l-4.35-4.35" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
              </svg>
              <input 
                type="text" 
                placeholder="Search or action..." 
                style={{
                  width: "100%",
                  height: "32px",
                  background: "var(--bg-surface)",
                  border: "1px solid var(--border-subtle)",
                  borderRadius: "6px",
                  padding: "0 1rem 0 2rem",
                  fontSize: "0.8125rem",
                  color: "var(--text-primary)",
                  outline: "none",
                  boxShadow: "var(--shadow-sm)"
                }} 
              />
              <span style={{ position: "absolute", right: "0.5rem", top: "50%", transform: "translateY(-50%)", fontSize: "0.625rem", color: "var(--text-dim)", fontFamily: "var(--font-mono)", padding: "0.125rem 0.25rem", background: "var(--bg-surface-2)", borderRadius: "4px", border: "1px solid var(--border-subtle)" }}>⌘K</span>
            </div>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: "1rem" }}>
            <button className="btn btn-primary" style={{ padding: "0.375rem 0.75rem", fontSize: "0.75rem", borderRadius: "6px", display: "flex", alignItems: "center", gap: "0.375rem" }}>
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" color="currentColor"><path d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/></svg>
              Export
            </button>
            <button className="btn btn-ghost" style={{ padding: "0.375rem 0.75rem", fontSize: "0.75rem", borderRadius: "6px", display: "flex", gap: "0.5rem", alignItems: "center", border: "none", background: "transparent", boxShadow: "none" }}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" color="currentColor"><path d="M4 6h16M4 12h16M4 18h16" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/></svg>
              Filter
            </button>
            {/* GitHub User Avatar */}
            <GitHubUserMenu />
          </div>
        </header>

        {/* Page Content (Scrollable) */}
        <div style={{ flex: 1, overflowY: "auto", overflowX: "hidden" }}>
          {children}
        </div>

      </main>
    </div>
  );
}


// ─── GitHub User Menu ───────────────────────────────────────────────────────

function decodeJwtPayload(token: string): Record<string, string> | null {
  try {
    const base64 = token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/");
    return JSON.parse(atob(base64));
  } catch {
    return null;
  }
}

function GitHubUserMenu() {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [user, setUser] = useState<{
    login: string;
    name: string;
    avatar: string;
  } | null>(null);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const token = localStorage.getItem("patchr_token");
    if (!token) return;
    const payload = decodeJwtPayload(token);
    if (payload?.github_login) {
      setUser({
        login: payload.github_login,
        name: payload.github_name || payload.github_login,
        avatar: payload.github_avatar || "",
      });
    }
  }, []);

  // Close dropdown on outside click
  useEffect(() => {
    function handler(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  function handleSignOut() {
    localStorage.removeItem("patchr_token");
    router.push("/login");
  }

  if (!user) {
    // Fallback: no GitHub user (legacy password token)
    return (
      <div style={{
        width: "28px", height: "28px", borderRadius: "50%",
        background: "var(--accent-dim)", color: "var(--accent)",
        display: "flex", alignItems: "center", justifyContent: "center",
        fontWeight: 600, fontSize: "0.75rem", marginLeft: "0.5rem",
      }}>
        P
      </div>
    );
  }

  return (
    <div ref={ref} style={{ position: "relative", marginLeft: "0.5rem" }}>
      {/* Avatar button */}
      <button
        onClick={() => setOpen(!open)}
        style={{
          display: "flex", alignItems: "center", gap: "0.5rem",
          background: "none", border: "none", cursor: "pointer", padding: "2px",
          borderRadius: "999px",
          outline: open ? "2px solid var(--accent)" : "none",
          outlineOffset: "2px",
          transition: "outline 0.15s",
        }}
        aria-label="Account menu"
      >
        {user.avatar ? (
          <img
            src={user.avatar}
            alt={user.login}
            width={28} height={28}
            style={{ borderRadius: "50%", display: "block" }}
          />
        ) : (
          <div style={{
            width: "28px", height: "28px", borderRadius: "50%",
            background: "var(--accent-dim)", color: "var(--accent)",
            display: "flex", alignItems: "center", justifyContent: "center",
            fontWeight: 700, fontSize: "0.75rem",
          }}>
            {user.login[0].toUpperCase()}
          </div>
        )}
      </button>

      {/* Dropdown */}
      {open && (
        <div style={{
          position: "absolute", top: "calc(100% + 10px)", right: 0,
          width: "240px",
          background: "var(--bg-surface)",
          border: "1px solid var(--border-subtle)",
          borderRadius: "12px",
          boxShadow: "0 8px 32px rgba(0,0,0,0.12), 0 2px 8px rgba(0,0,0,0.06)",
          zIndex: 100,
          overflow: "hidden",
        }}>
          {/* Profile section */}
          <div style={{
            padding: "1rem",
            borderBottom: "1px solid var(--border-subtle)",
          }}>
            <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
              {user.avatar ? (
                <img src={user.avatar} alt={user.login} width={36} height={36}
                  style={{ borderRadius: "50%", flexShrink: 0 }} />
              ) : (
                <div style={{
                  width: "36px", height: "36px", borderRadius: "50%",
                  background: "var(--accent-dim)", color: "var(--accent)",
                  display: "flex", alignItems: "center", justifyContent: "center",
                  fontWeight: 700, fontSize: "0.875rem", flexShrink: 0,
                }}>
                  {user.login[0].toUpperCase()}
                </div>
              )}
              <div style={{ minWidth: 0 }}>
                <p style={{ fontSize: "0.875rem", fontWeight: 600, color: "var(--text-primary)", margin: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  {user.name}
                </p>
                <p style={{ fontSize: "0.75rem", color: "var(--text-muted)", margin: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  @{user.login}
                </p>
              </div>
            </div>
          </div>

          {/* Connected account */}
          <div style={{ padding: "0.75rem 1rem", borderBottom: "1px solid var(--border-subtle)" }}>
            <p style={{ fontSize: "0.6875rem", fontWeight: 600, color: "var(--text-dim)", letterSpacing: "0.06em", marginBottom: "0.625rem" }}>
              CONNECTED ACCOUNT
            </p>
            <div style={{ display: "flex", alignItems: "center", gap: "0.6rem" }}>
              {/* GitHub icon */}
              <svg width="16" height="16" viewBox="0 0 24 24" fill="var(--text-secondary)">
                <path d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z"/>
              </svg>
              <div>
                <p style={{ fontSize: "0.8125rem", color: "var(--text-primary)", fontWeight: 500, margin: 0 }}>
                  GitHub
                </p>
                <p style={{ fontSize: "0.75rem", color: "var(--text-muted)", margin: 0 }}>
                  @{user.login}
                </p>
              </div>
              <span style={{
                marginLeft: "auto", fontSize: "0.6875rem", fontWeight: 600,
                padding: "0.2rem 0.5rem", borderRadius: "9999px",
                background: "#ECFDF5", color: "#047857", border: "1px solid #34D399",
              }}>
                CONNECTED
              </span>
            </div>
          </div>

          {/* Actions */}
          <div style={{ padding: "0.5rem" }}>
            <a
              href={`https://github.com/${user.login}`}
              target="_blank"
              rel="noopener noreferrer"
              style={{
                display: "flex", alignItems: "center", gap: "0.6rem",
                padding: "0.5rem 0.75rem", borderRadius: "8px",
                fontSize: "0.8125rem", color: "var(--text-secondary)",
                textDecoration: "none", transition: "background 0.15s",
              }}
              onMouseEnter={e => (e.currentTarget.style.background = "var(--bg-surface-2)")}
              onMouseLeave={e => (e.currentTarget.style.background = "transparent")}
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/>
              </svg>
              View GitHub profile
            </a>
            <button
              onClick={handleSignOut}
              style={{
                width: "100%", display: "flex", alignItems: "center", gap: "0.6rem",
                padding: "0.5rem 0.75rem", borderRadius: "8px",
                fontSize: "0.8125rem", color: "var(--severity-critical)",
                background: "none", border: "none", cursor: "pointer",
                textAlign: "left", transition: "background 0.15s",
              }}
              onMouseEnter={e => (e.currentTarget.style.background = "var(--bg-surface-2)")}
              onMouseLeave={e => (e.currentTarget.style.background = "transparent")}
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/>
              </svg>
              Sign out
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

// ─── Nav Item ──────────────────────────────────────────────────────────────────

interface NavItemProps {
  href: string;
  label: string;
  icon: React.ReactNode;
  active: boolean;
}

function NavItem({ href, label, icon, active }: NavItemProps) {
  return (
    <div style={{ position: "relative" }}>
      {active && (
        <div
          style={{
            position: "absolute",
            left: "-0.75rem",
            top: "50%",
            transform: "translateY(-50%)",
            width: "3px",
            height: "1rem",
            background: "var(--accent)",
            borderRadius: "0 4px 4px 0",
          }}
        />
      )}
      <Link
        href={href}
        style={{
          display: "flex",
          alignItems: "center",
          gap: "0.625rem",
          padding: "0.5rem 0.75rem",
          borderRadius: "var(--radius-md)",
          fontSize: "0.8125rem",
          fontWeight: active ? 600 : 500,
          color: active ? "var(--accent)" : "var(--text-secondary)",
          background: active ? "var(--accent-dim)" : "transparent",
          textDecoration: "none",
          transition: "all 0.15s ease",
        }}
        onMouseEnter={(e) => {
          if (!active) {
            e.currentTarget.style.background = "var(--bg-surface-2)";
            e.currentTarget.style.color = "var(--text-primary)";
          }
        }}
        onMouseLeave={(e) => {
          if (!active) {
            e.currentTarget.style.background = "transparent";
            e.currentTarget.style.color = "var(--text-secondary)";
          }
        }}
      >
        <span style={{ color: active ? "var(--accent)" : "inherit" }}>{icon}</span>
        {label}
      </Link>
    </div>
  );
}

// ─── Icons (16px) ──────────────────────────────────────────────────────────────

function FixFlowLogo() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
      <rect x="2" y="2" width="20" height="20" rx="4" stroke="var(--text-primary)" strokeWidth="1.5" />
      <path d="M7 12h10M12 7v10" stroke="var(--text-primary)" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  );
}

function DashboardIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
      <rect x="3" y="3" width="7" height="7" rx="1" stroke="currentColor" strokeWidth="1.5" />
      <rect x="14" y="3" width="7" height="7" rx="1" stroke="currentColor" strokeWidth="1.5" />
      <rect x="3" y="14" width="7" height="7" rx="1" stroke="currentColor" strokeWidth="1.5" />
      <rect x="14" y="14" width="7" height="7" rx="1" stroke="currentColor" strokeWidth="1.5" />
    </svg>
  );
}

function IncidentsIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
      <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="1.5" />
      <path d="M12 7v5l3 3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function RepoIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
      <path d="M3 3h18v18H3z" rx="2" stroke="currentColor" strokeWidth="1.5" fill="none" />
      <path d="M3 9h18M9 21V9" stroke="currentColor" strokeWidth="1.5" />
    </svg>
  );
}

function SettingsIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
      <circle cx="12" cy="12" r="3" stroke="currentColor" strokeWidth="1.5" />
      <path
        d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"
        stroke="currentColor"
        strokeWidth="1.5"
      />
    </svg>
  );
}

function LogoutIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
      <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function MonitoringIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
      <path d="M2 12h4l3-9 5 18 3-9h5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function PatchesIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
      <path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z" stroke="currentColor" strokeWidth="1.5" />
    </svg>
  );
}

function VerificationIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
      <path d="M9 11l3 3L22 4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function ActivityIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
      <path d="M22 12h-4l-3 9L9 3l-3 9H2" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function AutomationsIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
      <rect x="2" y="14" width="20" height="8" rx="2" stroke="currentColor" strokeWidth="1.5" />
      <rect x="6" y="2" width="12" height="8" rx="2" stroke="currentColor" strokeWidth="1.5" />
      <path d="M12 10v4" stroke="currentColor" strokeWidth="1.5" />
    </svg>
  );
}

function IntegrationsIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
      <path d="M12 2v20" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      <path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function PoliciesIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function JourneysIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
      <circle cx="5" cy="12" r="2" stroke="currentColor" strokeWidth="1.5" />
      <circle cx="19" cy="5" r="2" stroke="currentColor" strokeWidth="1.5" />
      <circle cx="19" cy="19" r="2" stroke="currentColor" strokeWidth="1.5" />
      <path d="M7 12h4.5a1.5 1.5 0 0 0 1.5-1.5v-2a1.5 1.5 0 0 1 1.5-1.5H17" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      <path d="M7 12h4.5a1.5 1.5 0 0 1 1.5 1.5v2a1.5 1.5 0 0 0 1.5 1.5H17" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  );
}
