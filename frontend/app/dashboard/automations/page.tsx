export default function AutomationsPage() {
  return (
    <div style={{ padding: '2.5rem' }}>
      <div style={{ marginBottom: "2rem", display: "flex", alignItems: "flex-start", justifyContent: "space-between" }}>
        <div>
          <h1 style={{ fontSize: '1.25rem', marginBottom: '0.25rem' }}>Automations</h1>
          <p style={{ fontSize: '0.875rem', color: 'var(--text-muted)' }}>
            Configure auto-healing and auto-merging workflows.
          </p>
        </div>
        <button className="btn btn-primary" disabled style={{ opacity: 0.5 }}>+ New Automation</button>
      </div>
      
      <div className="card" style={{ padding: '5rem 2rem', textAlign: 'center', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '1.25rem' }}>
        <div style={{ width: "48px", height: "48px", borderRadius: "var(--radius-lg)", border: "1px solid var(--border)", display: "flex", alignItems: "center", justifyContent: "center", color: "var(--accent)", background: "var(--accent-dim)" }}>
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
            <rect x="2" y="14" width="20" height="8" rx="2" stroke="currentColor" strokeWidth="2" />
            <rect x="6" y="2" width="12" height="8" rx="2" stroke="currentColor" strokeWidth="2" />
            <path d="M12 10v4" stroke="currentColor" strokeWidth="2" />
          </svg>
        </div>
        <div>
          <p style={{ fontSize: '1rem', fontWeight: 600, color: "var(--text-primary)" }}>No automations configured</p>
          <p style={{ fontSize: '0.875rem', color: 'var(--text-secondary)', marginTop: '0.375rem', maxWidth: "400px", margin: "0.375rem auto 0" }}>
            By default, FixFlow requires human approval to merge patches. You can set up rules to auto-merge verified fixes.
          </p>
        </div>
      </div>
    </div>
  );
}
