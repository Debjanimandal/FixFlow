"use client";

import { useEffect, useState, useCallback, useRef, useMemo } from "react";
import { incidents as incidentsApi, repositories as reposApi, type IncidentListItem, type Repository } from "@/lib/api-client";
import { STATUS_LABELS, SEVERITY_LABELS } from "@/lib/design-tokens";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip as RechartsTooltip, ResponsiveContainer, Cell } from "recharts";

const POLL_INTERVAL_MS = 15_000;

export default function DashboardPage() {
  const [incidents, setIncidents] = useState<IncidentListItem[]>([]);
  const [repos, setRepos] = useState<Repository[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const pollTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const fetchIncidents = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    try {
      const data = await incidentsApi.list({ limit: 50 });
      setIncidents(data);
      setError(null);
    } catch (err: any) {
      if (!silent) setError(err.message);
    } finally {
      if (!silent) setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchIncidents();
    reposApi.list().then(setRepos).catch(() => {});
  }, [fetchIncidents]);

  useEffect(() => {
    const schedule = () => {
      pollTimerRef.current = setTimeout(async () => {
        await fetchIncidents(true);
        schedule();
      }, POLL_INTERVAL_MS);
    };
    schedule();
    return () => {
      if (pollTimerRef.current) clearTimeout(pollTimerRef.current);
    };
  }, [fetchIncidents]);

  const stats = useMemo(() => ({
    total: incidents.length,
    active: incidents.filter((i) =>
      ["detected", "analyzing", "root_cause_identified", "repair_proposed",
       "verifying", "awaiting_review", "needs_review"].includes(i.status)
    ).length,
    critical: incidents.filter((i) => i.severity === "critical").length,
    resolved: incidents.filter((i) => i.status === "resolved").length,
  }), [incidents]);

  const barChartData = useMemo(() => {
    const days: Record<string, number> = {};
    const labels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
    labels.forEach(l => days[l] = 0); // Init
    
    incidents.forEach(inc => {
      const d = new Date(inc.created_at);
      const label = d.toLocaleDateString('en-US', { weekday: 'short' });
      if (days[label] !== undefined) {
        days[label] += 1;
      }
    });

    const data = Object.entries(days).map(([name, value]) => ({ name, value, prevValue: 0 }));
    // Calculate prevValue for dynamic trend
    for (let i = 1; i < data.length; i++) {
      data[i].prevValue = data[i - 1].value;
    }
    return data;
  }, [incidents]);

  const [activeIndex, setActiveIndex] = useState(4); // Default highlighted bar

  return (
    <div style={{ padding: "2rem", display: "flex", flexDirection: "column", gap: "1.5rem" }}>
      
      {/* ── Top Row: Metrics ── */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "1.5rem" }}>
        <MetricCard 
          label="SYSTEM HEALTH" 
          value={stats.active > 0 ? "Degraded" : "Healthy"} 
          trend={stats.active > 0 ? "-2.4%" : "+100%"} 
          trendPositive={stats.active === 0}
          delayClass="delay-0"
        />
        <MetricCard 
          label="ACTIVE INCIDENTS" 
          value={stats.active.toString()} 
          trend={`+${stats.active}`} 
          trendPositive={stats.active === 0}
          delayClass="delay-1"
        />
        <MetricCard 
          label="MONITORED REPOS" 
          value={repos.length.toString()} 
          trend="+1" 
          trendPositive={true}
          delayClass="delay-2"
        />
        <MetricCard 
          label="RECOVERIES (MTD)" 
          value={stats.resolved.toString()} 
          trend="+12%" 
          trendPositive={true}
          delayClass="delay-3"
        />
      </div>

      {/* ── Middle Row: 40/60 Split ── */}
      <div style={{ display: "grid", gridTemplateColumns: "4fr 6fr", gap: "1.5rem" }}>
        
        {/* Left: Live Activity (System Logs) */}
        <div className="card animate-fade-in delay-4" style={{ display: "flex", flexDirection: "column", height: "420px" }}>
          <div style={{ marginBottom: "1.25rem", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div>
              <h3 style={{ fontSize: "0.875rem", fontWeight: 600, color: "var(--text-primary)" }}>System Logs</h3>
              <p style={{ fontSize: "0.75rem", color: "var(--text-dim)" }}>Recent events and notifications</p>
            </div>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" color="var(--text-muted)"><circle cx="12" cy="12" r="1" stroke="currentColor" strokeWidth="2"/><circle cx="12" cy="5" r="1" stroke="currentColor" strokeWidth="2"/><circle cx="12" cy="19" r="1" stroke="currentColor" strokeWidth="2"/></svg>
          </div>
          
          <div style={{ flex: 1, overflowY: "auto", display: "flex", flexDirection: "column" }}>
            {incidents.slice(0, 5).map((inc, i) => {
              const bgSolid = getSolidStatusBgColor(inc.status);
              return (
                <div key={inc.id} style={{ display: "flex", gap: "1rem", padding: "1rem 0", borderBottom: i < 4 ? "1px solid var(--border-subtle)" : "none" }}>
                  <div style={{ width: "36px", height: "36px", borderRadius: "10px", background: bgSolid, color: "#FFFFFF", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0, boxShadow: "var(--shadow-sm)" }}>
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                      {bgSolid === "#10B981" && <><circle cx="12" cy="12" r="10"/><path d="M9 12l2 2 4-4"/></>}
                      {bgSolid === "#F97316" && <><path d="M18.36 6.64a9 9 0 1 1-12.73 0"/><line x1="12" y1="2" x2="12" y2="12"/></>}
                      {bgSolid === "#0EA5E9" && <><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></>}
                      {bgSolid === "#737373" && <><path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/></>}
                      {bgSolid === "#F59E0B" && <><circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/></>}
                    </svg>
                  </div>
                  <div style={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column", justifyContent: "center" }}>
                    <p style={{ fontSize: "0.875rem", color: "var(--text-primary)", fontWeight: 600 }}>
                      Incident {inc.id.slice(0,6)} <span style={{ textTransform: "capitalize" }}>{inc.status.replace(/_/g, ' ')}</span>
                    </p>
                    <p style={{ fontSize: "0.8125rem", color: "var(--text-dim)", marginTop: "2px", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                      {inc.title}
                    </p>
                  </div>
                  <div style={{ textAlign: "right", whiteSpace: "nowrap", display: "flex", flexDirection: "column", alignItems: "flex-end", justifyContent: "center", gap: "0.25rem" }}>
                    <div style={{ display: "flex" }}>
                      <div style={{ width: "20px", height: "20px", borderRadius: "50%", background: "#E5E7EB", border: "2px solid #FFFFFF", display: "flex", alignItems: "center", justifyContent: "center", fontSize: "0.5rem", color: "#4B5563", fontWeight: "bold", zIndex: 2 }}>
                        🤖
                      </div>
                      <div style={{ width: "20px", height: "20px", borderRadius: "50%", background: "#BFDBFE", border: "2px solid #FFFFFF", display: "flex", alignItems: "center", justifyContent: "center", fontSize: "0.625rem", color: "#1D4ED8", fontWeight: "bold", marginLeft: "-8px", zIndex: 1 }}>
                        J
                      </div>
                    </div>
                    <p style={{ fontSize: "0.75rem", color: "var(--text-dim)" }}>
                      {formatRelative(inc.updated_at ?? inc.created_at)}
                    </p>
                  </div>
                </div>
              );
            })}
            {incidents.length === 0 && (
              <p style={{ fontSize: "0.8125rem", color: "var(--text-dim)", textAlign: "center", marginTop: "2rem" }}>Listening for events...</p>
            )}
          </div>
        </div>

        {/* Right: Bar Chart */}
        <div className="card animate-fade-in delay-5" style={{ display: "flex", flexDirection: "column", height: "420px" }}>
          <div style={{ marginBottom: "1rem", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div>
              <h3 style={{ fontSize: "0.875rem", fontWeight: 600, color: "var(--text-primary)" }}>Incident Volume</h3>
              <p style={{ fontSize: "0.75rem", color: "var(--text-dim)" }}>
                <span style={{ color: "var(--text-primary)", fontWeight: 500, fontSize: "1.125rem", marginRight: "0.5rem" }}>
                  {stats.total.toLocaleString()}
                </span>
                total incidents
              </p>
            </div>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" color="var(--text-muted)"><circle cx="12" cy="12" r="1" stroke="currentColor" strokeWidth="2"/><circle cx="12" cy="5" r="1" stroke="currentColor" strokeWidth="2"/><circle cx="12" cy="19" r="1" stroke="currentColor" strokeWidth="2"/></svg>
          </div>
          <div style={{ flex: 1, position: "relative" }}>
            {incidents.length === 0 ? (
              <div style={{ height: "100%", display: "flex", alignItems: "center", justifyContent: "center", color: "var(--text-dim)", fontSize: "0.8125rem" }}>Gathering historical data...</div>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={barChartData} margin={{ top: 20, right: 0, left: -20, bottom: 0 }}
                  onMouseMove={(state: any) => {
                    if (state.isTooltipActive) setActiveIndex(state.activeTooltipIndex);
                  }}
                  onMouseLeave={() => setActiveIndex(4)}
                >
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--border-subtle)" opacity={0.5} />
                  <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{ fontSize: 12, fill: "var(--text-dim)", fontWeight: 500 }} dy={10} />
                  <YAxis axisLine={false} tickLine={false} tick={false} />
                  
                  {/* Custom Tooltip */}
                  <RechartsTooltip
                    cursor={{ fill: 'transparent' }}
                    content={({ active, payload }) => {
                      if (active && payload && payload.length) {
                        const data = payload[0].payload;
                        const hasPrev = data.prevValue > 0;
                        const trend = hasPrev ? ((data.value - data.prevValue) / data.prevValue) * 100 : 0;
                        const isPositive = trend >= 0;
                        
                        return (
                          <div style={{ background: "#262626", borderRadius: "12px", padding: "0.75rem 1rem", color: "white", boxShadow: "var(--shadow-lg)", minWidth: "120px" }}>
                            <p style={{ fontSize: "0.6875rem", color: "#A3A3A3", marginBottom: "0.25rem" }}>Total incidents</p>
                            <p style={{ fontSize: "1.125rem", fontWeight: 500, marginBottom: data.prevValue > 0 || data.value > 0 ? "0.25rem" : "0" }}>{data.value}</p>
                            {(data.prevValue > 0 || data.value > 0) && (
                              <p style={{ fontSize: "0.6875rem", color: "#A3A3A3", display: "flex", justifyContent: "space-between", gap: "1rem" }}>
                                vs previous day 
                                {hasPrev ? (
                                  <span style={{ color: isPositive ? "#F87171" : "#34D399" }}>
                                    {isPositive ? "+" : ""}{trend.toFixed(1)}%
                                  </span>
                                ) : (
                                  <span style={{ color: "#A3A3A3" }}>—</span>
                                )}
                              </p>
                            )}
                          </div>
                        );
                      }
                      return null;
                    }}
                  />
                  
                  <Bar dataKey="value" radius={[8, 8, 8, 8]} barSize={48} minPointSize={8}>
                    {barChartData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={index === activeIndex ? "var(--accent)" : "var(--bg-surface-3)"} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>
        </div>

      </div>

      {/* ── Bottom Row: Data Table ── */}
      <div className="card animate-fade-in delay-5" style={{ padding: 0, display: "flex", flexDirection: "column", overflow: "hidden" }}>
        <div style={{ padding: "1.25rem 1.5rem", borderBottom: "1px solid var(--border-subtle)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div>
            <h3 style={{ fontSize: "1rem", fontWeight: 600, color: "var(--text-primary)" }}>Recent Incidents Log</h3>
            <p style={{ fontSize: "0.8125rem", color: "var(--text-dim)", marginTop: "2px" }}>Recent endpoint activity and status</p>
          </div>
          <div style={{ display: "flex", gap: "0.75rem", alignItems: "center" }}>
             <div style={{ position: "relative", width: "240px" }}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" style={{ position: "absolute", left: "0.75rem", top: "50%", transform: "translateY(-50%)", color: "var(--text-dim)" }}>
                <circle cx="11" cy="11" r="8" stroke="currentColor" strokeWidth="2" />
                <path d="M21 21l-4.35-4.35" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
              </svg>
              <input type="text" placeholder="Search" style={{ width: "100%", height: "36px", background: "var(--bg-surface)", border: "1px solid var(--border-subtle)", borderRadius: "6px", padding: "0 1rem 0 2rem", fontSize: "0.8125rem", color: "var(--text-primary)", outline: "none", boxShadow: "var(--shadow-sm)" }} />
            </div>
            <div style={{ display: "flex", background: "var(--bg-surface)", border: "1px solid var(--border-subtle)", borderRadius: "6px", padding: "4px", boxShadow: "var(--shadow-sm)" }}>
              <button style={{ padding: "0.375rem 0.75rem", fontSize: "0.8125rem", background: "var(--bg-surface-2)", borderRadius: "4px", border: "1px solid var(--border-subtle)", fontWeight: 500, color: "var(--text-primary)", display: "flex", alignItems: "center", gap: "0.375rem" }}>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01" strokeLinecap="round" strokeLinejoin="round"/></svg>
                List
              </button>
              <button style={{ padding: "0.375rem 0.75rem", fontSize: "0.8125rem", background: "transparent", borderRadius: "4px", border: "1px solid transparent", color: "var(--text-dim)", display: "flex", alignItems: "center", gap: "0.375rem" }}>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M4 4h6v6H4zM14 4h6v6h-6zM4 14h6v6H4zM14 14h6v6h-6z" strokeLinecap="round" strokeLinejoin="round"/></svg>
                Grid
              </button>
            </div>
          </div>
        </div>
        
        <div style={{ overflowX: "auto" }}>
          {loading && <TableSkeleton />}
          {error && <ErrorState message={error} />}
          {!loading && !error && incidents.length === 0 && (
             <div style={{ padding: "4rem", textAlign: "center", color: "var(--text-dim)", fontSize: "0.875rem" }}>
               No recent incidents.
             </div>
          )}
          {!loading && !error && incidents.length > 0 && (
            <IncidentTable incidents={incidents.slice(0, 6)} />
          )}
        </div>

        {/* Pagination Footer (Only show if there are more than 6 incidents) */}
        {incidents.length > 6 && (
          <div style={{ padding: "1.25rem 1.5rem", borderTop: "1px solid var(--border-subtle)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <p style={{ fontSize: "0.875rem", color: "var(--text-dim)" }}>
              Showing 6 of {incidents.length} incidents
            </p>
            <div style={{ display: "flex", gap: "0.375rem" }}>
              <button style={{ width: "32px", height: "32px", display: "flex", alignItems: "center", justifyContent: "center", background: "var(--bg-surface)", border: "1px solid var(--border-subtle)", borderRadius: "6px", color: "var(--text-dim)", cursor: "pointer", boxShadow: "var(--shadow-sm)" }}>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M15 18l-6-6 6-6"/></svg>
              </button>
              <button style={{ width: "32px", height: "32px", display: "flex", alignItems: "center", justifyContent: "center", background: "#111111", border: "1px solid #111111", borderRadius: "6px", color: "#FFFFFF", fontSize: "0.875rem", fontWeight: 500, cursor: "pointer", boxShadow: "var(--shadow-sm)" }}>1</button>
              <button style={{ width: "32px", height: "32px", display: "flex", alignItems: "center", justifyContent: "center", background: "var(--bg-surface)", border: "1px solid var(--border-subtle)", borderRadius: "6px", color: "var(--text-secondary)", fontSize: "0.875rem", fontWeight: 500, cursor: "pointer", boxShadow: "var(--shadow-sm)" }}>2</button>
              <button style={{ width: "32px", height: "32px", display: "flex", alignItems: "center", justifyContent: "center", background: "transparent", border: "none", color: "var(--text-dim)", fontSize: "0.875rem", fontWeight: 500, pointerEvents: "none" }}>...</button>
              <button style={{ width: "32px", height: "32px", display: "flex", alignItems: "center", justifyContent: "center", background: "var(--bg-surface)", border: "1px solid var(--border-subtle)", borderRadius: "6px", color: "var(--text-secondary)", fontSize: "0.875rem", fontWeight: 500, cursor: "pointer", boxShadow: "var(--shadow-sm)" }}>6</button>
              <button style={{ width: "32px", height: "32px", display: "flex", alignItems: "center", justifyContent: "center", background: "var(--bg-surface)", border: "1px solid var(--border-subtle)", borderRadius: "6px", color: "var(--text-secondary)", fontSize: "0.875rem", fontWeight: 500, cursor: "pointer", boxShadow: "var(--shadow-sm)" }}>7</button>
              <button style={{ width: "32px", height: "32px", display: "flex", alignItems: "center", justifyContent: "center", background: "var(--bg-surface)", border: "1px solid var(--border-subtle)", borderRadius: "6px", color: "var(--text-secondary)", cursor: "pointer", boxShadow: "var(--shadow-sm)" }}>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M9 18l6-6-6-6"/></svg>
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ─── Sub-Components ────────────────────────────────────────────────────────────

function MetricCard({ label, value, trend, trendPositive, delayClass }: { label: string; value: string | number; trend: string; trendPositive: boolean; delayClass: string }) {
  return (
    <div className={`card animate-fade-in ${delayClass}`} style={{ display: "flex", flexDirection: "column", padding: "1.25rem 1.5rem" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
        <p style={{ fontSize: "0.6875rem", fontWeight: 600, color: "var(--text-secondary)", textTransform: "uppercase", letterSpacing: "0.05em", display: "flex", alignItems: "center", gap: "0.5rem" }}>
          {label === "SYSTEM HEALTH" && (
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" color="var(--accent)"><rect x="2" y="3" width="20" height="14" rx="2" stroke="currentColor" strokeWidth="2"/><path d="M8 21h8m-4-4v4" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/></svg>
          )}
          {label === "ACTIVE INCIDENTS" && (
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" color="var(--accent)"><path d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/></svg>
          )}
          {label === "MONITORED REPOS" && (
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" color="var(--accent)"><path d="M3 3h18v18H3z" rx="2" stroke="currentColor" strokeWidth="2"/><path d="M3 9h18M9 21V9" stroke="currentColor" strokeWidth="2"/></svg>
          )}
          {label === "RECOVERIES (MTD)" && (
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" color="var(--accent)"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/></svg>
          )}
          {label}
        </p>
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" color="var(--text-dim)"><circle cx="12" cy="12" r="1" stroke="currentColor" strokeWidth="2"/><circle cx="12" cy="5" r="1" stroke="currentColor" strokeWidth="2"/><circle cx="12" cy="19" r="1" stroke="currentColor" strokeWidth="2"/></svg>
      </div>
      
      <p style={{ fontSize: "2rem", fontWeight: 300, color: "var(--text-primary)", lineHeight: 1, marginBottom: "1.25rem", display: "flex", alignItems: "baseline", gap: "0.25rem" }}>
        {label === "SYSTEM HEALTH" ? (
          value
        ) : (
          <>
            {value} <span style={{ fontSize: "0.875rem", color: "var(--text-secondary)", fontWeight: 400 }}>total</span>
          </>
        )}
      </p>

      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", borderTop: "1px solid var(--border-subtle)", paddingTop: "0.75rem", marginTop: "auto" }}>
        <p style={{ fontSize: "0.75rem", color: "var(--text-dim)" }}>vs last month</p>
        <span style={{ 
          fontSize: "0.75rem", 
          fontWeight: 600, 
          color: trendPositive ? "#10B981" : "#EF4444",
          display: "flex",
          alignItems: "center",
          gap: "0.125rem"
        }}>
          {trendPositive ? (
            <svg width="10" height="10" viewBox="0 0 24 24" fill="none"><path d="M18 15l-6-6-6 6" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"/></svg>
          ) : (
            <svg width="10" height="10" viewBox="0 0 24 24" fill="none"><path d="M6 9l6 6 6-6" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"/></svg>
          )}
          {trend}
        </span>
      </div>
    </div>
  );
}

function IncidentTable({ incidents }: { incidents: IncidentListItem[] }) {
  return (
    <table style={{ width: "100%", borderCollapse: "collapse" }}>
      <thead>
        <tr style={{ background: "var(--bg-surface-2)" }}>
          {["Incident ID", "Repository", "Type", "Status", "Duration", "Time", ""].map((col) => (
            <th key={col} style={{ padding: "0.875rem 1.5rem", textAlign: "left", fontSize: "0.875rem", fontWeight: 500, color: "var(--text-secondary)", whiteSpace: "nowrap", borderBottom: "1px solid var(--border-subtle)" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                {col}
                {col && (
                  <div style={{ display: "flex", flexDirection: "column", gap: "1px", color: "var(--text-dim)" }}>
                    <svg width="8" height="8" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" style={{ marginBottom: "-2px" }}><path d="M18 15l-6-6-6 6"/></svg>
                    <svg width="8" height="8" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"><path d="M6 9l6 6 6-6"/></svg>
                  </div>
                )}
              </div>
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
  );
}

function IncidentRow({ incident, index }: { incident: IncidentListItem; index: number }) {
  return (
    <tr
      style={{
        borderBottom: "1px solid var(--border-subtle)",
        cursor: "pointer",
        transition: "background 0.15s ease",
      }}
      onMouseEnter={(e) => { e.currentTarget.style.background = "var(--bg-surface-2)"; }}
      onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; }}
      onClick={() => { window.location.href = `/dashboard/incidents/${incident.id}`; }}
    >
      <td style={{ padding: "1.25rem 1.5rem", whiteSpace: "nowrap" }}>
        <span style={{ fontSize: "0.875rem", color: "var(--text-primary)", fontWeight: 600 }}>
          INC-{incident.id.slice(0,6)}
        </span>
      </td>
      <td style={{ padding: "1.25rem 1.5rem", whiteSpace: "nowrap" }}>
        <span style={{ fontSize: "0.875rem", color: "#0ea5e9", fontWeight: 500 }}>
          /{incident.repository_full_name ?? "repo"}
        </span>
      </td>
      <td style={{ padding: "1.25rem 1.5rem", whiteSpace: "nowrap" }}>
        <span style={{ fontSize: "0.75rem", fontWeight: 600, color: "var(--text-secondary)", textTransform: "uppercase", background: "var(--bg-surface-2)", padding: "0.25rem 0.625rem", borderRadius: "6px", border: "1px solid var(--border-subtle)" }}>
          {incident.failure_type.split('_')[0]}
        </span>
      </td>
      <td style={{ padding: "1.25rem 1.5rem", whiteSpace: "nowrap" }}>
        <span className={`status-chip status-chip-${incident.status.toLowerCase()}`}>
          {STATUS_LABELS[incident.status] ?? incident.status.toUpperCase()}
        </span>
      </td>
      <td style={{ padding: "1.25rem 1.5rem", whiteSpace: "nowrap" }}>
        <span style={{ fontSize: "0.875rem", color: "var(--text-secondary)" }}>
          124ms
        </span>
      </td>
      <td style={{ padding: "1.25rem 1.5rem", whiteSpace: "nowrap" }}>
        <span style={{ fontSize: "0.875rem", color: "var(--text-secondary)" }}>
          {new Date(incident.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false })}
        </span>
      </td>
      <td style={{ padding: "1.25rem 1.5rem", textAlign: "right", whiteSpace: "nowrap" }}>
        <button style={{ width: "36px", height: "36px", borderRadius: "8px", background: "var(--bg-surface)", border: "1px solid var(--border-subtle)", display: "inline-flex", alignItems: "center", justifyContent: "center", color: "var(--text-dim)", cursor: "pointer", boxShadow: "var(--shadow-sm)" }}>
           <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
        </button>
      </td>
    </tr>
  );
}

function TableSkeleton() {
  return (
    <div style={{ padding: "1.5rem" }}>
      {[...Array(5)].map((_, i) => (
        <div key={i} style={{ height: "2.5rem", background: "var(--bg-surface-2)", borderRadius: "var(--radius-md)", marginBottom: "0.5rem", opacity: 1 - i * 0.15, animation: "pulse-subtle 1.5s ease-in-out infinite", animationDelay: `${i * 0.1}s` }} />
      ))}
    </div>
  );
}

function ErrorState({ message }: { message: string }) {
  return <div style={{ padding: "2rem", textAlign: "center", color: "var(--severity-critical)", fontSize: "0.8125rem" }}>Failed to load incidents: {message}</div>;
}

function formatRelative(dateStr: string): string {
  const date = new Date(dateStr);
  const now = new Date();
  const diff = now.getTime() - date.getTime();
  const mins = Math.floor(diff / 60000);
  const hours = Math.floor(diff / 3600000);

  if (mins < 1) return "just now";
  if (mins < 60) return `${mins} mins ago`;
  if (hours < 24) return `${hours} hrs ago`;
  return date.toLocaleDateString();
}

function getStatusBgColor(status: string) {
  if (status === 'resolved' || status === 'verified') return '#D1FAE5';
  if (status.includes('fail')) return '#FEE2E2';
  if (status.includes('review')) return '#FEF3C7';
  if (status === 'detected') return '#F3F4F6';
  return 'var(--accent-dim)';
}

function getStatusColor(status: string) {
  if (status === 'resolved' || status === 'verified') return '#10B981';
  if (status.includes('fail')) return '#EF4444';
  if (status.includes('review')) return '#D97706';
  if (status === 'detected') return '#6B7280';
  return 'var(--accent)';
}

function getSolidStatusBgColor(status: string) {
  if (status === 'resolved' || status === 'verified') return '#10B981'; // Green
  if (status.includes('fail')) return '#F97316'; // Orange
  if (status.includes('review')) return '#F59E0B'; // Yellow
  if (status.includes('analyzing') || status.includes('repair')) return '#0EA5E9'; // Blue
  return '#737373'; // Gray for detected or others
}
