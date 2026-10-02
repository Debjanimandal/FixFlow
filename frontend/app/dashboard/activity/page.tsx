export default function ActivityPage() {
  return (
    <div style={{ padding: '2.5rem' }}>
      <div style={{ marginBottom: "2rem" }}>
        <h1 style={{ fontSize: '1.25rem', marginBottom: '0.25rem' }}>Activity</h1>
        <p style={{ fontSize: '0.875rem', color: 'var(--text-muted)' }}>
          System-wide audit log of AI actions and user approvals.
        </p>
      </div>
      
      <div className="card" style={{ padding: '5rem 2rem', textAlign: 'center', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '1.25rem' }}>
        <div style={{ width: "48px", height: "48px", borderRadius: "var(--radius-lg)", border: "1px solid var(--border)", display: "flex", alignItems: "center", justifyContent: "center", color: "var(--accent)", background: "var(--accent-dim)" }}>
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
            <path d="M22 12h-4l-3 9L9 3l-3 9H2" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </div>
        <div>
          <p style={{ fontSize: '1rem', fontWeight: 600, color: "var(--text-primary)" }}>No activity recorded yet</p>
          <p style={{ fontSize: '0.875rem', color: 'var(--text-secondary)', marginTop: '0.375rem', maxWidth: "400px", margin: "0.375rem auto 0" }}>
            As incidents are detected and resolved, a full audit trail will appear here.
          </p>
        </div>
      </div>
    </div>
  );
}
