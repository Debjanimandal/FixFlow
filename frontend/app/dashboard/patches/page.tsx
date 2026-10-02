export default function PatchesPage() {
  return (
    <div style={{ padding: '2.5rem' }}>
      <div style={{ marginBottom: "2rem" }}>
        <h1 style={{ fontSize: '1.25rem', marginBottom: '0.25rem' }}>Patches</h1>
        <p style={{ fontSize: '0.875rem', color: 'var(--text-muted)' }}>
          AI-generated code fixes and pull request proposals.
        </p>
      </div>
      
      <div className="card" style={{ padding: '5rem 2rem', textAlign: 'center', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '1.25rem' }}>
        <div style={{ width: "48px", height: "48px", borderRadius: "var(--radius-lg)", border: "1px solid var(--border)", display: "flex", alignItems: "center", justifyContent: "center", color: "var(--accent)", background: "var(--accent-dim)" }}>
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
            <path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </div>
        <div>
          <p style={{ fontSize: '1rem', fontWeight: 600, color: "var(--text-primary)" }}>No repair proposals yet</p>
          <p style={{ fontSize: '0.875rem', color: 'var(--text-secondary)', marginTop: '0.375rem', maxWidth: "400px", margin: "0.375rem auto 0" }}>
            FixFlow will surface generated patches here when an incident requires a repair.
          </p>
        </div>
      </div>
    </div>
  );
}
