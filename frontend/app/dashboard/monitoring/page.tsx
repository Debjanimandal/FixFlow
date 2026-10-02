export default function MonitoringPage() {
  return (
    <div style={{ padding: '2.5rem' }}>
      <div style={{ marginBottom: "2rem" }}>
        <h1 style={{ fontSize: '1.25rem', marginBottom: '0.25rem' }}>Monitoring</h1>
        <p style={{ fontSize: '0.875rem', color: 'var(--text-muted)' }}>
          Real-time ingestion of application logs, traces, and metrics.
        </p>
      </div>
      
      <div className="card" style={{ padding: '5rem 2rem', textAlign: 'center', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '1.25rem' }}>
        <div style={{ position: "relative" }}>
          <div style={{ width: "48px", height: "48px", borderRadius: "var(--radius-lg)", border: "1px solid var(--border)", display: "flex", alignItems: "center", justifyContent: "center", color: "var(--accent)", background: "var(--accent-dim)" }}>
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
              <path d="M2 12h4l3-9 5 18 3-9h5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </div>
          <div style={{ position: "absolute", top: -4, right: -4, width: "12px", height: "12px", borderRadius: "50%", background: "#22c55e", border: "2px solid var(--bg-surface)", boxShadow: "0 0 0 2px #22c55e33" }} />
        </div>
        <div>
          <p style={{ fontSize: '1rem', fontWeight: 600, color: "var(--text-primary)" }}>Monitoring is active</p>
          <p style={{ fontSize: '0.875rem', color: 'var(--text-secondary)', marginTop: '0.375rem', maxWidth: "400px", margin: "0.375rem auto 0" }}>
            FixFlow is actively listening to your connected repositories and Vercel projects. Waiting for the next error signal.
          </p>
        </div>
        <div style={{ display: "flex", gap: "0.75rem", marginTop: "1rem" }}>
          <span style={{ fontSize: "0.75rem", color: "var(--text-dim)", display: "flex", alignItems: "center", gap: "0.375rem" }}>
            <span style={{ width: 6, height: 6, borderRadius: "50%", background: "#22c55e", display: "inline-block", animation: "pulse-subtle 2s ease-in-out infinite" }} />
            Listening to 1 repository
          </span>
        </div>
      </div>
    </div>
  );
}
